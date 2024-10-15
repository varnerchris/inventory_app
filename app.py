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
                    toggle_item_state(barcode)  # Process the scanned barcode
                    barcode = ''  # Reset for the next scan
                else:
                    # Add key to barcode string
                    barcode += key[-1]

# Function to toggle item state
def toggle_item_state(barcode, checked_out_by=None):
    try:
        print(f"DEBUG: Toggling item state for barcode: {barcode}")
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
            # Optionally log who checked out the item
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
    print(f"DEBUG: Received scan for barcode: {barcode}")
    toggle_item_state(barcode)

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
    return render_template('inventory.html', items=items)

# Flask route to toggle item status via a web interface
@app.route('/toggle/<barcode>', methods=['POST'])
def toggle(barcode):
    checked_out_by = request.form.get('checked_out_by')
    toggle_item_state(barcode, checked_out_by)
    return redirect(url_for('inventory'))

@app.route('/submit_name', methods=['POST'])
def submit_name():
    barcode = request.json.get('barcode')
    checked_out_by = request.json.get('checked_out_by')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update inventory status and log the checkout information
        cursor.execute("SELECT status FROM inventory WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()

        if row is None:
            return {'error': 'Barcode not found'}, 404

        # Update the status and log the transaction
        new_status = 'out' if row[0] == 'in' else 'in'
        cursor.execute("UPDATE inventory SET status = ? WHERE barcode = ?", (new_status, barcode))
        cursor.execute("INSERT INTO checkout_log (barcode, checked_out_by, timestamp) VALUES (?, ?, ?)", 
                       (barcode, checked_out_by, time.strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        return {'success': True}
    
    except Exception as e:
        print(f"Error processing barcode {barcode}: {e}")
        return {'error': str(e)}, 500
    
    finally:
        conn.close()

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
