package ai.loadlink.driver.services

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
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import java.util.concurrent.atomic.AtomicInteger

/**
 * LoadLink Driver - Location Tracking Foreground Service
 *
 * Implements persistent location tracking compliant with Android 14+ foreground service policies.
 * Adaptive sampling intervals:
 *  - Highway (> 45 km/h): 30s interval
 *  - City (5 - 45 km/h):  60s interval
 *  - Stationary (< 5 km/h for > 5 min): 300s interval (heartbeat)
 */
class LocationForegroundService : Service() {

    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private var wakeLock: PowerManager.WakeLock? = null
    private val sequenceCounter = AtomicInteger(1)
    
    private var currentIntervalMs: Long = 30000L
    private var consecutiveIdleCycles = 0

    companion object {
        const val CHANNEL_ID = "loadlink_tracking_channel"
        const val NOTIFICATION_ID = 9001
        const val ACTION_START = "ai.loadlink.driver.action.START_TRACKING"
        const val ACTION_STOP = "ai.loadlink.driver.action.STOP_TRACKING"

        const val INTERVAL_HIGHWAY_MS = 30000L // 30s
        const val INTERVAL_CITY_MS = 60000L    // 60s
        const val INTERVAL_IDLE_MS = 300000L   // 5 min (300s)
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
                    processLocation(location)
                }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startTracking()
            ACTION_STOP -> stopTracking()
        }
        // START_STICKY ensures Android restarts the service if it gets killed due to memory pressure
        return START_STICKY
    }

    private fun startTracking() {
        wakeLock?.acquire(24 * 60 * 60 * 1000L) // Safety cap: 24h
        val notification = buildForegroundNotification("LoadLink active: Tracking route telemetry")
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
            // Permission revoked by user in runtime settings
        }
    }

    private fun processLocation(location: Location) {
        val speedKmh = location.speed * 3.6f
        adjustSamplingInterval(speedKmh)

        val seq = sequenceCounter.getAndIncrement()

        // 1. Write immediately to local encrypted SQLite/Room queue
        // 2. Dispatch network sync worker if network is reachable
        // 3. Batch transmission handles batched sync (max 50 points per HTTP POST)
    }

    private fun adjustSamplingInterval(speedKmh: Float) {
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

    private fun buildForegroundNotification(statusText: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("LoadLink Driver Active")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Location Tracking Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps driver telemetry alive during active delivery runs"
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
