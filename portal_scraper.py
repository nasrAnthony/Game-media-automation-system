import time
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime
from utils import (
        base_url,
        credentials_email, 
        credentials_password
)

class Game():
    def __init__(self, id, players, start_time, end_time):
        self.game_id = id
        self.game_folder_id = None
        self.players = players
        self.start_time = start_time
        self.end_time = end_time
        self.associated_media = []
        self.game_media_folder_link = None 
        self.absorbed_flag = False #set to true if game was absorbed by another game obj

    #getters
    def get_id(self) -> str:
        return self.game_id
    
    def get_players(self) -> list:
        return self.players
    
    def get_associated_media(self) -> list:
        return self.associated_media
    
    def get_players_emails(self) -> list:
        return [player[1] for player in self.players]
    
    def get_game_id(self) -> str:
        return self.game_id
    
    def get_game_folder_id(self) -> str:
        return self.game_folder_id
    
    def get_start_time(self) -> str:
        return self.start_time
    
    def get_end_time(self) -> str:
        return self.end_time
    
    def get_game_media_folder_link(self) -> str:
        return self.game_media_folder_link
    
    def set_game_media_folder_link(self, new_link) -> None:
        self.game_media_folder_link = new_link

    def set_game_folder_id(self, new_folder_id) -> None:
        self.game_folder_id = new_folder_id

    def set_absorbed_flag(self, new_flag) -> None:
        self.absorbed_flag = new_flag
    
    #for logging
    def __str__(self, verbose= False):
        total_player_count = len(self.players)
        player_list_string , media_list_string= "", ""
        player_count = 0 
        media_count = 0
        for player in self.players:
            player_count += 1
            player_list_string += f"\t\t#{player_count} name: {player[0]} || email: {player[1]}\n"
        for media in self.associated_media:
            media_count += 1
            media_list_string += f"\t\t#{media_count} file id: {media}\n"
        if media_list_string == "":
            media_list_string = "\t\tNo media was associated to this game.\n"
        description = (
                        f"Game #{self.game_id} :\n"+
                        f"\t Start time   : {self.start_time}\n"+
                        f"\t End time     : {self.end_time}\n"+
                        f"\t Players ({total_player_count}):\n"+ 
                        player_list_string+
                        f"\tAbsorbed Flag: {self.absorbed_flag}\n"+
                        f"\t Game media ({media_count}):\n"+
                        media_list_string+
                        f"\t Game folder link: {self.game_media_folder_link}\n"
                    )
        if verbose:
            print(description)
        return description

def standardize_date(raw_date, type) -> str:
    """
    input format: DD MMM YYYY - HH:MM PM/AM
                EX: 11 Aug 2024 - 7:53 PM
    output format:   YYYY-MM-DD HH:MM:00 
    """
    types = {
        "start": "00", #second suffix start is min
        "end": "59", #second suffic end is max
    }
    input_format  = "%d %b %Y - %I:%M %p"
    output_format = "%Y-%m-%d %H:%M:%S"
    date_object   = datetime.strptime(raw_date, input_format)
    try: 
        formatted_date = date_object.strftime(output_format)
        formatted_date = formatted_date[:17] + types.get(type) #buffer
        return formatted_date
    except Exception as e:
        print(f"Failed to format date {raw_date} due to {e}\n")
        return ""

def extract_start_end_times(driver):
    form_rows = driver.find_elements(By.CLASS_NAME, "form-row")
    for row in form_rows:
        label = row.find_element(By.CLASS_NAME, "form-label-sec").text.strip()
        if("Start Time" in label):
            raw_start_date = row.find_element(By.CLASS_NAME, "form-input-sec").text.strip()
            start_time = standardize_date(raw_date= raw_start_date, type= "start")
        if("End Time" in label):
            raw_end_time = row.find_element(By.CLASS_NAME, "form-input-sec").text.strip()
            end_time = standardize_date(raw_date= raw_end_time, type= "end")
    return start_time, end_time

def build_game_player_list(driver, start_time, end_time, id):
    player_elements = driver.find_elements(By.XPATH, "//tbody//a[contains(@href, '/player/')]")

    #Extract the href attributes and the player names
    players_info = set([(element.get_attribute('href'), element.text) for element in player_elements])

    #Print out the hrefs and player names
    game_key = f"{id}"
    player_list = [] #(playername, playeremail, linktoprofile)
    player_emails = []  #emails (for comparison)

    for href, name in players_info:
        driver.get(href) #go to player profile page
        email_temp = driver.find_element(By.ID, "Email")
        player_email = email_temp.get_attribute("value")
        player_list.append((name, player_email, href))

    return Game(game_key, player_list, start_time, end_time )


def run_scraper(date, verbose= True):
    parser = argparse.ArgumentParser(description="Web scraper to fetch and format data to be used for automation purposes.")
    parser.add_argument("--verbose", action="store_true", help = "Increase output verbosity")
    args = parser.parse_args()

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--log-level=3')
    web_driver = webdriver.Chrome(options=options)
    web_driver.get(base_url + "login?r=%2F")

    email_input = web_driver.find_element(By.NAME, "Email")
    password_input = web_driver.find_element(By.NAME, "Password")
    email_input.send_keys(credentials_email)
    password_input.send_keys(credentials_password)
    web_driver.find_element(By.ID, "LoginButton").click()
    web_driver.implicitly_wait(5) #seconds

    web_driver.get(base_url + "game-results")

    date_picker_display = web_driver.find_element(By.CSS_SELECTOR, ".display-value-container")
    date_picker_display.click()
    date_picker_input = web_driver.find_element(By.ID, "Range")
    desired_date = web_driver.find_element(By.CSS_SELECTOR, f"td[data-day='{date}']") # Replace with the correct data-day attribute
    time.sleep(3)
    desired_date.click()
    time.sleep(3)

    data_ids = web_driver.find_elements(By.CSS_SELECTOR, "[data-id]")

    game_ids = [data_ids[i].get_attribute("data-id") for i in range(len(data_ids))]
    game_list = []
    for game_id in game_ids[1:]:
        if args.verbose:
            print(base_url + f"game-result/{game_id}")
        web_driver.get(base_url + f"game-result/{game_id}")
        time.sleep(3)
        game_start_time_value, game_end_time_value = extract_start_end_times(web_driver)
        game = build_game_player_list(web_driver, game_start_time_value, game_end_time_value, game_id)
        game_list.append(game)

    web_driver.quit()
    return game_list

#if __name__ == "__main__":
    #total_game_list = run_scraper()





