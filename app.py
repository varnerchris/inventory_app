from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

# Function to get database connection
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row  # This allows access to columns by name
    return conn

@app.route('/')
def inventory():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM inventory').fetchall()
    conn.close()
    
    # Debugging output
    print(f"Items in inventory: {items}")

    return render_template('inventory.html', items=items)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Adjust host and port as needed
