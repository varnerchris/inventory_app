import sqlite3
import subprocess
import evdev
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import threading
from email_notifications import send_notification
from datetime import datetime

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
        SELECT 
            i.barcode, 
            i.status, 
            l.checked_out_by, 
            l.timestamp AS checkout_timestamp,
            i.expected_return_date  -- Include expected return date
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
    ''').fetchall()
 # Debug: Log fetched items
    print("DEBUG: Fetched items from the database:")
    for item in items:
        print({
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'],
            'checkout_timestamp': item['checkout_timestamp'],
            'expected_return_date': item['expected_return_date']
        })
    # Create a list to hold the inventory state
    inventory = []

    for item in items:
        inventory.append({
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'] or 'N/A',
            'checkout_timestamp': item['checkout_timestamp'] or 'N/A',
            'expected_return_date': item['expected_return_date'] or 'N/A'  # Include expected return date
        })

    conn.close()
    return {'items': inventory}

# Function to process barcode scan




""" #OLD
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
                    
                    # Check if the item already exists in the inventory
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    item = cursor.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()
                    conn.close()

                    if item:
                        # If the item exists, emit barcode to client-side to trigger the modal
                        socketio.emit('barcode_scanned', {'barcode': barcode})
                    else:
                        # If the item doesn't exist, create it with default values
                        print(f"DEBUG: Creating new item in inventory: {barcode}")
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('INSERT INTO inventory (barcode, status, checked_out_by, expected_return_date) VALUES (?, ?, ?, ?)', 
                                       (barcode, 'in', 'system', 'N/A'))
                        conn.commit()
                        conn.close()
                        print(f"DEBUG: New item {barcode} added to inventory.")

                    barcode = ''  # Reset for the next scan
                else:
                    # Add key to barcode string
                    barcode += key[-1]
"""

# Function to process barcode scan
def process_barcode(scanner):
    barcode = ''
    print("DEBUG: Starting barcode processing...")

    for event in scanner.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            key_event = evdev.categorize(event)
            if key_event.keystate == key_event.key_down:
                key = evdev.ecodes.KEY[key_event.scancode]

                

                # Ignore the Shift keys
                if key in ['KEY_LEFTSHIFT', 'KEY_RIGHTSHIFT']:
                    continue

                # When 'Enter' key is detected, barcode is complete
                if key == 'KEY_ENTER':
                    

                    # Check if the item already exists in the inventory
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    item = cursor.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()
                    conn.close()

                    if item:
                        # If the item exists, emit barcode to client-side to trigger the modal
                        socketio.emit('barcode_scanned', {'barcode': barcode})
                    else:
                        # If the item doesn't exist, create it with default values
                        print(f"DEBUG: Creating new item in inventory: {barcode}")
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            'INSERT INTO inventory (barcode, status, checked_out_by, expected_return_date) VALUES (?, ?, ?, ?)', 
                            (barcode, 'in', 'system', 'N/A')
                        )
                        conn.commit()
                        conn.close()
                        print(f"DEBUG: New item {barcode} added to inventory.")

                    # Reset the barcode string for the next scan
                    barcode = ''

                else:
                    # Convert key name to the actual character
                    char = None
                    if key.startswith('KEY_'):
                        # Remove 'KEY_' prefix to get the character
                        char = key.split('KEY_')[-1].lower()
                        if len(char) == 1:  # If it's a single character
                            barcode += char
                            print(f"DEBUG: Updated barcode: {barcode}")









# Function to toggle the state of an item
def toggle_item_state(barcode, checked_out_by, expected_return_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the item already exists in the inventory
    item = cursor.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()

    if item:
        # If the item exists, toggle the status
        new_status = 'out' if item['status'] == 'in' else 'in'

        if new_status == 'out':
            # When checking out, ensure the expected return date is provided
            if not expected_return_date:
                print("Expected return date is required for check-out.")
                return  # Exit if no return date is provided
            
            # Insert the action into the checkout_log for checkout
            action = 'checkout'
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)',
                           (barcode, action, checked_out_by, timestamp))

        else:
            # When checking in, clear the expected return date
            expected_return_date = None  # Clear return date when checking in
            action = 'checkin'
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)',
                           (barcode, action, checked_out_by, timestamp))
    
    else:
        # If the item does not exist, it means it's a new entry (create action)
        new_status = 'in'  # Mark the new item as 'in'
        action = 'create'
        
        # Insert the new item into the inventory table with status 'in'
        cursor.execute('INSERT INTO inventory (barcode, status, checked_out_by, expected_return_date) VALUES (?, ?, ?, ?)', 
                       (barcode, new_status, checked_out_by, expected_return_date))

        # Insert the action into the checkout_log for create
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)',
                       (barcode, action, 'system', timestamp))

        # Emit a `new_item` event to the frontend
        socketio.emit('new_item', {
            'barcode': barcode,
            'status': 'in',
            'checked_out_by': 'system',
            'expected_return_date': expected_return_date or 'N/A'
        })
        print(f"DEBUG: New item {barcode} added to inventory.")

    # Update the inventory table with the new status, checked out by, and expected return date
    cursor.execute('UPDATE inventory SET status = ?, checked_out_by = ?, checkout_timestamp = ?, expected_return_date = ? WHERE barcode = ?', 
                   (new_status, checked_out_by, timestamp, expected_return_date, barcode))

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
    expected_return_date = data.get('expected_return_date')  # Get expected return date

    # Establish the database connection
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the item exists
    item = cursor.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()

    # Get the current timestamp
    checkout_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    if item:
        # If the item exists, determine the new status
        new_status = 'out' if item['status'] == 'in' else 'in'  # Toggle status

        # Update the inventory with new status, checked out by, expected return date, and timestamp
        cursor.execute('''
            UPDATE inventory 
            SET status = ?, checked_out_by = ?, checkout_timestamp = ?, expected_return_date = ? 
            WHERE barcode = ?
        ''', (new_status, employee_id, checkout_timestamp, expected_return_date if new_status == 'out' else None, barcode))
        
        # Log the checkout or check-in action in the checkout_log
        action = 'checkout' if new_status == 'out' else 'checkin'
        cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)', 
                       (barcode, action, employee_id, checkout_timestamp))

        print(f"DEBUG: Updated item {barcode}: new_status={new_status}, checked_out_by={employee_id}, expected_return_date={expected_return_date}, checkout_timestamp={checkout_timestamp}")

    else:
        # If the item does not exist, create it with default values
        cursor.execute('INSERT INTO inventory (barcode, status, checked_out_by, expected_return_date) VALUES (?, ?, ?, ?)', 
                       (barcode, 'in', employee_id, expected_return_date))
        
        # Log the creation action in the checkout_log
        action = 'create'
        cursor.execute('INSERT INTO checkout_log (barcode, action, checked_out_by, timestamp) VALUES (?, ?, ?, ?)', 
                       (barcode, action, 'system', checkout_timestamp))
        print(f"DEBUG: New item {barcode} added to inventory with status 'in'.")

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()

    # Emit the updated inventory to all connected clients
    emit('update_inventory', get_inventory_data(), broadcast=True)








# Flask route to display inventory
@app.route('/')
def inventory():
    conn = get_db_connection()
    
    # Query to get the most recent checkout_log entry for each barcode, including employee names
    items = conn.execute(''' 
        SELECT i.id, 
                i.description,
               i.barcode, 
               i.status, 
               e.name AS checked_out_by,  -- Get employee name instead of ID
               l.timestamp, 
               i.expected_return_date  -- Include expected return date
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
        LEFT JOIN employees e ON l.checked_out_by = e.id  -- Join with employees table to get employee name
        ORDER BY l.timestamp DESC;
    ''').fetchall()

    # Convert items from sqlite3.Row to a list of dictionaries
    items_list = []
    for item in items:
        items_list.append({
            'id': item['id'],
            'description' : item['description'],
            'barcode': item['barcode'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'] if item['checked_out_by'] else 'N/A',  # Handle NULL values
            'timestamp': item['timestamp'],
            'expected_return_date': item['expected_return_date']  # Include expected return date
        })

    conn.close()
    
    # Print the items for debugging
    print("DEBUG: Items fetched from database:", items_list)

    return render_template('inventory.html', items=items_list)



# Route to GET item Status
@app.route('/get_item_status', methods=['GET'])
def get_item_status():
    barcode = request.args.get('barcode')
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()
    conn.close()

    if item:
        return jsonify({
            'status': item['status'],
            'checked_out_by': item['checked_out_by'],
            'expected_return_date': item['expected_return_date'] or 'N/A'
        })
    else:
        # Skip modal, item is newly created
        return jsonify({'status': 'new_item'}), 200  # Indicate it's a new item and skip status lookup


# Route to get employee names and emails for the dropdown
@app.route('/get_employees', methods=['GET'])
def get_employees():
    conn = get_db_connection()
    employees = conn.execute('SELECT id, name, email, active FROM employees').fetchall()
    conn.close()
    
    # Format data for Select2: id, text, and active status
    employee_list = [{'id': emp['id'], 'text': f"{emp['name']} ({emp['email']})", 'active': emp['active']} for emp in employees]
    return jsonify(employee_list)


def get_inventory_data():
    conn = get_db_connection()
    
    items = conn.execute('''
        SELECT 
            i.description,
            i.barcode, 
            i.status, 
            e.name AS checked_out_by,  -- Get employee name instead of ID
            l.timestamp AS checkout_timestamp,
            i.expected_return_date  -- Include expected return date
        FROM 
            inventory i
        LEFT JOIN 
            checkout_log l ON i.barcode = l.barcode
        LEFT JOIN 
            employees e ON l.checked_out_by = e.id  -- Join with employees table to get employee name
        WHERE 
            l.timestamp = (
                SELECT MAX(timestamp) 
                FROM checkout_log AS sublog 
                WHERE sublog.barcode = l.barcode
            )
    ''').fetchall()
    
    # Debug: Print raw items fetched from the database
    print("DEBUG: Raw items fetched from database:")
    for item in items:
        print(dict(item))  # Convert each Row object to a dictionary for clearer output

    # Convert to a list of dictionaries for easier manipulation on the client
    inventory_items = []
    for item in items:
        inventory_items.append({
            'barcode': item['barcode'],
            'description': item['description'],
            'status': item['status'],
            'checked_out_by': item['checked_out_by'] if item['checked_out_by'] else 'N/A',  # Handle NULL values
            'checkout_timestamp': item['checkout_timestamp'] if item['checkout_timestamp'] else 'N/A',  # Handle NULL values
            'expected_return_date': item['expected_return_date'] if item['expected_return_date'] else 'N/A'  # Handle NULL values
        })
    
    # Debug: Print the structured inventory items
    print("DEBUG: Structured inventory items:", inventory_items)

    conn.close()
    return {'items': inventory_items}  # Return as a dictionary with 'items' key for consistency




# Function to check if items are overdue and send an email
def check_overdue_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query to get overdue items and the email of the person who checked them out
    overdue_items = cursor.execute('''
        SELECT i.barcode, i.expected_return_date, e.email
        FROM inventory i
        JOIN employees e ON i.checked_out_by = e.id
        WHERE i.status = 'out' 
        AND i.expected_return_date IS NOT NULL 
        AND DATE(i.expected_return_date) < DATE('now')
    ''').fetchall()
    
    for item in overdue_items:
        barcode = item['barcode']
        expected_return_date = item['expected_return_date']
        email = item['email']

        # Send email notification for overdue item
        send_notification(barcode, expected_return_date, email)
    
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
