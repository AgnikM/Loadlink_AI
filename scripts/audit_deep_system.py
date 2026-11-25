import sys
import os
import inspect
import sqlite3

sys.path.insert(0, os.path.abspath('backend'))

import app.main
from app.core.config import settings
from app.models import entities, enums

print("=" * 70)
print("LOADLINK AI - COMPREHENSIVE ARCHITECTURAL AUDIT (PHASE 1)")
print("=" * 70)

# --- 1. ROUTE AUDIT ---
routes_audit = []
seen_routes = {}
duplicate_routes = []

for r in app.main.app.routes:
    if hasattr(r, 'original_router'):
        prefix = r.include_context.prefix if hasattr(r, 'include_context') else ''
        for sub_r in r.original_router.routes:
            methods = list(sub_r.methods) if hasattr(sub_r, 'methods') else []
            full_path = prefix + sub_r.path
            ep = sub_r.endpoint
            routes_audit.append({
                "methods": methods,
                "path": full_path,
                "name": ep.__name__,
                "module": getattr(ep, '__module__', ''),
                "endpoint": ep
            })
    elif hasattr(r, 'methods') and hasattr(r, 'path'):
        routes_audit.append({
            "methods": list(r.methods),
            "path": r.path,
            "name": r.endpoint.__name__,
            "module": getattr(r.endpoint, '__module__', ''),
            "endpoint": r.endpoint
        })

print(f"\n[1] TOTAL ENDPOINTS DISCOVERED: {len(routes_audit)}")

for item in routes_audit:
    for m in item['methods']:
        key = (m, item['path'])
        if key in seen_routes:
            duplicate_routes.append((key, item['name'], seen_routes[key]['name']))
        else:
            seen_routes[key] = item

if duplicate_routes:
    print(f"⚠️  DUPLICATE ROUTES FOUND: {len(duplicate_routes)}")
    for d in duplicate_routes:
        print(f"   {d[0][0]} {d[0][1]}: {d[1]} conflicts with {d[2]}")
else:
    print("✅ No duplicate HTTP routes detected across all modules.")

# --- 2. AUTHENTICATION & RBAC COVERAGE ON SENSITIVE ENDPOINTS ---
public_whitelist = {
    "/health",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/token",
}

unprotected_sensitive_routes = []
for item in routes_audit:
    path = item['path']
    if any(path.startswith(pw) for pw in public_whitelist):
        continue
    # Check dependencies of endpoint
    sig = inspect.signature(item['endpoint'])
    has_auth_dep = False
    for param in sig.parameters.values():
        param_repr = str(param.default)
        if any(auth_kw in param_repr for auth_kw in ['get_current_user', 'get_current_active_user', 'oauth2_scheme', 'Security']):
            has_auth_dep = True
            break
    if not has_auth_dep:
        unprotected_sensitive_routes.append(f"{item['methods']} {path} ({item['module']}.{item['name']})")

print(f"\n[2] ROUTE SECURITY & RBAC AUDIT:")
if unprotected_sensitive_routes:
    print(f"⚠️  POTENTIALLY UNPROTECTED ROUTES WITHOUT AUTH DEPENDENCY ({len(unprotected_sensitive_routes)}):")
    for r in unprotected_sensitive_routes:
        print(f"   - {r}")
else:
    print("✅ All non-whitelisted API endpoints require authenticated user dependency!")

# --- 3. DATABASE SCHEMA & INDEX COVERAGE ---
conn = sqlite3.connect('backend/loadlink.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
db_tables = [r[0] for r in cur.fetchall()]

cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
existing_indexes = cur.fetchall()

print(f"\n[3] DATABASE SCHEMA AUDIT:")
print(f"   Total SQLite Tables: {len(db_tables)}")
print(f"   Total Explicit Indexes: {len(existing_indexes)}")

# Let's inspect foreign keys missing indexes
# SQLite does NOT automatically index foreign keys!
missing_fk_indexes = []
for t in db_tables:
    cur.execute(f"PRAGMA foreign_key_list({t});")
    fks = cur.fetchall()
    # fks format: (id, seq, table, from_col, to_col, on_update, on_delete, match)
    cur.execute(f"PRAGMA index_list({t});")
    idx_list = cur.fetchall()
    indexed_cols = set()
    for idx in idx_list:
        idx_name = idx[1]
        cur.execute(f"PRAGMA index_info({idx_name});")
        for col_info in cur.fetchall():
            indexed_cols.add(col_info[2])
    
    for fk in fks:
        from_col = fk[3]
        if from_col not in indexed_cols and from_col != 'id':
            missing_fk_indexes.append((t, from_col, fk[2]))

print(f"   Foreign Keys without Dedicated Index: {len(missing_fk_indexes)}")
for t, col, ref_t in missing_fk_indexes[:10]:
    print(f"    * {t}.{col} -> references {ref_t}.id")
if len(missing_fk_indexes) > 10:
    print(f"    ... and {len(missing_fk_indexes)-10} more FK columns")

conn.close()

# --- 4. CHECK FOR MOCKED OR HARDCODED DEMO LOGIC ---
print("\n[4] SCANNING FOR MOCKED DATA / HARDCODED LOGIC IN SERVICES:")
services_dir = 'backend/app/services'
suspicious_patterns = ['mock', 'TODO', 'FIXME', 'fake', 'dummy', 'temp_token', 'hardcoded']
found_issues = []

for root, _, files in os.walk(services_dir):
    for f in files:
        if f.endswith('.py'):
            fpath = os.path.join(root, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                for line_no, line in enumerate(fp, 1):
                    for pat in suspicious_patterns:
                        if pat.lower() in line.lower() and not line.strip().startswith('#'):
                            found_issues.append((f, line_no, line.strip()))

if found_issues:
    print(f"   Found {len(found_issues)} suspicious / mock code lines:")
    for f, lno, txt in found_issues[:15]:
        print(f"    - {f}:{lno} : {txt[:80]}")
else:
    print("✅ No suspicious mock / fake patterns found in backend services.")

print("\nComprehensive audit finished.")
