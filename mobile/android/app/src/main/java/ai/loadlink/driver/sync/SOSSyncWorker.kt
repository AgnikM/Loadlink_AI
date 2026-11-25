package ai.loadlink.driver.sync

import ai.loadlink.driver.data.local.LocationDatabase
import ai.loadlink.driver.network.ApiClient
import ai.loadlink.driver.network.SOSTriggerRequest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class SOSSyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val db = LocationDatabase.getInstance(applicationContext)
        val pendingSOSList = db.sosEventDao().getPendingSOSEvents()

        if (pendingSOSList.isEmpty()) {
            return Result.success()
        }

        // Securely retrieve token from private SharedPreferences without hardcoded fallback
        val prefs = applicationContext.getSharedPreferences("loadlink_auth", Context.MODE_PRIVATE)
        val token = prefs.getString("auth_token", null)
        val apiService = ApiClient.getService()

        for (sos in pendingSOSList) {
            try {
                val req = SOSTriggerRequest(
                    eventId = sos.eventId,
                    truckId = sos.truckId,
                    shipmentId = sos.shipmentId,
                    bookingId = sos.bookingId,
                    latitude = sos.latitude,
                    longitude = sos.longitude,
                    accuracyMeters = sos.accuracyMeters,
                    incidentCategory = sos.incidentCategory,
                    networkStatus = "OFFLINE_SYNCED",
                    deviceTimestamp = sos.deviceTimestamp,
                    emergencyContactName = sos.emergencyContactName,
                    emergencyContactPhone = sos.emergencyContactPhone,
                    audioOrMediaUrl = null
                )

                val authHeader = if (!token.isNullOrBlank()) "Bearer $token" else ""
                val response = apiService.triggerSOS(authHeader, req)

                if (response.isSuccessful && response.body() != null) {
                    val body = response.body()!!
                    db.sosEventDao().markSOSSynced(sos.eventId, "SERVER_CONFIRMED", body.id)
                } else {
                    prepareDriverSmsFallbackNotification(sos, db)
                }
            } catch (e: Exception) {
                // Network unreachable; trigger driver confirmation notification for native SMS fallback
                prepareDriverSmsFallbackNotification(sos, db)
            }
        }

        return Result.success()
    }

    /**
     * Prepares emergency fallback using standard Android ACTION_SENDTO intent.
     * Complies with Play Protect PHA policies:
     * 1. No background SmsManager.sendTextMessage() calls.
     * 2. Gateway is retrieved from authorized config or contact phone, never hardcoded.
     * 3. Driver explicitly taps and reviews message in native SMS app before sending.
     * 4. State is marked as SMS_ATTEMPTED (never falsely marked as delivered).
     */
    private suspend fun prepareDriverSmsFallbackNotification(
        sos: ai.loadlink.driver.data.local.SOSEventEntity,
        db: LocationDatabase
    ) {
        val prefs = applicationContext.getSharedPreferences("loadlink_driver_state", Context.MODE_PRIVATE)
        val authorizedGateway = prefs.getString("control_room_sms_gateway", null)
            ?: sos.emergencyContactPhone

        if (authorizedGateway.isNullOrBlank()) {
            val updated = sos.copy(
                syncStatus = "FAILED",
                retryCount = sos.retryCount + 1,
                lastAttemptTimestamp = System.currentTimeMillis()
            )
            db.sosEventDao().updateSOS(updated)
            return
        }

        val smsBody = "LOADLINK_SOS|${sos.eventId}|${sos.driverId}|${sos.truckId}|${sos.latitude},${sos.longitude}|${sos.incidentCategory}|${sos.deviceTimestamp}"

        // Launch native SMS app via ACTION_SENDTO intent
        val smsUri = Uri.parse("smsto:${Uri.encode(authorizedGateway)}")
        val smsIntent = Intent(Intent.ACTION_SENDTO, smsUri).apply {
            putExtra("sms_body", smsBody)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        val pendingIntent = PendingIntent.getActivity(
            applicationContext,
            sos.eventId.hashCode(),
            smsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notificationManager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channelId = "loadlink_emergency_fallback"

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Emergency SMS Fallback",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Prompts driver to send pre-formatted offline SOS via default SMS app"
            }
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(applicationContext, channelId)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("Emergency Alert: Tap to Send SMS")
            .setContentText("Network offline. Tap to confirm and dispatch SOS to Control Room.")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(sos.eventId.hashCode(), notification)

        // Truthful state: Record SMS_ATTEMPTED. Never claim delivered until server confirms HTTP 200/201.
        db.sosEventDao().updateSyncStatus(sos.eventId, "SMS_ATTEMPTED")
    }
}
