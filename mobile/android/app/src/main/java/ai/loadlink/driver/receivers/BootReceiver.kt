package ai.loadlink.driver.receivers

import ai.loadlink.driver.services.LocationForegroundService
import ai.loadlink.driver.sync.SOSSyncWorker
import ai.loadlink.driver.sync.TelemetrySyncWorker
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            val prefs = context.getSharedPreferences("loadlink_driver_state", Context.MODE_PRIVATE)
            val isTrackingActive = prefs.getBoolean("is_tracking_active", false)

            if (isTrackingActive) {
                val serviceIntent = Intent(context, LocationForegroundService::class.java).apply {
                    action = LocationForegroundService.ACTION_START
                    putExtra(LocationForegroundService.EXTRA_DRIVER_ID, prefs.getString("driver_id", null))
                    putExtra(LocationForegroundService.EXTRA_TRUCK_ID, prefs.getString("truck_id", null))
                    putExtra(LocationForegroundService.EXTRA_SHIPMENT_ID, prefs.getString("shipment_id", null))
                }
                ContextCompat.startForegroundService(context, serviceIntent)
            }

            // Immediately schedule workers to flush any pending queues once network is available
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val telemetryWork = OneTimeWorkRequestBuilder<TelemetrySyncWorker>()
                .setConstraints(constraints)
                .build()

            val sosWork = OneTimeWorkRequestBuilder<SOSSyncWorker>()
                .setConstraints(constraints)
                .build()

            val wm = WorkManager.getInstance(context)
            wm.enqueueUniqueWork("BootTelemetrySync", ExistingWorkPolicy.KEEP, telemetryWork)
            wm.enqueueUniqueWork("BootSOSSync", ExistingWorkPolicy.KEEP, sosWork)
        }
    }
}
