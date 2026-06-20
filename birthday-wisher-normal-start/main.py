"""
Birthday Mailer Script.
Automatically checks for birthdays matching today's date in a CSV file,
generates a personalized email message using dynamic templates, static fallbacks,
or a generative AI service, and sends them out over a single SMTP connection.
"""

import datetime as dt
import logging
import os
import random
import re
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv

# Regular expression for simple email validation
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def setup_logging() -> None:
    """Configures structured stdout logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )


def load_birthdays(file_path: Path) -> pd.DataFrame:
    """
    Loads birthdays from a CSV file.

    Args:
        file_path (Path): Path to the CSV file.

    Returns:
        pd.DataFrame: Loaded birthday records, or an empty DataFrame on failure.
    """
    try:
        logging.info(f"Loading birthday list from {file_path}")
        df = pd.read_csv(file_path, encoding="utf-8")
        # Normalize column names by stripping whitespace
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        logging.error(f"Birthday list file not found at {file_path}")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"Error reading birthday list CSV file: {e}")
        return pd.DataFrame()


def validate_birthday_row(row_idx: int, name: str, email: str, month: int, day: int) -> bool:
    """
    Validates fields of a single birthday record.

    Args:
        row_idx (int): The index of the row in the CSV (for logging).
        name (str): Person's name.
        email (str): Person's email.
        month (int): Birth month.
        day (int): Birth day.

    Returns:
        bool: True if the row is valid, False otherwise.
    """
    # Check for empty name
    if not name or not isinstance(name, str) or not name.strip():
        logging.warning(f"Row {row_idx}: Name is empty or invalid. Skipping.")
        return False

    # Check for empty email
    if not email or not isinstance(email, str) or not email.strip():
        logging.warning(f"Row {row_idx} ({name}): Email is empty. Skipping.")
        return False

    # Validate email format
    if not EMAIL_REGEX.match(email.strip()):
        logging.warning(f"Row {row_idx} ({name}): Invalid email format '{email}'. Skipping.")
        return False

    # Validate month range
    try:
        month_val = int(month)
        if not (1 <= month_val <= 12):
            logging.warning(f"Row {row_idx} ({name}): Month {month_val} is out of range 1-12. Skipping.")
            return False
    except (ValueError, TypeError):
        logging.warning(f"Row {row_idx} ({name}): Month '{month}' is not an integer. Skipping.")
        return False

    # Validate day range for the given month
    try:
        day_val = int(day)
        # Using a leap year (2000) to allow February 29th
        dt.date(2000, month_val, day_val)
    except (ValueError, TypeError):
        logging.warning(f"Row {row_idx} ({name}): Day '{day}' is not valid for month {month_val}. Skipping.")
        return False

    return True


def get_today_birthdays(df: pd.DataFrame, today_month: int, today_day: int) -> list[dict]:
    """
    Filters and validates today's birthdays.

    Args:
        df (pd.DataFrame): Birthday DataFrame.
        today_month (int): Target month.
        today_day (int): Target day.

    Returns:
        list[dict]: A list of validated birthday records.
    """
    if df.empty:
        return []

    # Using direct pandas filtering instead of a dictionary format.
    # A dictionary lookup mapping (month, day) -> row causes data loss when multiple
    # entries share the same birthday, as later rows overwrite earlier ones.
    # By filtering the DataFrame directly, we fetch every matching row on that date.
    matching_rows = df[(df["month"] == today_month) & (df["day"] == today_day)]
    today_list = []

    for idx, row in matching_rows.iterrows():
        # Extracted variables
        name = row.get("naam")
        email = row.get("email")
        month = row.get("month")
        day = row.get("day")

        # Clean/convert values
        name_str = str(name).strip() if pd.notna(name) else ""
        email_str = str(email).strip() if pd.notna(email) else ""

        if validate_birthday_row(idx + 2, name_str, email_str, month, day):
            today_list.append({
                "naam": name_str,
                "email": email_str
            })

    return today_list


class TemplateProvider:
    """Handles loading static files, generating dynamic text, or calling AI template services."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.default_template = (
            "Dear [NAME],\n\n"
            "Happy Birthday! Wishing you a wonderful day filled with joy and happiness.\n\n"
            "Best wishes,\n"
            "Ramanan Dhakkshinamoorthy"
        )
        self.styles = {
            "friendly": {
                "greetings": ["Dear [NAME],", "Hey [NAME]!", "Hi [NAME],", "Dearest [NAME],"],
                "wishes": [
                    "Happy birthday! Hope you have a fantastic day filled with joy and lots of cake!",
                    "Wishing you a wonderful day and a year ahead filled with happiness and laughter!",
                    "Have a great birthday! Cheers to another amazing year of life!",
                    "May your birthday be as special and wonderful as you are!"
                ],
                "closings": ["Warmly,", "Best wishes,", "Lots of love,", "Cheers,"]
            },
            "professional": {
                "greetings": ["Dear [NAME],", "Hello [NAME],", "Warm greetings [NAME],"],
                "wishes": [
                    "Wishing you a very happy birthday and continued success in all your professional and personal endeavors.",
                    "May this special day bring you joy, and may the coming year bring you prosperity and success.",
                    "Wishing you a wonderful birthday celebration. Have a great day and a successful year ahead!"
                ],
                "closings": ["Warm regards,", "Best regards,", "Sincerely,"]
            },
            "humorous": {
                "greetings": ["Aha [NAME]!", "Look who is a year older [NAME]!", "Hey [NAME],"],
                "wishes": [
                    "Happy birthday! Don't count the candles, just enjoy the cake (and the fact that you still have teeth to eat it)!",
                    "Another birthday? You don't look a day older than your profile picture from 5 years ago! Have a blast!",
                    "Happy birthday! Statistics show that people who have more birthdays live longer. Enjoy your day!",
                    "Congratulations on surviving another year! Have an awesome birthday!"
                ],
                "closings": ["Your favorite bot,", "Sent from a server somewhere,", "Cheers,"]
            },
            "inspirational": {
                "greetings": ["Dear [NAME],", "Warmest greetings [NAME],", "Hello [NAME],"],
                "wishes": [
                    "May this year be a breakthrough year for you, full of growth, discovery, and exciting new opportunities.",
                    "On your birthday, remember that you have the power to achieve anything you set your mind to. Keep shining!",
                    "Wishing you a year of self-discovery, joy, and the courage to pursue your biggest dreams. Happy birthday!"
                ],
                "closings": ["With warm inspiration,", "Keep shining,", "Best wishes,"]
            }
        }

    def get_static_template(self, name: str) -> tuple[str, str]:
        """Tries to load a local letter template randomly, falls back to default if files are missing."""
        try:
            letter_idx = random.randint(1, 3)
            template_file = self.templates_dir / f"letter_{letter_idx}.txt"
            if template_file.exists():
                with open(template_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content.replace("[NAME]", name), f"static file ({template_file.name})"
            else:
                logging.warning(f"Static template {template_file.name} not found. Falling back to default.")
        except Exception as e:
            logging.error(f"Error loading static template: {e}. Falling back to default.")
        
        return self.default_template.replace("[NAME]", name), "fallback (default template)"

    def generate_dynamic_template(self, name: str) -> tuple[str, str]:
        """Generates a dynamic personalized message randomly choosing a style."""
        style = random.choice(list(self.styles.keys()))
        style_data = self.styles[style]
        
        greeting = random.choice(style_data["greetings"]).replace("[NAME]", name)
        wish = random.choice(style_data["wishes"])
        closing = random.choice(style_data["closings"])
        
        message = f"{greeting}\n\n{wish}\n\n{closing}\n\nRamanan Dhakkshinamoorthy"
        return message, f"dynamic generator ({style} style)"

    def get_api_template(self, name: str) -> tuple[str, str]:
        """Calls a free public API to fetch a random piece of advice/quote, falls back to dynamic."""
        try:
            response = requests.get("https://api.adviceslip.com/advice", timeout=5)
            if response.status_code == 200:
                data = response.json()
                advice = data.get("slip", {}).get("advice", "")
                if advice:
                    message = (
                        f"Dear {name},\n\n"
                        f"Happy Birthday! Today, on your special day, here is a little piece of advice:\n"
                        f"\"{advice}\"\n\n"
                        f"Have an amazing day and a wonderful year ahead!\n\n"
                        f"Warm regards,\n"
                        f"Ramanan Dhakkshinamoorthy"
                    )
                    return message, "free API (Advice Slip)"
        except Exception as e:
            logging.warning(f"Failed to fetch template from free API: {e}. Falling back to dynamic.")
        
        return self.generate_dynamic_template(name)

    def get_ai_template(self, name: str) -> tuple[str, str]:
        """Calls Gemini Generative AI API to write a unique message if configured, falls back to static."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.info("GEMINI_API_KEY not configured. Falling back to static templates.")
            return self.get_static_template(name)
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            prompt = (
                f"Write a warm, concise, and friendly happy birthday message for {name}. "
                "The message must be suitable for an email, short, positive, and end with the sender "
                "'Ramanan Dhakkshinamoorthy'. Only return the final email body text, no extra explanation."
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }
            response = requests.post(url, headers=headers, json=payload, timeout=8)
            if response.status_code == 200:
                resp_json = response.json()
                text = resp_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text:
                    return text, "Gemini Generative AI API"
                else:
                    logging.warning("Received empty text from Gemini API. Falling back to static.")
            else:
                logging.warning(f"Gemini API returned status code {response.status_code}. Falling back to static.")
        except Exception as e:
            logging.warning(f"Error calling Gemini API: {e}. Falling back to static.")
            
        return self.get_static_template(name)

    def get_template(self, name: str, source: str = "dynamic") -> tuple[str, str]:
        """Main interface to fetch templates based on configuration, with cascading fallbacks."""
        source = source.lower()
        if source == "static":
            return self.get_static_template(name)
        elif source == "api":
            return self.get_api_template(name)
        elif source == "ai":
            return self.get_ai_template(name)
        else:
            return self.generate_dynamic_template(name)


def create_smtp_connection(sender_email: str, sender_password: str) -> smtplib.SMTP:
    """
    Creates and logs into GMail SMTP server.

    Args:
        sender_email (str): The login email.
        sender_password (str): The Gmail App Password.

    Returns:
        smtplib.SMTP: Connected and authenticated SMTP connection object.
    """
    logging.info("Connecting to GMail SMTP server...")
    connection = smtplib.SMTP("smtp.gmail.com", port=587)
    try:
        connection.starttls()
        connection.login(user=sender_email, password=sender_password)
        logging.info("SMTP login successful.")
        return connection
    except Exception as e:
        # Close connection if login fails to clean up socket
        try:
            connection.quit()
        except Exception:
            pass
        raise e


def send_birthday_email(
    connection: smtplib.SMTP,
    sender_email: str,
    recipient_name: str,
    recipient_email: str,
    body: str
) -> bool:
    """
    Sends birthday email to a single recipient over an open SMTP connection.

    Args:
        connection (smtplib.SMTP): Active SMTP connection.
        sender_email (str): Sender address.
        recipient_name (str): Recipient name.
        recipient_email (str): Recipient email.
        body (str): Email message body.

    Returns:
        bool: True if email sent successfully, False otherwise.
    """
    try:
        logging.info(f"Preparing email for {recipient_name} ({recipient_email})...")
        
        # Construct RFC2822 email message to avoid spam filter flags and ensure proper headers
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = Header(f"Happy Birthday {recipient_name}!", "utf-8")
        msg.attach(MIMEText(body, "plain", "utf-8"))

        connection.sendmail(
            from_addr=sender_email,
            to_addrs=recipient_email,
            msg=msg.as_string()
        )
        logging.info(f"Email successfully sent to {recipient_name} ({recipient_email}).")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {recipient_name} ({recipient_email}): {e}")
        return False


def send_notification_email(
    connection: smtplib.SMTP,
    sender_email: str,
    recipient_email: str,
    names: list[str]
) -> bool:
    """
    Sends a combined notification email with a list of today's birthdays.
    """
    try:
        logging.info(f"Preparing notification email for {recipient_email}...")
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        names_str = ", ".join(names)
        msg["Subject"] = Header(f"Hey, it's {names_str}'s birthday! Wish them now", "utf-8")
        
        body = f"Hey,\n\nIt's {names_str}'s birthday today! The wisher bot has successfully sent them their birthday greetings.\n\nDon't forget to wish them!\n\nBest,\nYour Birthday Bot"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        connection.sendmail(
            from_addr=sender_email,
            to_addrs=recipient_email,
            msg=msg.as_string()
        )
        logging.info("Notification email successfully sent.")
        return True
    except Exception as e:
        logging.error(f"Failed to send notification email: {e}")
        return False


def main() -> None:
    """Main execution function."""
    setup_logging()
    
    # Load environment variables (from local .env file if it exists)
    load_dotenv()
    
    # Securely retrieve credentials from environment variables
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    
    if not email:
        raise ValueError("Environment variable 'EMAIL' is not set.")
    if not password:
        raise ValueError("Environment variable 'PASSWORD' is not set.")
    
    # Determine the template source (default is 'dynamic')
    template_source = os.getenv("TEMPLATE_SOURCE", "dynamic")
    
    # Define directories relative to this file
    script_dir = Path(__file__).parent
    birthdays_path = script_dir / "birthdays.csv"
    letter_templates_dir = script_dir / "letter_templates"
    
    # Load birthday entries
    df = load_birthdays(birthdays_path)
    if df.empty:
        logging.error("No birthday data loaded. Terminating script.")
        return

    # Calculate current date in India Standard Time (IST)
    ist = pytz.timezone("Asia/Kolkata")
    today = dt.datetime.now(ist)
    today_month = today.month
    today_date = today.day
    
    logging.info(f"Checking birthdays for date: Month={today_month}, Day={today_date} (IST)")
    
    # Filter and validate entries
    today_birthdays = get_today_birthdays(df, today_month, today_date)
    
    if not today_birthdays:
        logging.info("No birthdays to wish today. Exiting.")
        return
        
    logging.info(f"Found {len(today_birthdays)} validated birthday(s) to process.")
    
    template_provider = TemplateProvider(letter_templates_dir)
    
    # Establish single SMTP connection for all emails
    try:
        with create_smtp_connection(email, password) as connection:
            success_count = 0
            wished_names = []
            for person in today_birthdays:
                name = person["naam"]
                mail = person["email"]
                
                # Fetch/generate message
                message, src_name = template_provider.get_template(name, template_source)
                logging.info(f"Using template source: {src_name}")
                
                # Send email
                if send_birthday_email(connection, email, name, mail, message):
                    success_count += 1
                    wished_names.append(name)
            
            # Send notification to ramanan2735@gmail.com
            if wished_names:
                send_notification_email(connection, email, "ramanan2735@gmail.com", wished_names)
            
            logging.info(f"Execution complete. Successfully sent {success_count}/{len(today_birthdays)} emails.")
    except Exception as e:
        logging.error(f"SMTP session failure: {e}")


if __name__ == "__main__":
    main()
