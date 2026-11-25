package ai.loadlink.driver.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "offline_sos_events")
data class SOSEventEntity(
    @PrimaryKey
    val eventId: String, // UUIDv4 idempotency key
    val driverId: String,
    val truckId: String,
    val shipmentId: String?,
    val bookingId: String?,
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Float,
    val incidentCategory: String,
    val networkStatus: String, // ONLINE, OFFLINE_SYNCED, SMS_QUEUED
    val deviceTimestamp: String,
    val emergencyContactName: String?,
    val emergencyContactPhone: String?,
    val syncStatus: String = "PENDING_SYNC", // PENDING_SYNC, SYNCED, SMS_FALLBACK_SENT, FAILED
    val retryCount: Int = 0,
    val lastAttemptTimestamp: Long = 0,
    val backendResponseId: String? = null
)
