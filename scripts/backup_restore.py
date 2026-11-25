import os
import shutil
import sqlite3
import sys
import time

def backup_database(src_db: str = "backend/loadlink.db", backup_dir: str = "backups"):
    if not os.path.exists(src_db):
        print(f"Source database '{src_db}' not found.")
        return None

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_path = os.path.join(backup_dir, f"loadlink_backup_{timestamp}.db")

    # Use SQLite online backup API to ensure transactionally consistent snapshot
    src_conn = sqlite3.connect(src_db)
    dst_conn = sqlite3.connect(dest_path)
    with dst_conn:
        src_conn.backup(dst_conn, pages=100)
    dst_conn.close()
    src_conn.close()

    size_kb = os.path.getsize(dest_path) / 1024.0
    print(f"✅ Consistent online backup created: {dest_path} ({size_kb:.1f} KB)")
    return dest_path

def restore_database(backup_path: str, target_db: str = "backend/loadlink.db"):
    if not os.path.exists(backup_path):
        print(f"❌ Backup file '{backup_path}' does not exist.")
        return False

    # Verify backup integrity first
    conn = sqlite3.connect(backup_path)
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check;")
    res = cur.fetchone()[0]
    conn.close()

    if res != "ok":
        print(f"❌ Backup file integrity check failed: {res}")
        return False

    # Perform atomic restore
    temp_target = target_db + ".restore_tmp"
    shutil.copy2(backup_path, temp_target)
    if os.path.exists(target_db):
        os.replace(temp_target, target_db)
    else:
        os.rename(temp_target, target_db)

    print(f"✅ Successfully restored '{target_db}' from '{backup_path}'.")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Usage: python backup_restore.py restore <backup_path>")
        else:
            restore_database(sys.argv[2])
    else:
        backup_database()
