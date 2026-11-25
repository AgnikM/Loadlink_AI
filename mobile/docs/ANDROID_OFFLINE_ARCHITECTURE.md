# LoadLink AI - Android Mobile & Offline Operations Architecture

## 1. Executive Overview

This specification documents the production-grade Android mobile tracking and offline execution model for the LoadLink AI Driver application. It addresses the realities of freight transit across low-connectivity highway corridors, severe operating system battery restrictions (Android Doze Mode and OEM App Killers), and the strict boundary between map visualization versus dynamic offline route recalculation.

---

## 2. Android Mobile Application Architecture

### 2.1 Process Execution Model
Web applications running in mobile browsers (or standard background web workers) are aggressively suspended by modern Android releases (Android 11 through 14+) within 60 to 180 seconds of the screen locking. To guarantee uninterrupted telematics, the LoadLink driver client utilizes a hybrid Capacitor runtime backed by a native Kotlin Foreground Service (`LocationForegroundService`).

```
+-------------------------------------------------------------+
|                 Android OS Runtime                          |
|                                                             |
|  +---------------------------+   IPC / JS Bridge            |
|  |   Capacitor WebView UI    |<==========================>+ |
|  |  (Next.js / DriverView)   |                            | |
|  +---------------------------+                            | |
|                |                                          | |
|                v Local Storage / IndexedDB                | |
|  +---------------------------+                            | |
|  |   Offline Event Storage   |                            | |
|  |  (SOS, Breakdowns, Checks)|                            | |
|  +---------------------------+                            | |
|                ^                                          | |
|                | Room DB Mirror                           | |
|  +------------------------------------------------------+ | |
|  |       Native LocationForegroundService (START_STICKY) | | |
|  |  - FusedLocationProviderClient (GPS + Cellular)      | | |
|  |  - Partial WakeLock (Keep CPU active during motion)  | | |
|  |  - Adaptive Sampling Engine                          | | |
|  |  - Local Encrypted SQLite Breadcrumb Queue           | | |
|  |  - WorkManager Sync Reconciliation                   | | |
|  +------------------------------------------------------+ | |
+-------------------------------------------------------------+
```

### 2.2 Adaptive Battery & Speed-Aware Sampling Strategy
To balance high tracking fidelity against device battery preservation across 10-14 hour highway shifts, telemetry collection dynamically adjusts according to vehicle velocity:

| State | Speed Threshold | Sampling Interval | Transmission Batch Size | Battery Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Highway Transit** | Speed > 45 km/h | **30 seconds** | 5 breadcrumbs (every 150s) | Moderate (~3-4% / hr) |
| **City / Congestion**| 5 km/h ≤ Speed ≤ 45 km/h | **60 seconds** | 5 breadcrumbs (every 300s) | Low (~2% / hr) |
| **Stationary / Rest**| Speed < 5 km/h for > 5 min| **300 seconds (5 min)**| 1 heartbeat breadcrumb | Negligible (<0.5% / hr) |

### 2.3 Android Permission Matrix & Rationale

| Permission | API Level | Type | Purpose & Justification |
| :--- | :--- | :--- | :--- |
| `ACCESS_FINE_LOCATION` | All | Runtime | Precise GNSS coordinates for custody geofencing and lane tracking. |
| `ACCESS_COARSE_LOCATION` | All | Runtime | Fallback network cell-tower / Wi-Fi positioning. |
| `ACCESS_BACKGROUND_LOCATION` | API 29+ | Runtime (Dedicated prompt) | Telematics collection while driver navigates or device screen is locked. |
| `FOREGROUND_SERVICE` | API 28+ | Manifest | Authorizes non-terminating background processing. |
| `FOREGROUND_SERVICE_LOCATION` | API 34+ | Manifest | Android 14 mandatory capability declaration for location services. |
| `WAKE_LOCK` | All | Normal | Prevents CPU sleep during coordinate sampling and queue commit. |
| `ACTIVITY_RECOGNITION` | API 29+ | Runtime | Identifies `IN_VEHICLE` vs `STILL` states without waking GNSS chip. |
| `POST_NOTIFICATIONS` | API 33+ | Runtime | Ongoing notification required by Android for foreground services. |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | API 23+ | System Intent | Whitelists LoadLink from Android Doze-mode background restrictions. |
| `RECEIVE_BOOT_COMPLETED` | All | Normal | Revives tracking and pending queue flush after phone reboot. |
| `SEND_SMS` | All | Runtime | SOS emergency fallback trigger when zero data (2G/3G/4G/5G) exists. |

---

## 3. Resilience & OS Constraint Management

### 3.1 Android Doze Mode Handling
When an Android device is unplugged, stationary, and screen-off for an extended duration, Doze mode suspends network access, ignores wake locks, and defers alarms until brief "maintenance windows":
1. **Foreground Service Exemption**: Declaring `android:foregroundServiceType="location"` with an active notification and acquiring a `PARTIAL_WAKE_LOCK` permits the CPU to fire scheduled location callbacks during normal transit.
2. **Whitelist Intent**: On first launch, the driver is guided to accept `Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, ensuring unthrottled background execution.

### 3.2 Mitigation of Aggressive OEM Killers (MIUI, ColorOS, OxygenOS, Samsung OneUI)
Many Android OEM builds terminate background services regardless of `START_STICKY`:
- **Dual Safeguard Architecture**:
  1. `LocationForegroundService` returns `START_STICKY`.
  2. A scheduled `androidx.work.PeriodicWorkRequest` runs every 15 minutes. If it detects the foreground service has died while a shipment status is `IN_TRANSIT`, it posts a high-priority heads-up notification prompting the driver to reopen the app and restarts the service.
  3. `BootReceiver` hooks `android.intent.action.BOOT_COMPLETED` and `MY_PACKAGE_REPLACED` to seamlessly resume tracking.

---

## 4. Offline Map & Corridor Caching Architecture

### 4.1 Corridor Bounding Box Definition
For the primary industrial freight corridor (e.g., Haldia Port - Durgapur Industrial Corridor):
- **Corridor Bounding Box**: `[22.2, 86.8, 23.8, 88.5]` (Min Lat, Min Lon, Max Lat, Max Lon)
- **Supported Zoom Levels**: 10 (interstate highway overview) through 15 (ramp and terminal gate precision).
- **Storage Footprint**: Vector map tiles (`.pbf` format) for this bounding box require **~180 MB to 260 MB** of internal storage.

### 4.2 Critical Technical Notice: Tile Caching vs. Dynamic Routing
> [!IMPORTANT]
> **Vector or raster tile caching alone provides visual map rendering only. It DOES NOT provide offline turn-by-turn route calculation or dynamic re-routing when a driver deviates from the designated path.**
> 
> Generating a new path offline requires an embedded native routing engine binary (such as Valhalla, GraphHopper, or OSRM) compiled as an Android NDK C++ shared library (`.so`) bundled with a pre-compiled routing graph (`.osm.pbf` contraction hierarchies, ~350 MB additional per state).
>
> **LoadLink Strategy**:
> - Pre-cache the authoritative Corridor Polyline and Bounding Box Tiles prior to dispatch.
> - If the driver deviates (> 500m off-route) while offline, the app displays a prominent **"OFF-ROUTE - RECONNECTING"** visual vector breadcrumb linking back to the nearest corridor waypoint without attempting invalid client-side route recomputations.

### 4.3 Network Reconnection Reconciliation Flow
```
Driver Device (Offline)              Local SQLite Queue              LoadLink Backend
       |                                     |                               |
       |-- (GPS / SOS / Breakdown) --------->| Store UUIDv4 + Timestamp      |
       |                                     | Status: PENDING_SYNC          |
       |                                     |                               |
[Network Restored (Online)]                  |                               |
       |                                     |                               |
       |-- Trigger Sync Job ---------------->| Read un-synced events         |
       |                                     | Sequence #101, #102, #103...  |
       |                                     |                               |
       |                                     |-- POST /api/v1/tracking/batch |
       |                                     |   (or /sos/trigger, etc.) --->|
       |                                     |                               |-- Verify Signatures & Seq
       |                                     |                               |-- Detect Haversine Jumps
       |                                     |                               |-- Idempotent UPSERT
       |                                     |<-- HTTP 200 OK ---------------|
       |                                     |    (ingested_count: 3)        |
       |<-- Notify "All Synced" -------------| Mark CONFIRMED_SYNC           |
```
