import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL")
MAILGUN_TO_EMAIL = os.getenv("MAILGUN_TO_EMAIL")

# Function to send email
def send_notification(barcode, expected_return_date, to_email):
    response = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": MAILGUN_FROM_EMAIL,
            "to": to_email,
            "subject": f"Item {barcode} is still checked out!",
            "text": f"Item with barcode {barcode} was expected to be returned on {expected_return_date}, but is still checked out."
        }
    )

    # Debugging output
    if response.status_code == 200:
        print(f"Email sent successfully for item {barcode} to {to_email}!")
    else:
        print(f"Failed to send email for item {barcode} to {to_email}. Status code: {response.status_code}, Response: {response.text}")

    return response