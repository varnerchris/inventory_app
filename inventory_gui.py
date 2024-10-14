import sqlite3
import tkinter as tk

# Connect to SQLite database
conn = sqlite3.connect('inventory.db')
cursor = conn.cursor()

# Create a main application window
class InventoryApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Inventory Status")
        self.geometry("400x300")

        # Create a Listbox to display items
        self.listbox = tk.Listbox(self, width=50, height=15)
        self.listbox.pack(pady=20)

        # Create a refresh button
        self.refresh_button = tk.Button(self, text="Refresh", command=self.refresh)
        self.refresh_button.pack(pady=10)

        # Refresh the displayed items
        self.refresh()

    def refresh(self):
        """Clear the listbox and display current item statuses."""
        self.listbox.delete(0, tk.END)
        
        cursor.execute("SELECT barcode, status FROM inventory")
        items = cursor.fetchall()
        
        for item in items:
            barcode, status = item
            if status == 'in':
                color = 'green'
            else:
                color = 'red'

            self.listbox.insert(tk.END, f"{barcode} - {status}")
            self.listbox.itemconfig(tk.END, {'bg': color})

# Run the application
if __name__ == "__main__":
    app = InventoryApp()
    app.mainloop()

# Close the database connection when the GUI closes
conn.close()
