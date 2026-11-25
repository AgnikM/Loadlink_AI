package ai.loadlink.driver.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_locations")
data class LocationEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val driverId: String,
    val truckId: String,
    val shipmentId: String?,
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Float,
    val speedKmh: Float,
    val heading: Float,
    val deviceTimestamp: String,
    val sequenceNumber: Int,
    val isSuspiciousJump: Boolean = false,
    val isSynced: Boolean = false,
    val createdAt: Long = System.currentTimeMillis()
)
