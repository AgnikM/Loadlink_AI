# LoadLink AI

> **Deterministic B2B Freight Logistics & Custody Platform**  
> Operational Corridor: *Kolkata ↔ Durgapur ↔ Asansol (NH19 Industrial Belt, West Bengal)*

---

## 1. Project Overview

**LoadLink AI** is an intelligent, high-reliability B2B freight marketplace and telematics platform designed for industrial manufacturing corridors. It connects verified dealers/shippers, fleet transporters, and commercial drivers through deterministic multi-factor load matching, digital custody tracking, statutory risk-based insurance gating, direct payment acknowledgements, and offline-capable Android telematics with an emergency SOS response system.

### Key Capabilities
- **7-Factor Deterministic Matching Engine**: Evaluates truck candidates across route compatibility, pickup feasibility, proximity, capacity utilization, benchmark pricing, reliability, and return-load potential (<0.1ms latency with spatial LRU caching).
- **Role-Based Portals**: Tailored interfaces for Dealers/Shippers, External Transporters, Commercial Drivers, Fleet Managers, Control Room Operators, Compliance Officers, and Admins.
- **Digital Cargo Custody**: End-to-end handover workflow covering loading inspection, electronic seals, transit incident logging, and digital Proof of Delivery (POD) with support for full delivery, partial delivery, or refusal.
- **Risk-Based Insurance Verification**: Automated consignment risk tiering that enforces mandatory transit insurance and dispatch gating prior to departure.
- **Direct Carrier Payments & Platform Invoices**: Transparent dealer-to-transporter payment recording with explicit carrier acknowledgement, separated from platform commission invoices.
- **Native Android Driver Telematics**: Background Location Foreground Service with adaptive GPS sampling, Room database offline event queuing, and zero-permission native `ACTION_SENDTO` emergency SOS dispatch.

---

## 2. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend API** | Python 3.12, FastAPI, SQLAlchemy 2.0 (Asyncio), Pydantic v2, Uvicorn, Jose JWT, Passlib (Bcrypt) |
| **Database** | SQLite 3 (`loadlink.db`) with `PRAGMA foreign_keys = ON` & 110 explicit indexes; PostgreSQL + asyncpg ready |
| **Frontend Web** | Next.js 16.3.4 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS, Lucide Icons |
| **Android Mobile** | Kotlin 1.9, Android SDK 34 (minSdk 26), AndroidX, Room DB, WorkManager, Retrofit2, OkHttp3 |
| **Testing & Tools** | Pytest, Pytest-Asyncio, HTTPX, Adoptium OpenJDK 17, Gradle 8.5 |

---

## 3. Repository Architecture

```
loadlink-ai/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/              # 21 modular REST & WebSocket routers (98 endpoints)
│   │   ├── core/             # Configuration, Database engine, Rate limiting, Logging
│   │   ├── models/           # 33 relational SQLAlchemy entity models & enums
│   │   ├── schemas/          # Pydantic v2 validation & response schemas
│   │   └── services/         # Match engine, Custody, State machine, Routing, SOS
│   ├── tests/                # 70 automated pytest test cases (58 core regression tests)
│   ├── requirements.txt      # Python dependencies
│   ├── seed_corridor_data.py # Seed script for West Bengal corridor hubs & test actors
│   └── .env.example          # Backend environment template
├── frontend/                 # Next.js Web Application
│   ├── src/
│   │   ├── app/              # Next.js App Router (Dealer, Driver, Admin portals)
│   │   ├── components/       # Reusable UI widgets, agreements, tracking & operations
│   │   ├── lib/              # API client & offline IndexedDB storage helpers
│   │   └── types/            # TypeScript interfaces
│   ├── package.json          # Node.js dependencies
│   └── .env.example          # Frontend environment template
├── mobile/android/           # Native Android Driver Application
│   ├── app/                  # Android application module (Kotlin source & manifests)
│   ├── keystore.properties.example # Release signing template
│   └── build.gradle          # Gradle build & BuildConfig definitions
├── scripts/                  # Operational, benchmark & audit utilities
│   ├── apply_database_indexes.py # Schema indexing migration script
│   ├── backup_restore.py     # SQLite hot backup and recovery utility
│   ├── load_test_bench.py    # Multi-worker load test harness (100, 500, 1000 users)
│   └── setup_android_sdk.py  # Portable toolchain bootstrapper
├── .env.example              # Root environment reference
├── .gitignore                # Production-grade Git ignore definitions
└── README.md                 # Project documentation
```

---

## 4. Getting Started Locally

### Prerequisites
- **Python 3.12+**
- **Node.js 18+ & npm**
- **JDK 17** & **Android SDK** (for Android app compilation)

---

### Step 1: Clone and Configure Environment

```bash
git clone <repository-url> loadlink-ai
cd loadlink-ai
```

Copy the environment templates:

```bash
# Backend configuration
cp backend/.env.example backend/.env

# Frontend configuration
cp frontend/.env.example frontend/.env.local

# Android signing configuration (if building mobile)
cp mobile/android/keystore.properties.example mobile/android/keystore.properties
```

---

### Step 2: Backend Setup & Database Seeding

1. **Create and activate a virtual environment**:
   ```bash
   # On Windows (PowerShell):
   python -m venv backend/.venv
   .\backend\.venv\Scripts\Activate.ps1

   # On Linux/macOS:
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Initialize and seed the database**:
   ```bash
   python backend/seed_corridor_data.py
   python scripts/apply_database_indexes.py
   ```

4. **Start the FastAPI backend server**:
   ```bash
   # From the project root with virtual environment activated:
   python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
   ```

The backend API will be available at `http://127.0.0.1:8000`.

---

### Step 3: Frontend Setup

1. **Install Node.js dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server**:
   ```bash
   npm run dev
   ```

3. **Build for production**:
   ```bash
   npm run build
   ```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### Step 4: Android Driver Application (Optional)

1. **Run native unit tests**:
   ```bash
   python scripts/run_android_tests.py
   ```

2. **Assemble debug APK**:
   ```bash
   python scripts/build_android.py
   ```

The generated APK will be output to:  
`mobile/android/app/build/outputs/apk/debug/app-debug.apk`

---

## 5. API Documentation

Interactive OpenAPI / Swagger documentation is available out of the box when the backend is running:

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check & Latency Probe**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **System Metrics**: [http://127.0.0.1:8000/health/metrics](http://127.0.0.1:8000/health/metrics)

---

## 6. Default Demo Credentials

The seed script creates initial accounts for corridor demonstration:

| Role | Email | Password |
| :--- | :--- | :--- |
| **Admin** | `admin@loadlink.ai` | `admin123` |
| **Dealer / Shipper** | `dealer.kolkata@bengalsteel.in` | `dealer123` |
| **Transporter** | `transporter@bengalroadways.in` | `transporter123` |
| **Driver** | `driver.rajesh@loadlink.ai` | `driver123` |
| **Control Room** | `control.room@loadlink.ai` | `control123` |
| **Compliance Officer**| `compliance@loadlink.ai` | `compliance123` |
| **Dispute Officer** | `disputes@loadlink.ai` | `dispute123` |

---

## 7. Testing & Verification

Run the full automated test suite:

```bash
# Core regression tests (58 tests)
pytest backend/tests/test_master_prompt_1.py -v
pytest backend/tests/test_master_prompt_2.py -v
pytest backend/tests/test_master_prompt_2_1_security.py -v
pytest backend/tests/test_master_prompt_3.py -v

# Run multi-worker load test (100, 500, 1000 simulated users)
python scripts/load_test_bench.py
```

---

## 8. Backup & Recovery Operations

Create an atomic online SQLite hot backup:

```bash
python scripts/backup_restore.py
```

Restore from a backup snapshot:

```bash
python scripts/backup_restore.py restore backups/loadlink_backup_<timestamp>.db
```

---

## 9. Known Limitations & Production Roadmap

- **Database Write Concurrency**: SQLite with Write-Ahead Logging (`WAL`) provides stable throughput up to ~100 concurrent users (0.0% error rate). For mass-scale production exceeding 500 simultaneous writing clients, migration to PostgreSQL 16 + PostGIS is recommended.
- **Android Sideloading Advisory**: APKs sideloaded outside the Google Play Store display a standard *"Unrecognized App"* dialog until published through Google Play Console under an enrolled developer account.
- **Routing Service Fallback**: Live OSRM integration features an automatic circuit breaker. When running offline or behind firewalls, high-accuracy corridor geodesic heuristics are automatically used.
- **Legal Compliance**: Direct freight agreements and liability terms reflect statutory Carriage by Road Rules (2007) and should undergo jurisdiction-specific legal review prior to commercial deployment.
