"""
Author: Anthony Nasr
Last modified: 2024-08-06
version 2.0
"""

#imports
import smtplib
import getpass
import re
import os
import portal_scraper
import json
import drive_file_parser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from googleapiclient.discovery import build
from google.oauth2 import service_account
from utils import *
from datetime import datetime
from portal_scraper import Game




#globals
context = {
    "google_maps_review_link": google_maps_review_link,
    "website_link": website_link,
    "facebook_link": facebook_link,
    "instagram_link": instagram_link,
    "tiktok_link": tiktok_link,
    "folder_link": "None"
}
#lock_duration_seconds = 120 #seconds
email_template = resource_path("email_template.html")
logo_path = resource_path("ZL_logo.png")

customers_to_email = {}


def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes= SCOPES)
    return creds

def is_folder_empty(service, folder_id):
    """Check if a folder is empty."""
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    return len(items) == 0

def get_all_files(service, parent_id= PARENT_FOLDER_ID):
    results = service.files().list(
        q= f"'{parent_id}' in parents",
        fields= "files(id, name, mimeType, parents)"
    ).execute()

def build_customer_list(service, parent_id= PARENT_FOLDER_ID):
    """Recursively list all files in the specified folder and its subfolders."""
    results = service.files().list(
        q=f"'{parent_id}' in parents",
        fields="files(id, name, mimeType, parents)"
    ).execute()
    
    items = results.get('files', [])
    all_files = []

    print(results)

    for item in items:
        # Add file details to the list
        all_files.append(item)
        # If the item is a folder, recurse into it
        if item['mimeType'] == 'application/vnd.google-apps.folder':
            if(not is_folder_empty(service, folder_id= item['id'])): #make sure folder contains some files to be sent in email.
                match = re.search(r'_(\S+@\S+\.\S+)', item['name']) #fetch email from name
                if match is not None:
                    customers_to_email[match.group(1)] = google_drve_folder_url_base+item['id']
    
def print_files(files):
    """Prints the names of all files."""
    for file in files:
        print(f"Name: {file['name']} - ID: {file['id']} - Type: {file['mimeType']}")

def move_folder(folder_id, new_parent_id, service):
    """Move a folder to a new parent folder."""
    try:
        # Retrieve the existing parents to remove
        file = service.files().get(fileId=folder_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        
        # Move the folder by updating the 'parents' property
        service.files().update(
            fileId=folder_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
    except Exception as e:
        print(f"Failed to move folder {folder_id}: {e}")

def check_if_preferences_setup():
    """
    Checks if a preference.json file exists. 
    If so, then it will use the existing login credentials saved in it. 
    If not, then it will prompt the user to enter a new set of credentials.
    """
    test= os.path.isfile("preferences.json")
    return test


def log_user_in(server):
    logged_in = False
    login_attempts = 3
    if check_if_preferences_setup():
        try:
            with open("preferences.json", "r") as file:
                data = json.load(file)
                email = data.get('email', None)
                password = data.get('password', None)
                server.login(email, password) #email log in goes here.
                logged_in = True
                print("-------LOGIN SUCCESSFUL-------")
                return email
        except Exception as e:
            print("Failed to extract login credentials from preference file. Delete it and run the program again.")
    else:
        while(not logged_in):
            try:
                email = input("Enter you email address: ").strip()
                password = getpass.getpass("Enter your password: ").strip()
                server.login(email, password) #email log in goes here.
                logged_in = True
                print("-------LOGIN SUCCESSFUL-------")
                valid_input = False
                while(not valid_input):
                    seeking_preferences = input("Would like to save login information? (y/n): ").strip()
                    match seeking_preferences:
                        case "y":
                            data = {
                                "email": email,
                                "password": password
                            }
                            with open('preferences.json', 'w') as f:
                                json.dump(data, f)
                            valid_input = True
                            return email
                        case "n":
                            valid_input = True
                            return email
                        case _ :
                            print("Invalid input.")
                            valid_input = False
            except Exception:
                login_attempts -= 1
                if(login_attempts == 0):
                    print("-------ERROR: LOGIN ATTEMPT FAILED. PLEASE RESTART THE PROGRAM.-------")
                    #time.sleep(lock_duration_seconds)
                    return #should maybe notify admin?
                elif(login_attempts != 0):
                    print(f"-------ERROR: LOGIN ATTEMPT {3-login_attempts} FAILED. You have {login_attempts} remaining.-------")
    

def send_email( games_list, master_log, subject = "Gameplay Footage"):
    server = smtplib.SMTP('smtp-mail.outlook.com', 587)
    server.starttls()
    try:
        email = log_user_in(server)
    except Exception as e:
        print("Failed to login user.")
        return
    for game in games_list:
        if not game.absorbed_flag and game.game_media_folder_link: #make sure it is not an absorbed game. and there is a link...
            #build email template:
            with open(email_template, "r") as file:
                html_template = file.read()
            context["folder_link"] = game.get_game_media_folder_link()
            html_content = html_template.format(**context)
            msg = MIMEMultipart("related")
            msg['From'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))
            with open(logo_path, "rb") as img_file:
                img = MIMEImage(img_file.read())
                img.add_header("Content-ID", "<logo>")
                msg.attach(img)
            for player_info in game.get_players():
                customer_email = player_info[1]
                #msg['To'] = customer_email
                msg['To'] = "anthonyjnasr29@gmail.com"
                message_body = msg.as_string()
                try:
                    response = server.sendmail(msg['From'], msg['To'], message_body)
                    #response = False
                    if not response:
                        if master_log:
                            master_log.write(f'Email Successfully sent to {customer_email} at {datetime.now().strftime("%d/%m/%Y || %I:%M %p")} \n')
                    else:
                        if master_log:
                            master_log.write(f'Failed to send email to {customer_email} \n\t -> ERROR :{response} at {datetime.now().strftime("%d/%m/%Y || %I:%M %p")}\n')

                except Exception as e:
                    if master_log:
                        master_log.write(f'Failed to send email to {customer_email} \n\t at {datetime.now().strftime("%d/%m/%Y || %I:%M %p")}\n')
    server.quit()

if __name__ == '__main__':
    date_today = datetime.today().strftime("%d%m%Y") #get today's date to run script on
    #date_today = "17082024"
    master_log = None
    current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_filename = os.path.join(log_dir, f"masterlog_{current_date}.txt")

    try:
        master_log = open(log_filename, "w")
    except Exception as e:
        print(f"Failed to open master log file: {e}")
    game_list = portal_scraper.run_scraper(date= date_today) #date format => DDMMYYYY
    #game_list = []
    #files_map = cross_checker.run_cross_check(game_list, master_log)
    #Log stuff :)
    if master_log:
        master_log.write("--------------------SCRAPER RUN INFORMATION--------------------\n")
        master_log.write(f"Game data extracted from {len(game_list)} games on {date_today[:2]}\{date_today[2:4]}\{date_today[4:]}\n")
    if not len(game_list):#no games found... 
        if master_log:
            master_log.write("No games found from web portal.\n")
    elif len(game_list): #games found...
        files_map = drive_file_parser.run_cross_check(game_list, master_log)
        #GOAL: Send one email to customers with more than one session (on a given day)

    #TODO: send the emails... 
    send_email(game_list, master_log)
    if master_log:
            master_log.close()
    print(f"RUN COMPLETE - Please view {log_filename} for run log.")