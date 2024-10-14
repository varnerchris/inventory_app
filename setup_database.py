import sqlite3

# Connect to the database (it will create the file if it doesn't exist)
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

# Create the inventory table
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('in', 'out')),
    checked_out_by TEXT,  -- New column for the name of the person checking out
    checkout_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP  -- New column for the checkout timestamp
)
''')
# Commit the changes and close the connection
conn.commit()
conn.close()

print("Inventory table created successfully.")
