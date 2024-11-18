#!/usr/bin/python3

import sqlite3
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# API URL from environment variables
API_URL = os.getenv("API_URL")

# Connect to the database
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to fetch data from the API
def fetch_api_data():
    response = requests.get(API_URL)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from API. Status Code: {response.status_code}")
        return []

# Function to update the Employees table
def update_employees_table(data):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all existing employee emails from the database
    cursor.execute("SELECT email FROM employees")
    db_emails = {row["email"] for row in cursor.fetchall()}

    # Collect emails and employee details from the API
    api_emails = set()
    api_employees = []

    for employee in data:
        acf = employee.get('acf', {})
        if acf.get('av_inventory') is True:
            name = acf.get('staff_name')
            email = acf.get('email_address')

            if name and email:
                api_emails.add(email)
                api_employees.append({"name": name, "email": email})

    # Deactivate employees no longer in the API
    to_deactivate = db_emails - api_emails
    for email in to_deactivate:
        cursor.execute(
            "UPDATE employees SET active = 0 WHERE email = ?",
            (email,)
        )
        print(f"Deactivated employee: {email}")

    # Add or reactivate employees from the API
    for employee in api_employees:
        cursor.execute(
            "SELECT * FROM employees WHERE email = ?",
            (employee['email'],)
        )
        existing_employee = cursor.fetchone()

        if existing_employee:
            if not existing_employee["active"]:  # Reactivate if previously deactivated
                cursor.execute(
                    "UPDATE employees SET active = 1 WHERE email = ?",
                    (employee['email'],)
                )
                print(f"Reactivated employee: {employee['name']} ({employee['email']})")
        else:
            # Add new employee to the database
            cursor.execute(
                "INSERT INTO employees (name, email, active) VALUES (?, ?, 1)",
                (employee['name'], employee['email'])
            )
            print(f"Added new employee: {employee['name']} ({employee['email']})")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Fetch data from the API
    api_data = fetch_api_data()

    # Update the employees table
    update_employees_table(api_data)

    print("Employee table update complete.")
