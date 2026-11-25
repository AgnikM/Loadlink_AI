import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "loadlink.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in cursor.fetchall()]
print(f"Total Tables in {db_path}: {len(tables)}")
for t in tables:
    if t.startswith("sqlite_"):
        continue
    cursor.execute(f'SELECT count(*) FROM "{t}";')
    cnt = cursor.fetchone()[0]
    print(f"  {t:32}: {cnt} rows")

cursor.execute("PRAGMA foreign_keys;")
fk = cursor.fetchone()[0]
print(f"PRAGMA foreign_keys default in SQLite connection: {fk}")

# Check columns for loads table
cursor.execute("PRAGMA table_info('loads');")
load_cols = [c[1] for c in cursor.fetchall()]
print("\nLoads table columns (P2 added check):")
for col in ["cargo_category", "cargo_description", "declared_value_inr", "fragility", "hazard_classification", "handling_instructions", "supporting_documents"]:
    print(f"  {col}: {'EXISTS' if col in load_cols else 'MISSING'}")

conn.close()
