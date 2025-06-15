##################### Normal Starting Project ######################

# 1. Update the birthdays.csv with your friends & family's details. 
# HINT: Make sure one of the entries matches today's date for testing purposes. e.g.
#name,email,year,month,day
#YourName,your_own@email.com,today_year,today_month,today_day

# 2. Check if today matches a birthday in the birthdays.csv
# HINT 1: Create a tuple from today's month and day using datetime. e.g.
# today = (today_month, today_day)

# HINT 2: Use pandas to read the birthdays.csv

# HINT 3: Use dictionary comprehension to create a dictionary from birthday.csv that is formated like this:
# birthdays_dict = {
#     (birthday_month, birthday_day): data_row
# }
#Dictionary comprehension template for pandas DataFrame looks like this:
# new_dict = {new_key: new_value for (index, data_row) in data.iterrows()}
#e.g. if the birthdays.csv looked like this:
# name,email,year,month,day
# Angela,angela@email.com,1995,12,24
#Then the birthdays_dict should look like this:
# birthdays_dict = {
#     (12, 24): Angela,angela@email.com,1995,12,24
# }

#HINT 4: Then you could compare and see if today's month/day tuple matches one of the keys in birthday_dict like this:
# if (today_month, today_day) in birthdays_dict:

# 3. If there is a match, pick a random letter (letter_1.txt/letter_2.txt/letter_3.txt) from letter_templates and replace the [NAME] with the person's actual name from birthdays.csv
# HINT 1: Think about the relative file path to open each letter. 
# HINT 2: Use the random module to get a number between 1-3 to pick a randome letter.
# HINT 3: Use the replace() method to replace [NAME] with the actual name. https://www.w3schools.com/python/ref_string_replace.asp

# 4. Send the letter generated in step 3 to that person's email address.
# HINT 1: Gmail(smtp.gmail.com), Yahoo(smtp.mail.yahoo.com), Hotmail(smtp.live.com), Outlook(smtp-mail.outlook.com)
# HINT 2: Remember to call .starttls()
# HINT 3: Remember to login to your email service with email/password. Make sure your security setting is set to allow less secure apps.
# HINT 4: The message should have the Subject: Happy Birthday then after \n\n The Message Body.



import datetime  as dt
import pandas as pd
import smtplib
import random
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()



def sendBirthdayMail():
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    print(password)
    with smtplib.SMTP("smtp.gmail.com",port=587) as connection:
        connection.starttls()
        connection.login(user="ramanansbirthdaybot@gmail.com" ,password="ztny xqhd akwc igpm")
        connection.sendmail(from_addr="ramanansbirthdaybot@gmail.com", to_addrs=recipient_mail,msg=f"Subject:Happy Birthday {recipient_name}\n\n{new_letter}")



today = dt.datetime.now()
today_date = today.day
today_month = today.month

# Get the directory where the script is located
script_dir = Path(__file__).parent

# Use this for all file paths
birthdays_path = script_dir / "birthdays.csv"
letter_templates_dir = script_dir / "letter_templates"

all_birthdays = pd.read_csv(birthdays_path)
birthday_dict = {
    (row.month, row.day): (row.naam,row.email,row.year,row.month,row.day)
    for index, row in all_birthdays.iterrows()
}

for (i,v) in birthday_dict.items():
    if i[0] == today_month and i[1] == today_date:        
        with open(f"{letter_templates_dir}/letter_{random.randint(1,3)}.txt") as letter:
            letter_contents = letter.read()
            new_letter = letter_contents.replace("[NAME]",f"{v[0]}")
            recipient_name = v[0]
            recipient_mail = v[1]
        sendBirthdayMail()