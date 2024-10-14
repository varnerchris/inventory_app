import sqlite3
import subprocess
import evdev
import time
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
from gevent import monkey

# Apply monkey patching to allow gevent to work with other libraries
monkey.patch_all()

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
        print("DEBUG: Table 'inventory' does not exist. Running setup_database.py...")
        try:
            subprocess.run(['python3', 'setup_database.py'], check=True)
            print("DEBUG: setup_database.py executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Error running setup_database.py: {e}")
    else:
        print("DEBUG: Table 'inventory' already exists.")
    conn.close()

# Initialize the database
initialize_database()

# Connect to SQLite database globally
def get_db_connection():
    print("DEBUG: Establishing DB connection...")
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to toggle item state
def toggle_item_state(barcode, checked_out_by=None):
    try:
        print(f"DEBUG: Toggling item state for barcode: {barcode}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()

        if row is None:
            print(f"DEBUG: Barcode {barcode} not found in DB. Inserting new record.")
            status = 'in'
            cursor.execute("INSERT INTO inventory (barcode, status) VALUES (?, ?)", (barcode, status))
            print(f"DEBUG: Inserted barcode {barcode} with status {status}.")
        else:
            current_status = row[0]
            new_status = 'out' if current_status == 'in' else 'in'
            print(f"DEBUG: Barcode {barcode} found with status {current_status}. Updating to {new_status}.")
            cursor.execute("UPDATE inventory SET status = ? WHERE barcode = ?", (new_status, barcode))

        if checked_out_by:
            print(f"DEBUG: Logging checkout for {checked_out_by}.")
            cursor.execute("INSERT INTO checkout_log (barcode, checked_out_by, timestamp) VALUES (?, ?, ?)",
                           (barcode, checked_out_by, time.time()))

        conn.commit()
        # Emit the scanned barcode to all connected clients
        print(f"DEBUG: Emitting event 'barcode_scanned' for barcode {barcode}.")
        socketio.emit('barcode_scanned', {'barcode': barcode, 'checked_out_by': checked_out_by})
    except Exception as e:
        print(f"ERROR: Error toggling item state for barcode {barcode}: {e}")
    finally:
        conn.close()

# WebSocket event for handling barcode scans
@socketio.on('scan')
def handle_scan(data):
    barcode = data.get('barcode', None)
    if barcode:
        print(f"DEBUG: Received scan for barcode: {barcode}")
        toggle_item_state(barcode)
    else:
        print("ERROR: No barcode received in 'scan' event.")

# Flask route to display inventory
@app.route('/')
def inventory():
    print("DEBUG: Loading inventory page.")
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    print(f"DEBUG: Inventory page loaded with {len(items)} items.")
    return render_template('inventory.html', items=items)

# Flask route to toggle item status via a web interface
@app.route('/toggle/<barcode>', methods=['POST'])
def toggle(barcode):
    print(f"DEBUG: Toggling item via web interface for barcode: {barcode}.")
    checked_out_by = request.form.get('checked_out_by')
    toggle_item_state(barcode, checked_out_by)
    return redirect(url_for('inventory'))

# Function to process barcode from scanner
def process_barcode(scanner):
    barcode = ''
    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]
                if key == 'KEY_ENTER':
                    print(f"DEBUG: Barcode scanned: {barcode}")
                    toggle_item_state(barcode)  # Process the scanned barcode
                    barcode = ''  # Reset for the next scan
                else:
                    barcode += key[-1]  # Add the last character of the key name

# Main execution flow
if __name__ == "__main__":
    # Detect barcode scanner
    print("DEBUG: Detecting barcode scanner.")
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    scanner = None

    # Assign the first device found (adjust if needed)
    for device in devices:
        print(f"DEBUG: Device found: {device.path} {device.name}")
        if device.path == '/dev/input/event3':  # Ensure this is the correct event device
            scanner = device
            print(f"DEBUG: Barcode scanner selected: {device.path}")
            break

    if not scanner:
        raise Exception("ERROR: No barcode scanner found!")

    # Start the barcode processing in a separate thread
    print("DEBUG: Starting barcode processing thread.")
    threading.Thread(target=process_barcode, args=(scanner,), daemon=True).start()

    # Start Flask app with gevent for WebSocket support
    print("DEBUG: Starting Flask app with WebSocket support.")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
