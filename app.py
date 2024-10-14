from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

@app.route('/')
def inventory():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute("SELECT barcode, status FROM inventory")
    items = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', items=items)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
