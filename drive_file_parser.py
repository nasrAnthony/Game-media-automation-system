from googleapiclient.discovery import build
from google.oauth2 import service_account
from utils import *
from datetime import datetime, timedelta

files_map = {}

def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes= SCOPES)
    return creds

def get_all_files(service, master_log, parent_id) -> list:
    """
    Return list of files from drive folder. 
    """
    all_files = []
    page_token = None
    while True:
        results = service.files().list(
            q= f"'{parent_id}' in parents",
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

def fetch_bday_from_name(file_name, master_log) -> str:
    date_formated = "" 
    try:
        file_name = file_name.split('.')[0] #get file name wihtout ext
        list_name = list(file_name)
        if(len(list_name) != 15):
            raise Exception ("File name must be 15 characters.")
        ymd = file_name.split('_')[0]
        hms = file_name.split('_')[1]
        year = ymd[:4]
        month = ymd[4:6]
        day = ymd[6:]
        hour = hms[:2]
        minutes = hms[2:4]
        seconds = hms[4:]
        date_formated = f"{year}-{month}-{day} {hour}:{minutes}:{seconds}"
    except Exception as e:
        if master_log:
            master_log.write(f"Error formating the date please check the name of the file {file_name}\n")
            master_log.write(f"\tERROR => {e}\n")
            return date_formated
    return date_formated

def analyze_files(service, master_log):
    master_error_count = 0 
    files = get_all_files(service, master_log, UNPROCESSED_FOOTAGE_FOLDER_ID)
    if(len(files) == 0 and master_log):
        master_log.write("No files were found in the Google Drive folder.")
    #files = result_file_list.get('files', [])
    if master_log:
        master_log.write("Runing file analysis...\n"+
                        "Extracting creation date from files...\n")
    for file in files:
        file_id, fyle_mimeType, file_name = file['id'], file['mimeType'], file['name']
        if master_log:
                master_log.write(f"Analyzing {file_name}\n")
        media_birthday = fetch_bday_from_name(file_name, master_log)
        if media_birthday == "": 
            master_error_count += 1
            #error detected... 
            #file is skipped and not added to file map..
            if master_log:
                master_log.write(f"\tFILE {file_name} was skipped due to naming error.\n")
        else: #success detected
            files_map[file_id] = media_birthday
            if master_log:
                master_log.write(f"\tRESULTS => Id: {file_id} || Type: {fyle_mimeType} || Time taken: {files_map[file_id]}\n")
    if master_log:
        master_log.write(f"**SUMMARY**: \n\tTotal files parsed: {len(files)}\n\t\tSuccess count: {len(files_map)}\n\t\tSkip count: {master_error_count}\n")

def move_to_folder(file_id, new_parent_id, service):
    """Move a folder to a new parent folder."""
    try:
        # Retrieve the existing parents to remove
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        
        # Move the folder by updating the 'parents' property
        service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
    except Exception as e:
        print(f"Failed to move folder {file_id}: {e}")

def reconcile_media(service, games_list, master_log):
    """
    Method will compare media creation date with date intervals of games
    in order to detremine which files belong to which (games/curstomers)
    """
    date_format = "%Y-%m-%d %H:%M:%S"

    for game in games_list: #iterate through all the games
        game_folder_name = f"game_{game.get_id()}_media"
        #if master_log:
        #    master_log.write(f"Reconciling media for game {game.get_id()}\n")
        start_time = game.get_start_time()
        end_time = game.get_end_time()
        leeway = timedelta(minutes=2)
        start_dt = datetime.strptime(start_time, date_format)
        end_dt = datetime.strptime(end_time, date_format)
        start_dt_leeway = start_dt - leeway #allow media taken before game started by 3 min. 
        end_dt_leeway = end_dt + leeway #allow media taken after game ended by 3 min. 
        for file in files_map.keys():
            file_creation_date = files_map[file]
            file_creation_date_dt = datetime.strptime(file_creation_date, date_format)
            if start_dt_leeway <= file_creation_date_dt <= end_dt_leeway:
                if(len(game.associated_media) == 0): #this will be the first media in the folder, should create folder first. 
                    #create drive folder. 
                    game_folder_name = f"game_{game.get_id()}_media"
                    folder_metadata = {
                        'name': game_folder_name, 
                        'mimeType': 'application/vnd.google-apps.folder',
                    }
                    try:
                        parent_folder_prefix = game.get_start_time().split("-")[1]
                        # Retrieve the list of possible parent folders
                        parent_folders = get_all_files(service, master_log, PARENT_FOLDER_ID)  # Adjust the parent_id as needed
                        
                        # Find the matching parent folder
                        matching_parent_folder_id = None
                        for folder in parent_folders:
                            if folder['mimeType'] == 'application/vnd.google-apps.folder' and folder['name'].startswith(parent_folder_prefix):
                                matching_parent_folder_id = folder['id']
                                break
                        folder_metadata['parents'] = [matching_parent_folder_id] #correct the parent (1_jan_2024 etc...)
                        folder = service.files().create(body=folder_metadata, fields='id').execute()
                        folder_id = folder.get('id')
                        permission = {
                                'type': 'anyone',
                                'role': 'reader'
                            }
                        service.permissions().create(
                            fileId=folder_id,
                            body=permission,
                            fields='id'
                        ).execute() #share perms (anyone with link)

                        move_to_folder(file, folder_id, service)
                        link_to_folder = f"https://drive.google.com/drive/folders/{folder_id}"
                        game.set_game_media_folder_link(link_to_folder)
                        game.set_game_folder_id(folder_id)
                    except Exception as e:
                        if master_log:
                            master_log.write(f"ERROR creating new folder for media : {e}")
                else:
                    #move file to folder
                    move_to_folder(file, folder_id, service)
                game.associated_media.append(file)

def compare_player_list(player_list_1, player_list_2) -> bool:
    """
    Compare player list of 2 different games.
        -> True if player lists are identical.
        -> False if player lists differ.
    """
    fro_set_1 = frozenset(player_list_1) #dont care about order, just values. 
    fro_set_2 = frozenset(player_list_2) #dont care about order, just values. 

    return fro_set_1 == fro_set_2

def rename_folder(folder_id, new_name, service, master_log):
    try: 
        file_metadata = {
            'name': new_name,
        }
        updated_folder = service.files().update(
            fileId=folder_id,
            body=file_metadata,
            fields='id, name'
        ).execute()

        if master_log:
            master_log.write(f"Folder #{folder_id} was renamed to {updated_folder.get('name')}\n")
    except Exception as e:
        if master_log:
            master_log.write(f"Failed to rename Folder #{folder_id} due to: {e}\n")
        

def absorb(game_1, game_2, service, master_log) -> bool:
    """
    merge contens of game_2 folder to game_1 folder. 
    return True if successful
    return False if failed
    """
    try:
        moved_media = []    #for roll back
                            #trying an all or nothing approach here

        #game1 will absorb game2. 
        new_parent_id = game_1.get_game_folder_id()
        for media in game_2.get_associated_media():
            move_to_folder(media, new_parent_id, service)
            game_1.associated_media.append(media)

        game_2.set_absorbed_flag(True)
        #rename folder...
        new_name = f"ABSORBED_game{game_2.get_id()}_media"
        rename_folder(game_2.get_game_folder_id(), new_name, service, master_log)
        if master_log: 
            master_log.write(
                        f"Media for {game_2.get_id()} was absorbed into {game_1.get_id()}.\n"+
                        f"\t\t\tFolder {game_2.get_game_folder_id()} has been marked as absorbed.\n"
                    )
        return True #all media moved successfully :)
    
    except Exception as e:
        if master_log: 
            master_log.write(
                        f"Error: Failed to absorb game media: {e}\n"+
                        f"Roll back initiated.\n"
                    )
        for media in moved_media:
            try:
                #Move media back to the original location (game_2 folder)
                move_to_folder(media, game_2.get_game_folder_id(), service)
                game_1.associated_media.remove(media)
            except Exception as rollback_error:
                if master_log:
                    master_log.write(
                            f"Error during rollback: {rollback_error}\n"+
                            f"Please add media to {game_2.get_game_folder_id()} mannually.\n"
                        )
        return False #media moving failed :(

def absorb_algo(game_list, service, master_log):
    #iterate over all games
    for game_1 in game_list:
        if not game_1.absorbed_flag:
            player_email_list_1 = game_1.get_players_emails()
            for game_2 in game_list:
                if((game_2.get_id() != game_1.get_id()) and not game_2.absorbed_flag):
                    player_email_list_2 = game_2.get_players_emails()
                    if compare_player_list(player_email_list_1, player_email_list_2):
                        absorb_operation = absorb(game_1, game_2, service, master_log) #run absorption
                        if not absorb_operation: #if fail, then keep them seperate, no need to absortb
                            continue #check other games. 

def run_cross_check(games_list, log_file):
    master_log= log_file
    if master_log:
        master_log.write("--------------------CROSS CHECKER RUN INFORMATION--------------------\n\n")
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    analyze_files(service, master_log) #build files map
    if master_log:
        master_log.write("--------------------CROSS CHECKER RUN COMPLETE-----------------------\n\n")

    reconcile_media(service, games_list= games_list, master_log= master_log)
    if master_log:
        master_log.write("--------------------ABSORPTION RUN INFORMATION-----------------------\n\n")
    absorb_algo(games_list, service, master_log) 
    if master_log:
        for game in games_list:
            master_log.write(game.__str__())

    return files_map


