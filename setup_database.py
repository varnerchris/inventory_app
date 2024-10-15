import sqlite3

# Connect to the database (it will create the file if it doesn't exist)
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

# Create the inventory table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('in', 'out')),
    checked_out_by TEXT,  -- Column for the name of the person checking out
    checkout_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP  -- Column for the checkout timestamp
)
''')

# Create the checkout_log table to track check-ins and check-outs
cursor.execute('''
CREATE TABLE IF NOT EXISTS checkout_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    checked_out_by TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL CHECK (action IN ('checkout', 'checkin'))  -- Add the action column
)
''')


# Commit the changes and close the connection
conn.commit()
conn.close()

print("Inventory and checkout_log tables created successfully.")
