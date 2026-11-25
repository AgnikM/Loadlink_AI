package ai.loadlink.driver.services

import ai.loadlink.driver.MainActivity
import ai.loadlink.driver.R
import ai.loadlink.driver.data.local.LocationDatabase
import ai.loadlink.driver.data.local.LocationEntity
import ai.loadlink.driver.sync.TelemetrySyncWorker
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.location.Location
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.atomic.AtomicInteger

/**
 * LoadLink Driver - Persistent Location Tracking Foreground Service
 *
 * Implements Android 14+ compliant foreground telematics service with:
 *  - Adaptive velocity-aware sampling (Highway: 30s, City: 60s, Stationary: 300s)
 *  - Partial WakeLock to bypass aggressive Doze Mode termination
 *  - Local encrypted SQLite (Room) persistence-first pipeline
 *  - Background WorkManager synchronization triggers
 */
class LocationForegroundService : Service() {

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private var wakeLock: PowerManager.WakeLock? = null
    private val sequenceCounter = AtomicInteger(1)

    private var currentIntervalMs: Long = INTERVAL_HIGHWAY_MS
    private var consecutiveIdleCycles = 0

    private var activeDriverId: String = "driver-default"
    private var activeTruckId: String = "truck-default"
    private var activeShipmentId: String? = null

    companion object {
        const val CHANNEL_ID = "loadlink_tracking_channel"
        const val NOTIFICATION_ID = 9001

        const val ACTION_START = "ai.loadlink.driver.action.START_TRACKING"
        const val ACTION_STOP = "ai.loadlink.driver.action.STOP_TRACKING"

        const val EXTRA_DRIVER_ID = "extra_driver_id"
        const val EXTRA_TRUCK_ID = "extra_truck_id"
        const val EXTRA_SHIPMENT_ID = "extra_shipment_id"

        const val INTERVAL_HIGHWAY_MS = 30000L   // 30 seconds
        const val INTERVAL_CITY_MS = 60000L      // 60 seconds
        const val INTERVAL_IDLE_MS = 300000L     // 300 seconds (5 min)
    }

    override fun onCreate() {
        super.onCreate()
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        createNotificationChannel()

        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "LoadLink:LocationWakeLock").apply {
            setReferenceCounted(false)
        }

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { location ->
                    handleLocation(location)
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                activeDriverId = intent.getStringExtra(EXTRA_DRIVER_ID) ?: activeDriverId
                activeTruckId = intent.getStringExtra(EXTRA_TRUCK_ID) ?: activeTruckId
                activeShipmentId = intent.getStringExtra(EXTRA_SHIPMENT_ID)
                startTracking()
            }
            ACTION_STOP -> {
                stopTracking()
            }
        }
        // START_STICKY instructs the Android runtime to recreate the service if killed under memory pressure
        return START_STICKY
    }

    private fun startTracking() {
        wakeLock?.acquire(24 * 60 * 60 * 1000L) // Safety lease cap: 24h
        val notification = buildNotification("LoadLink Active: Logging telemetry for West Bengal freight corridor")
        startForeground(NOTIFICATION_ID, notification)
        requestLocationUpdates(INTERVAL_HIGHWAY_MS)
    }

    private fun stopTracking() {
        fusedLocationClient.removeLocationUpdates(locationCallback)
        if (wakeLock?.isHeld == true) {
            wakeLock?.release()
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    @SuppressLint("MissingPermission")
    private fun requestLocationUpdates(intervalMs: Long) {
        currentIntervalMs = intervalMs
        fusedLocationClient.removeLocationUpdates(locationCallback)

        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMs)
            .setMinUpdateIntervalMillis(intervalMs / 2)
            .setMaxUpdateDelayMillis(intervalMs * 2)
            .build()

        try {
            fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper())
        } catch (e: SecurityException) {
            // Log security denial if driver revoked permission in settings
        }
    }

    private fun handleLocation(location: Location) {
        val speedKmh = location.speed * 3.6f
        adjustAdaptiveSampling(speedKmh)

        val seq = sequenceCounter.getAndIncrement()
        val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val timestampStr = isoFormat.format(Date(location.time))

        val entity = LocationEntity(
            driverId = activeDriverId,
            truckId = activeTruckId,
            shipmentId = activeShipmentId,
            latitude = location.latitude,
            longitude = location.longitude,
            accuracyMeters = location.accuracy,
            speedKmh = speedKmh,
            heading = location.bearing,
            deviceTimestamp = timestampStr,
            sequenceNumber = seq,
            isSuspiciousJump = speedKmh > 130.0f
        )

        // 1. Persistence-First: commit to local Room DB immediately
        serviceScope.launch {
            val db = LocationDatabase.getInstance(applicationContext)
            db.locationDao().insertLocation(entity)

            // 2. Trigger asynchronous WorkManager batch sync
            triggerSyncWorker()
        }
    }

    private fun adjustAdaptiveSampling(speedKmh: Float) {
        val targetInterval = when {
            speedKmh > 45f -> {
                consecutiveIdleCycles = 0
                INTERVAL_HIGHWAY_MS
            }
            speedKmh >= 5f -> {
                consecutiveIdleCycles = 0
                INTERVAL_CITY_MS
            }
            else -> {
                consecutiveIdleCycles++
                if (consecutiveIdleCycles >= 5) INTERVAL_IDLE_MS else INTERVAL_CITY_MS
            }
        }

        if (targetInterval != currentIntervalMs) {
            requestLocationUpdates(targetInterval)
        }
    }

    private fun triggerSyncWorker() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val syncRequest = OneTimeWorkRequestBuilder<TelemetrySyncWorker>()
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(applicationContext).enqueueUniqueWork(
            "TelemetryBatchSync",
            ExistingWorkPolicy.KEEP,
            syncRequest
        )
    }

    private fun buildNotification(text: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("LoadLink Active Tracking")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.tracking_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.tracking_channel_description)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopTracking()
        super.onDestroy()
    }
}
