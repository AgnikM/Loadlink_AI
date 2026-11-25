package ai.loadlink.driver.sync

import ai.loadlink.driver.data.local.LocationDatabase
import ai.loadlink.driver.network.ApiClient
import ai.loadlink.driver.network.GPSBatchIngestRequest
import ai.loadlink.driver.network.GPSBreadcrumbDto
import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class TelemetrySyncWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val db = LocationDatabase.getInstance(applicationContext)
        val pending = db.locationDao().getPendingLocations(limit = 50)

        if (pending.isEmpty()) {
            return Result.success()
        }

        val dtos = pending.map { entity ->
            GPSBreadcrumbDto(
                driverId = entity.driverId,
                truckId = entity.truckId,
                shipmentId = entity.shipmentId,
                latitude = entity.latitude,
                longitude = entity.longitude,
                accuracyMeters = entity.accuracyMeters,
                speedKmh = entity.speedKmh,
                heading = entity.heading,
                deviceTimestamp = entity.deviceTimestamp,
                sequenceNumber = entity.sequenceNumber
            )
        }

        return try {
            // Retrieve bearer token from private SharedPreferences
            val prefs = applicationContext.getSharedPreferences("loadlink_auth", Context.MODE_PRIVATE)
            val token = prefs.getString("auth_token", null)
            val authHeader = if (!token.isNullOrBlank()) {
                if (token.startsWith("Bearer ")) token else "Bearer $token"
            } else ""

            val apiService = ApiClient.getService()
            val response = apiService.ingestGPSBatch(authHeader, GPSBatchIngestRequest(breadcrumbs = dtos))

            if (response.isSuccessful && response.body() != null) {
                val syncedIds = pending.map { it.id }
                db.locationDao().markAsSynced(syncedIds)

                // Purge historical records older than 48 hours
                val cutoff = System.currentTimeMillis() - (48 * 60 * 60 * 1000L)
                db.locationDao().purgeSyncedLocations(cutoff)

                Result.success()
            } else if (response.code() in 400..499) {
                // Client error / rejected batch
                Result.failure()
            } else {
                // Server 5xx or network glitch: retry
                Result.retry()
            }
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
