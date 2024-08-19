import pillow_heif
import piexif
import tempfile
import gc
import io
from datetime import datetime
from googleapiclient.http import MediaIoBaseDownload
from PIL.ExifTags import TAGS
from googleapiclient.discovery import build
from google.oauth2 import service_account
from utils import *
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

files_map = {} 

def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes= SCOPES)
    return creds

def standardize_date(date_string, master_log):
    formats = [
        "%Y-%m-%d %H:%M:%S",  # Format with dashes
        "%Y/%m/%d %H:%M:%S",  # Format with slashes
        "%Y:%m:%d %H:%M:%S",  # Format with colons
    ]
    
    for fmt in formats:
        try:
            # Attempt to parse the datetime string
            return datetime.strptime(date_string, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            continue
    
    #If none of the formats work return None
    if master_log:
        master_log.write(f"ERROR: date format for date: {date_string} not supported.\n")
        return None
    
def extract_datetime_heic(exif_data):
    datetime_tags = {
        36867: 'DateTimeOriginal',  # Tag ID for DateTimeOriginal (when media was taken)
        36868: 'DateTimeDigitized',  # Tag ID for DateTimeDigitized
        306: 'DateTime',  # Tag ID for DateTime (Last modified)
    }

    if exif_data:
        for tag, value in exif_data.items():
            decoded_tag = TAGS.get(tag, tag)
            if decoded_tag == "DateTimeOriginal":
                #print(f"Original DateTime: {value}")
                return value
    return None

def extract_datetime_general(metadata):
    """
    will get the date time of creation for general media formats. 
    """
    creation_date = None
    possible_creation_time_keys = [ #ordered in priority
        'creation date',
        'creation-date', 
        'date-time original',
        'date time original', 
        'date-time-original', 
        'date-time-original',
        'datetime original',
        'datetime-original',
        'date created',
        'date-created',
        'date taken',
        'date-taken',
        'time-of-creation',
        'time of creation',
        'original-date',
        'original date',
        'datetime', 
        'date', 
    ]
    creation_date = None
    if metadata:
        data = metadata.get('Metadata', {})
        for key in possible_creation_time_keys:
            creation_date = data.get(key)
            if creation_date:
                break
    return creation_date

def get_all_files(service, master_log, parent_id= PARENT_FOLDER_ID):
    all_files = []
    master_log.write("")
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{parent_id}' in parents",
            fields="nextPageToken, files(id, name, mimeType, parents)",
            pageToken=page_token
        ).execute()

        files = results.get('files', [])
        all_files.extend(files)
        
        page_token = results.get('nextPageToken', None)
        if page_token is None:
            break
    if master_log:
        master_log.write(
                        f"Parsing files from drive fodler id {parent_id}\n"+
                        f"\t Number of files to be targeted: {len(all_files)}\n"
                        )
    return all_files

def fetch_exif_from_heic(fh, master_log):
    """
    Handle extracting exif data from .heic files
    """
    heif_file = pillow_heif.open_heif(fh)
    exif_bytes= heif_file.info.get('exif')
    exif_data= piexif.load(exif_bytes)
    return extract_datetime_heic(exif_data.get('Exif'))

def list_to_dict(list_metada):
    metadata_2layer_dict = {}
    if not list_metada: #give empty recieve empty :)
        return metadata_2layer_dict
    else:
        metadata_dict = {} 
        for data in list_metada:
            if(": " in data):
                key, val = data.split(": ", 1)
                key = key.strip("- ").lower().strip() #standardize lower keys for matching later.
                metadata_dict[key] = val
        metadata_2layer_dict['Metadata'] = metadata_dict
    return metadata_2layer_dict

def fetch_exif_general_media(fh, master_log, file_name):
    """
    Handle extracting metadata for majority of file types. 
        - jpeg, mov, mp4, png, jpg, gif...
        - not HEIC! use fetch_exif_from_heic() instead :)
    """

    temp_file = io.BytesIO(fh.read())
    temp_file.seek(0)
    ext = file_name.split('.')[-1].lower()
    print("Parsing filename: %s" % file_name)
    try:
        #Create a temporary file with .mov suffix
        with tempfile.NamedTemporaryFile(suffix= "." + ext, delete=False) as tmp:
            tmp.write(temp_file.read())
            tmp.flush()
            tmp_path = tmp.name  # Save the temporary file path
        if master_log:
            master_log.write(f"\tTemporary file created at {tmp_path}\n")
        parser = createParser(tmp_path)
        metadata = extractMetadata(parser)
        metadata_plain_text = metadata.exportPlaintext()

        if metadata_plain_text is not None:
            metadata_dict = list_to_dict(metadata_plain_text)
            return extract_datetime_general(metadata= metadata_dict)
        else:
            if master_log:
                master_log.write("\tError: Failed to extract metadata from .mov file\n")
            return None
    finally:
        # Clean up and remove the temporary file
        parser, metadata = None, None
        del parser
        del metadata
        gc.collect()
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                if master_log:
                    master_log.write(f"\tTemporary file deleted at {tmp_path}\n")
        except Exception as e:
            if master_log:
                    master_log.write(f"\tError: Failed to delete temporary file: {tmp_path} due to {e}\n")

def fetch_exif_data(service, file_id, file_type, master_log, file_name):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        #print(f"Download {int(status.progress() * 100)}%.") #FOR DEBUGGING REMOVE!

    fh.seek(0)
        
    if("heif" in file_type.lower()): #handle .heic files. 
        media_bday = fetch_exif_from_heic(fh, master_log)
    else: #handle mov, mp4, png, jpeg, jpg... 
        media_bday = fetch_exif_general_media(fh, master_log, file_name)

    return media_bday


def analyze_files(service, master_log):
    files = get_all_files(service, master_log)
    #files = result_file_list.get('files', [])
    if master_log:
        master_log.write("Runing file analysis...\n"+
                        "Extracting metadata from files...\n")
    for file in files:
        file_id, fyle_mimeType, file_name = file['id'], file['mimeType'], file['name']
        media_birthday = fetch_exif_data(service, file_id, fyle_mimeType, master_log, file_name)
        try:
            media_date_creation = media_birthday.decode('utf-8')
            files_map[file_id] = standardize_date(media_date_creation, master_log)
        except Exception:
            files_map[file_id] = standardize_date(media_birthday, master_log)
        if master_log:
                master_log.write(f"Analyzing {file_name} Results\n"+
                                f"\tId: {file_id} || Type: {fyle_mimeType} || Time taken: {files_map[file_id]}\n")


def run_cross_check(games_list, master_log):
    if master_log:
        master_log.write("--------------------CROSS CHECKER RUN INFORMATION--------------------\n\n")
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    analyze_files(service, master_log) #build files map
    if master_log:
        master_log.write("--------------------CROSS CHECKER RUN COMPLETE-----------------------\n\n")
    return files_map


if __name__ == "__main__":
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    analyze_files(service)  
    print(files_map)