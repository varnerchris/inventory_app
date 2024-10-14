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

    # Create the inventory table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK (status IN ('in', 'out'))
    )
    ''')

    # Create checkout_log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS checkout_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT NOT NULL,
        checked_out_by TEXT NOT NULL,
        timestamp REAL NOT NULL
    )
    ''')

    conn.commit()
    conn.close()

# Initialize the database
initialize_database()

# Connect to SQLite database globally
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Function to toggle item state
def toggle_item_state(barcode, checked_out_by=None):
    try:
        print(f"Toggling item state for barcode: {barcode}")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()

        if row is None:
            status = 'in'
            cursor.execute("INSERT INTO inventory (barcode, status) VALUES (?, ?)", (barcode, status))
            print(f"Inserted barcode {barcode} with status {status}.")
        else:
            current_status = row[0]
            new_status = 'out' if current_status == 'in' else 'in'
            cursor.execute("UPDATE inventory SET status = ? WHERE barcode = ?", (new_status, barcode))
            print(f"Updated barcode {barcode} to new status {new_status}.")

        if checked_out_by:
            cursor.execute("INSERT INTO checkout_log (barcode, checked_out_by, timestamp) VALUES (?, ?, ?)",
                           (barcode, checked_out_by, time.time()))

        conn.commit()
        # Emit the scanned barcode to all connected clients
        socketio.emit('barcode_scanned', {'barcode': barcode, 'checked_out_by': checked_out_by})
    except Exception as e:
        print(f"Error toggling item state for barcode {barcode}: {e}")
    finally:
        conn.close()

# WebSocket event for handling barcode scans
@socketio.on('scan')
def handle_scan(barcode):
    print(f"Received scan for barcode: {barcode}")
    toggle_item_state(barcode)

# Flask route to display inventory
@app.route('/')
def inventory():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    return render_template('inventory.html', items=items)

# Flask route to toggle item status via a web interface
@app.route('/toggle/<barcode>', methods=['POST'])
def toggle(barcode):
    checked_out_by = request.form.get('checked_out_by')
    toggle_item_state(barcode, checked_out_by)
    return redirect(url_for('inventory'))

# Function to process barcode input
def process_barcode(scanner):
    barcode = ''
    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]
                if key == 'KEY_ENTER':
                    socketio.emit('scan', barcode)
                    barcode = ''  # Reset for the next scan
                else:
                    barcode += key[-1]  # Append the character to the barcode

# Main execution flow
if __name__ == "__main__":
    # Detect barcode scanner
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    scanner = None

    # Assign the correct event device (make sure this is the right one)
    for device in devices:
        print(f"Device found: {device.path} {device.name}")
        if device.path == '/dev/input/event3':  # Change this if necessary
            scanner = device
            break

    if not scanner:
        raise Exception("No barcode scanner found!")

    # Start the barcode processing in a separate thread
    threading.Thread(target=process_barcode, args=(scanner,), daemon=True).start()

    # Start Flask app
    print("Ready to scan items...")
    socketio.run(app, host='0.0.0.0', port=5000)
