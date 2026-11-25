import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "loadlink.db")

def migrate():
    print(f"Connecting to database at {DB_PATH} for V5 Migration...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables_and_columns = [
        ("trucks", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
            ("legal_payload_tons", "FLOAT DEFAULT NULL"),
            ("quoted_freight_inr", "FLOAT DEFAULT NULL"),
        ]),
        ("drivers", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("dealers", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("transporters", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("users", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("organizations", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("loads", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("bookings", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("shipments", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
        ("truck_locations", [
            ("is_demo", "BOOLEAN DEFAULT 0"),
        ]),
    ]

    for table, columns in tables_and_columns:
        # Check if table exists
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            print(f"Table {table} does not exist. Skipping.")
            continue

        existing_cols = [r[1] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        for col_name, col_def in columns:
            if col_name not in existing_cols:
                print(f"Adding column '{col_name}' to '{table}'...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            else:
                print(f"Column '{col_name}' already exists in '{table}'.")

    conn.commit()
    conn.close()
    print("V5 Migration completed successfully.")

if __name__ == "__main__":
    migrate()
