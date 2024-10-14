import sqlite3
import subprocess
import evdev
import time


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

# Connect to SQLite database
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

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

# Function to process barcode scan
def process_barcode():
    barcode = ''
    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]
                if key == 'KEY_ENTER':
                    print(f"Barcode scanned: {barcode}")
                    toggle_item_state(barcode)
                    barcode = ''  # Reset barcode for next scan
                else:
                    barcode += key[-1]  # Add the last character of the key name

# Function to toggle the item state between 'in' and 'out'
def toggle_item_state(barcode):
    cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
    row = cursor.fetchone()
    
    if row is None:
        # If the item is not in the database, mark it as 'in'
        status = 'in'
        cursor.execute("INSERT INTO inventory (barcode, status) VALUES (?, ?)", (barcode, status))
        print(f"Item with barcode {barcode} is marked as {status}.")
    else:
        # If the item exists, toggle its status
        current_status = row[0]
        new_status = 'out' if current_status == 'in' else 'in'
        cursor.execute("UPDATE inventory SET status = ?, timestamp = CURRENT_TIMESTAMP WHERE barcode = ?", (new_status, barcode))
        print(f"Item with barcode {barcode} is now marked as {new_status}.")

    conn.commit()

# Main loop to process barcodes
try:
    print("Ready to scan items...")
    process_barcode()

except KeyboardInterrupt:
    print("Exiting program...")

finally:
    # Cleanup
    conn.close()
