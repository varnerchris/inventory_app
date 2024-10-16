import sqlite3
import subprocess
import evdev
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for
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

    # Create a dictionary to hold the most recent inventory state
    inventory_dict = {}

    for item in items:
        barcode = item['barcode']

        # Update the dictionary with the latest checkout information
        if barcode not in inventory_dict or (item['checkout_timestamp'] and item['checkout_timestamp'] > inventory_dict[barcode]['checkout_timestamp']):
            inventory_dict[barcode] = {
                'status': item['status'],
                'checked_out_by': item['checked_out_by'] or 'N/A',
                'checkout_timestamp': item['checkout_timestamp'] or 'N/A'
            }

    # Convert the dictionary back to a list
    inventory = [{'barcode': barcode, **data} for barcode, data in inventory_dict.items()]

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




# Function to toggle the state of an item
def toggle_item_state(barcode, checked_out_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    item = cursor.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()

    if item:
        new_status = 'out' if item['status'] == 'in' else 'in'
        action = 'checkout' if new_status == 'out' else 'checkin'
    else:
        new_status = 'out'  # Assuming first-time scan means checking out
        action = 'create'
        cursor.execute('INSERT INTO inventory (barcode, status, checked_out_by) VALUES (?, ?, ?)', 
                       (barcode, new_status, checked_out_by))

    # Insert the action into the checkout_log
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)',
                   (barcode, action, checked_out_by, timestamp))

    # Update the inventory table with the new status
    cursor.execute('UPDATE inventory SET status = ?, checked_out_by = ?, checkout_timestamp = ? WHERE barcode = ?', 
                   (new_status, checked_out_by, timestamp, barcode))

    conn.commit()
    conn.close()





# WebSocket event for handling barcode scans
@socketio.on('scan')
def handle_scan(barcode):
    print(f"DEBUG: Received scan for barcode: {barcode}")
    toggle_item_state(barcode)




# WebSocket event for handling name submission
@socketio.on('submit_name')
def handle_name_submission(data):
    barcode = data['barcode']
    employee_id = data['employee_id']
    
    # Fetch employee name from the database
    conn = get_db_connection()
    employee = conn.execute('SELECT name FROM employees WHERE id = ?', (employee_id,)).fetchone()
    
    if not barcode or not employee:
        return {'error': 'Missing barcode or employee'}, 400

    # Use employee name in inventory update
    toggle_item_state(barcode, employee['name'])
    emit('update_inventory', get_inventory_data(), broadcast=True)




# Flask route to display inventory
@app.route('/')
def inventory():
    conn = get_db_connection()
    
    # Query to get only the most recent checkout_log entry for each barcode
    items = conn.execute(''' 
        SELECT i.id, i.barcode, i.status, l.checked_out_by, l.timestamp
        FROM inventory i
        LEFT JOIN (
            SELECT barcode, checked_out_by, timestamp
            FROM checkout_log
            WHERE timestamp = (
                SELECT MAX(timestamp)
                FROM checkout_log AS sublog
                WHERE sublog.barcode = checkout_log.barcode
            )
        ) l ON i.barcode = l.barcode
        ORDER BY l.timestamp DESC;
    ''').fetchall()

    # Convert items from sqlite3.Row to a list of dictionaries
    items_list = []
    for item in items:
        items_list.append({
            'id': item['id'],
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'],
            'timestamp': item['timestamp']
        })

    conn.close()
    
    # Print the items for debugging
    print("DEBUG: Items fetched from database:", items_list)

    return render_template('inventory.html', items=items_list)


# Route to get employee names and emails for the dropdown
@app.route('/get_employees', methods=['GET'])
def get_employees():
    conn = get_db_connection()
    employees = conn.execute('SELECT id, name, email FROM employees').fetchall()
    conn.close()
    
    # Format data for Select2: id and text fields
    employee_list = [{'id': emp['id'], 'text': f"{emp['name']} ({emp['email']})"} for emp in employees]
    
    return jsonify(employee_list)


def get_inventory_data():
    conn = get_db_connection()
    
    items = conn.execute('''
        SELECT 
            i.barcode, 
            i.status, 
            l.checked_out_by, 
            l.timestamp AS checkout_timestamp 
        FROM 
            inventory i
        LEFT JOIN 
            (SELECT barcode, checked_out_by, timestamp 
             FROM checkout_log 
             WHERE (barcode, timestamp) IN (
                 SELECT barcode, MAX(timestamp) 
                 FROM checkout_log 
                 GROUP BY barcode
             )) l ON i.barcode = l.barcode
    ''').fetchall()
    
    # Convert to a list of dictionaries for easier manipulation on the client
    inventory_items = []
    for item in items:
        inventory_items.append({
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'] if item['checked_out_by'] else 'N/A',  # Handle NULL values
            'checkout_timestamp': item['checkout_timestamp'] if item['checkout_timestamp'] else 'N/A'  # Handle NULL values
        })
    
    conn.close()
    return {'items': inventory_items}  # Return as a dictionary with 'items' key for consistency






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
