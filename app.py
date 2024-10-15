import sqlite3
import subprocess
import evdev
import time
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import threading

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Function to check if the inventory table exists
def initialize_database():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory';")
    table_exists = cursor.fetchone()
    if table_exists is None:
        print("Table 'inventory' does not exist. Running setup_database.py...")
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

# Function to get all inventory data
def get_inventory_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all inventory data and latest checkout information
    items = cursor.execute('''
        SELECT i.barcode, i.status, l.checked_out_by, l.timestamp AS checkout_timestamp
        FROM inventory i
        LEFT JOIN checkout_log l ON i.barcode = l.barcode
        ORDER BY l.timestamp DESC
    ''').fetchall()

    inventory = []
    for item in items:
        inventory.append({
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'],
            'checkout_timestamp': item['checkout_timestamp']
        })

    conn.close()
    return {'items': inventory}

# Function to process barcode scan
def process_barcode(scanner):
    barcode = ''
    print("DEBUG: Starting barcode processing...")

    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]
                
                # When 'Enter' key is detected, barcode is complete
                if key == 'KEY_ENTER':
                    print(f"DEBUG: Barcode scanned: {barcode}")
                    socketio.emit('barcode_scanned', {'barcode': barcode})
                    barcode = ''  # Reset for the next scan
                else:
                    # Add key to barcode string
                    barcode += key[-1]

# Function to toggle item state
def toggle_item_state(barcode, checked_out_by=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()

        if row is None:
            status = 'in'
            cursor.execute("INSERT INTO inventory (barcode, status) VALUES (?, ?)", (barcode, status))
        else:
            current_status = row[0]
            new_status = 'out' if current_status == 'in' else 'in'
            cursor.execute("UPDATE inventory SET status = ? WHERE barcode = ?", (new_status, barcode))

        if checked_out_by:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO checkout_log (barcode, checked_out_by, timestamp) VALUES (?, ?, ?)",
                           (barcode, checked_out_by, timestamp))

        conn.commit()

        # Emit updated inventory to all connected clients
        socketio.emit('update_inventory', get_inventory_data(), broadcast=True)
        
    except Exception as e:
        print(f"Error toggling item state for barcode {barcode}: {e}")
    finally:
        conn.close()

# WebSocket event for handling barcode scans
@socketio.on('scan')
def handle_scan(barcode):
    print(f"DEBUG: Received scan for barcode: {barcode}")
    toggle_item_state(barcode)

# WebSocket event for handling name submission
@socketio.on('submit_name')
def handle_submit_name(data):
    barcode = data.get('barcode')
    checked_out_by = data.get('checked_out_by')

    if not barcode or not checked_out_by:
        return {'error': 'Missing barcode or name'}, 400

    toggle_item_state(barcode, checked_out_by)
    emit('update_inventory', get_inventory_data(), broadcast=True)

# Flask route to display inventory
@app.route('/')
def inventory():
    conn = get_db_connection()
    items = conn.execute('''
        SELECT i.id, i.barcode, i.status, l.checked_out_by, l.timestamp 
        FROM inventory i
        LEFT JOIN checkout_log l ON i.barcode = l.barcode 
        ORDER BY l.timestamp DESC
    ''').fetchall()
    conn.close()
    
    print(f"DEBUG: Items fetched from database: {items}")  # Add this line
    return render_template('inventory.html', items=items)


# Main execution flow
if __name__ == "__main__":
    # Detect barcode scanner
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    scanner = None

    # Assign the correct device for the scanner
    for device in devices:
        print(f"Device found: {device.path} {device.name}")
        if device.path == '/dev/input/event3':  # Adjust if needed
            scanner = evdev.InputDevice(device.path)
            break

    if not scanner:
        raise Exception("No barcode scanner found!")

    # Start the barcode processing in a separate thread
    threading.Thread(target=process_barcode, args=(scanner,), daemon=True).start()
    
    # Start Flask app
    print("Ready to scan items...")
    socketio.run(app, host='0.0.0.0', port=5000)
