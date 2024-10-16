import sqlite3

def create_employee_table():
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()

    # Create the employees table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE
    );
    ''')

    # Commit the changes and close the connection
    conn.commit()

    # Retrieve and print the data from the table
    cursor.execute('SELECT * FROM employees')
    rows = cursor.fetchall()

    print("Employees in the database:")
    for row in rows:
        print(row)

    # Close the connection
    conn.close()

if __name__ == "__main__":
    create_employee_table()
