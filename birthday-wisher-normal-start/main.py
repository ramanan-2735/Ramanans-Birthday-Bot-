import datetime as dt
import pandas as pd
import smtplib
import random
import os
from pathlib import Path
import pytz

MY_EMAIL = "ramanansbirthdaybot@gmail.com"
MY_PASSWORD = "ztnyxqhdakwcigpm"

def sendBirthdayMail(recipient_name, recipient_mail, new_letter):
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(user=MY_EMAIL, password=MY_PASSWORD)
        connection.sendmail(
            from_addr=MY_EMAIL,
            to_addrs=recipient_mail,
            msg=f"Subject:Happy Birthday {recipient_name}\n\n{new_letter}"
        )

ist = pytz.timezone("Asia/Kolkata")
today = dt.datetime.now(ist)
today_date = today.day
today_month = today.month

script_dir = Path(__file__).parent
birthdays_path = script_dir / "birthdays.csv"
letter_templates_dir = script_dir / "letter_templates"

all_birthdays = pd.read_csv(birthdays_path)
birthday_dict = {
    (row.month, row.day): (row.naam, row.email)
    for _, row in all_birthdays.iterrows()
}

for (month, day), (name, email) in birthday_dict.items():
    if month == today_month and day == today_date:
        with open(letter_templates_dir / f"letter_{random.randint(1,3)}.txt") as letter:
            letter_contents = letter.read()
            new_letter = letter_contents.replace("[NAME]", name)
        sendBirthdayMail(name, email, new_letter)
