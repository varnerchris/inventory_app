import sqlite3

def add_employee(name, email):
    # Connect to SQLite database
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # Insert employee data into the table
    try:
        cursor.execute('INSERT INTO employees (name, email) VALUES (?, ?)', (name, email))
        conn.commit()
        print(f"Employee {name} added successfully.")
    except sqlite3.IntegrityError:
        print(f"Error: Employee with email {email} already exists.")

      # Retrieve and print the data from the table
    cursor.execute('SELECT * FROM employees')
    rows = cursor.fetchall()

    print("Employees in the database:")
    for row in rows:
        print(row)

    
    # Close the connection
    conn.close()


if __name__ == "__main__":
    # Take employee details from user input
    name = input("Enter employee name: ")
    email = input("Enter employee email: ")

    # Add the employee to the database
    add_employee(name, email)

    
