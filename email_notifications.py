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
def send_notification(barcode, expected_return_date):
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": MAILGUN_FROM_EMAIL,
            "to": MAILGUN_TO_EMAIL,
            "subject": f"Item {barcode} is still checked out!",
            "text": f"Item with barcode {barcode} was expected to be returned on {expected_return_date}, but is still checked out."
        }
    )
# Example usage for testing
def test_send_email():
    subject = "Test Email from Raspberry Pi"
    message = "This is a test email to check the email notification system."
    response = send_notification(subject, message)
    print(response.status_code)
    print(response.text)