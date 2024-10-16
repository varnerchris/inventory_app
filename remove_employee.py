import sqlite3

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

def remove_employee(employee_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if the employee exists
    cursor.execute("SELECT * FROM employees WHERE name = ?", (employee_name,))
    employee = cursor.fetchone()

    if employee:
        # Employee exists, ask for confirmation
        confirm = input(f"Are you sure you want to remove the employee '{employee_name}'? (y/n): ").lower()
        if confirm == 'y':
            cursor.execute("DELETE FROM employees WHERE name = ?", (employee_name,))
            conn.commit()
            print(f"Employee '{employee_name}' has been removed successfully.")
        else:
            print("Operation cancelled. Employee not removed.")
            
    else:
        print(f"Employee '{employee_name}' not found.")
    
    conn.close()

if __name__ == "__main__":
    emp_name = input("Enter the name of the employee to remove: ")
    remove_employee(emp_name)
