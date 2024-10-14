import sqlite3
import subprocess
import evdev
import time
from flask import Flask, render_template, redirect, url_for
import threading

# Initialize Flask app
app = Flask(__name__)

# Function to check if the inventory table exists, and run setup_database.py if not
def initialize_database():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Check if the 'inventory' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory';")
    table_exists = cursor.fetchone()

    if table_exists is None:
        print("Table 'inventory' does not exist. Running setup_database.py...")
        
        # Run the setup_database.py script
        try:
            subprocess.run(['python3', 'setup_database.py'], check=True)
            print("setup_database.py executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error running setup_database.py: {e}")
    else:
        print("Table 'inventory' already exists.")

    conn.close()

# Initialize the database
initialize_database()

# Connect to SQLite database globally
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to toggle the item state between 'in' and 'out'
def toggle_item_state(barcode):
    try:
        print(f"Toggling item state for barcode: {barcode}")  # Debugging output
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the item exists in the database
        cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()
        print(f"Database lookup for barcode {barcode}: {row}")  # Debugging output

        if row is None:
            # If the item is not in the database, mark it as 'in'
            status = 'in'
            cursor.execute("INSERT INTO inventory (barcode, status) VALUES (?, ?)", (barcode, status))
            print(f"Inserted barcode {barcode} with status {status}.")  # Debugging output
        else:
            # If the item exists, toggle its status
            current_status = row[0]
            new_status = 'out' if current_status == 'in' else 'in'
            cursor.execute("UPDATE inventory SET status = ? WHERE barcode = ?", (new_status, barcode))
            print(f"Updated barcode {barcode} to new status {new_status}.")  # Debugging output

        conn.commit()
    except Exception as e:
        print(f"Error toggling item state for barcode {barcode}: {e}")  # Catch and print any errors
    finally:
        conn.close()  # Ensure connection is closed after operations

# Function to process barcode scan
def process_barcode(scanner):
    barcode = ''
    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]
                if key == 'KEY_ENTER':
                    print(f"Barcode scanned: {barcode}")  # Debugging output
                    toggle_item_state(barcode)  # Process the scanned barcode
                    barcode = ''  # Reset for the next scan
                else:
                    barcode += key[-1]  # Add the last character of the key name

# Flask route to display inventory
@app.route('/')
def inventory():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    return render_template('inventory.html', items=items)

# Flask route to toggle item status via a web interface
@app.route('/toggle/<barcode>')
def toggle(barcode):
    toggle_item_state(barcode)
    return redirect(url_for('inventory'))

# Main execution flow
if __name__ == "__main__":
    # Detect barcode scanner
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    scanner = None

    # Assign the first device found (adjust if needed)
    for device in devices:
        print(f"Device found: {device.path} {device.name}")
        scanner = evdev.InputDevice(device.path)
        break  # Use the first scanner found

    if not scanner:
        raise Exception("No barcode scanner found!")

    # Start the barcode processing in a separate thread
    threading.Thread(target=process_barcode, args=(scanner,), daemon=True).start()
    
    # Start Flask app
    print("Ready to scan items...")
    app.run(host='0.0.0.0', port=5000)
