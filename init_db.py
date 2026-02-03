import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

with open("schema.sql") as f:
    conn.executescript(f.read())



conn.commit()
conn.close()

print("Database created successfully")
