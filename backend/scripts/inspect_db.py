import sqlite3

conn = sqlite3.connect('loadlink.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Existing tables:", tables)
for t in ['users', 'trucks', 'bookings', 'organizations']:
    if t in tables:
        c.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in c.fetchall()]
        print(f"{t} columns:", cols)
conn.close()
