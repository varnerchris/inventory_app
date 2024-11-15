def update_employees_table(data):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch current employees from the database
    cursor.execute("SELECT email FROM employees")
    db_emails = {row['email'] for row in cursor.fetchall()}

    # Extract API employee emails and details
    api_emails = set()
    api_employees = []

    for employee in data:
        acf = employee.get('acf', {})
        if acf.get('av_inventory') is True:
            name = acf.get('staff_name')
            email = acf.get('email_address')
            if name and email:
                api_emails.add(email)
                api_employees.append({"name": name, "email": email})

    # Find employees to deactivate
    to_deactivate = db_emails - api_emails

    # Deactivate employees no longer in the API
    for email in to_deactivate:
        cursor.execute(
            "UPDATE employees SET active = 0 WHERE email = ?",
            (email,)
        )
        print(f"Deactivated employee: {email}")

    # Add new employees from the API
    for employee in api_employees:
        cursor.execute(
            "SELECT * FROM employees WHERE email = ?",
            (employee['email'],)
        )
        existing_employee = cursor.fetchone()

        if existing_employee:
            if not existing_employee['active']:
                # Reactivate if previously deactivated
                cursor.execute(
                    "UPDATE employees SET active = 1 WHERE email = ?",
                    (employee['email'],)
                )
                print(f"Reactivated employee: {employee['name']} ({employee['email']})")
        else:
            # Add new employee
            cursor.execute(
                "INSERT INTO employees (name, email, active) VALUES (?, ?, 1)",
                (employee['name'], employee['email'])
            )
            print(f"Added new employee: {employee['name']} ({employee['email']})")

    conn.commit()
    conn.close()
