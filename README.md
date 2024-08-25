# 📧 ****ZL Game Media To Email System**** 🎮


## ****High level functional overview:****
![image](https://github.com/user-attachments/assets/2212d357-16c3-4d84-a3eb-db740c99bc7d)

## ****Prerequisites:****

### 1). Required folder setup in google drive: 
Within a parent folder (ex : ‘2024’) include smaller subfolders for each month of the year following the naming format: MONTH#_MONTHNAME_YEAR 
=> ex 1_January_2024
=> ex 2_February_2024
In addition, include an “Unprocessed content” (or whatever name you like) folder. 
This is where all files should be sent from Google photos. 

![image](https://github.com/user-attachments/assets/8ab4e82e-bb25-4d1f-accf-97a784e13323)

<p align="center">
  Figure 1: Main Drive structure
</p>


### 2). Incoming media naming scheme:
The script is built to recognize and parse media with the following naming schema:
				YYYYMMDD_HHMMSS.EXT
				Ex: 20240816_224815.mp4
Files not following this naming format will be skipped during parsing.
 

### 3). Installation & Setup:

	1 - Open command shell in a secure location
 
	2 - Clone repo locally: 
      -> git clone https://github.com/nasrAnthony/Game-media-automation-system.git
        
	3 - Ensure python and pip are installed. 
		  -> If not then refer to this: https://pip.pypa.io/en/stable/installation/

	4 - Install dependencies
		  -> pip install -r requirements.txt

	5 - Contact anthonyjnasr29@gmail.com for API access and required credentials. 

### 4). How to run:

	  1 - Run sendemail.py
		    -> python sendemail.py
      
	  2 - Log in with appropriate outlook email credentials. 
   
      3 - Review log output, emails sent, and drive folder content to ensure results are correct.
