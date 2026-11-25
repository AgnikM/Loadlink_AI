import sys
import os
import sqlite3

sys.path.insert(0, os.path.abspath('backend'))

print("=== LOADLINK AI MASTER PROMPT 4 - SYSTEM AUDIT ===")

# 1. Database Inspection
conn = sqlite3.connect('backend/loadlink.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]
print(f"\n[1] Database Tables: {len(tables)}")

cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name, name;")
indexes = cur.fetchall()
print(f"[2] Explicit Indexes: {len(indexes)}")
for idx in indexes:
    print(f"  - {idx[0]} on {idx[1]}: {idx[2]}")

# Count rows per table
print("\n[3] Table Row Counts:")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t};")
    cnt = cur.fetchone()[0]
    if cnt > 0:
        print(f"  - {t}: {cnt} rows")

conn.close()

# 2. FastAPI Routes Inspection
from app.main import app
routes = []
for r in app.routes:
    if hasattr(r, 'methods') and hasattr(r, 'path'):
        for m in r.methods:
            routes.append((m, r.path, r.endpoint.__name__, getattr(r.endpoint, '__module__', '')))

print(f"\n[4] Total Registered FastAPI Routes: {len(routes)}")
# Check for duplicate paths with same method
seen = set()
duplicates = []
for m, path, ep, mod in routes:
    key = (m, path)
    if key in seen:
        duplicates.append((key, ep, mod))
    seen.add(key)

if duplicates:
    print(f"  WARNING: Found {len(duplicates)} duplicate routes:")
    for d in duplicates:
        print(f"    - {d[0][0]} {d[0][1]} -> {d[1]} in {d[2]}")
else:
    print("  No duplicate HTTP method + path routes detected.")

# Group by tag/module
by_mod = {}
for m, path, ep, mod in routes:
    short_mod = mod.split('.')[-1] if mod else 'main'
    by_mod.setdefault(short_mod, []).append((m, path, ep))

print("\n[5] Routes by Module:")
for mod, mod_routes in sorted(by_mod.items()):
    print(f"  - {mod} ({len(mod_routes)} endpoints):")
    for m, path, ep in mod_routes[:3]:
        print(f"      {m:6} {path} -> {ep}")
    if len(mod_routes) > 3:
        print(f"      ... and {len(mod_routes)-3} more")

print("\nAudit script completed successfully.")
