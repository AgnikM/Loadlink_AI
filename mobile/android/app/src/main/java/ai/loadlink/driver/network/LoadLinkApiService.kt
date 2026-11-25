package ai.loadlink.driver.network

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

// --- Telemetry DTOs ---
data class GPSBreadcrumbDto(
    @SerializedName("driver_id") val driverId: String,
    @SerializedName("truck_id") val truckId: String,
    @SerializedName("shipment_id") val shipmentId: String?,
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("accuracy_meters") val accuracyMeters: Float,
    @SerializedName("speed_kmh") val speedKmh: Float,
    @SerializedName("heading") val heading: Float,
    @SerializedName("device_timestamp") val deviceTimestamp: String,
    @SerializedName("sequence_number") val sequenceNumber: Int
)

data class GPSBatchIngestRequest(
    @SerializedName("breadcrumbs") val breadcrumbs: List<GPSBreadcrumbDto>
)

data class GPSBatchIngestResponse(
    @SerializedName("ingested_count") val ingestedCount: Int,
    @SerializedName("anomalies_detected") val anomaliesDetected: Int,
    @SerializedName("suspicious_points") val suspiciousPoints: List<Int>,
    @SerializedName("latest_latitude") val latestLatitude: Double?,
    @SerializedName("latest_longitude") val latestLongitude: Double?,
    @SerializedName("is_stale") val isStale: Boolean,
    @SerializedName("server_timestamp") val serverTimestamp: String
)

// --- SOS DTOs ---
data class SOSTriggerRequest(
    @SerializedName("event_id") val eventId: String,
    @SerializedName("truck_id") val truckId: String,
    @SerializedName("shipment_id") val shipmentId: String?,
    @SerializedName("booking_id") val bookingId: String?,
    @SerializedName("latitude") val latitude: Double,
    @SerializedName("longitude") val longitude: Double,
    @SerializedName("accuracy_meters") val accuracyMeters: Float,
    @SerializedName("incident_category") val incidentCategory: String,
    @SerializedName("network_status") val networkStatus: String,
    @SerializedName("device_timestamp") val deviceTimestamp: String,
    @SerializedName("emergency_contact_name") val emergencyContactName: String?,
    @SerializedName("emergency_contact_phone") val emergencyContactPhone: String?,
    @SerializedName("audio_or_media_url") val audioOrMediaUrl: String?
)

data class SOSEventResponse(
    @SerializedName("id") val id: String,
    @SerializedName("event_id") val eventId: String,
    @SerializedName("status") val status: String,
    @SerializedName("control_room_notified") val controlRoomNotified: Boolean,
    @SerializedName("dealer_notified") val dealerNotified: Boolean,
    @SerializedName("emergency_contact_notified") val emergencyContactNotified: Boolean,
    @SerializedName("server_timestamp") val serverTimestamp: String
)

// --- Offline Metadata DTO ---
data class CorridorBoundingBoxDto(
    @SerializedName("min_latitude") val minLatitude: Double,
    @SerializedName("min_longitude") val minLongitude: Double,
    @SerializedName("max_latitude") val maxLatitude: Double,
    @SerializedName("max_longitude") val maxLongitude: Double
)

data class OfflineCorridorMetadataResponse(
    @SerializedName("corridor_name") val corridorName: String,
    @SerializedName("bounding_box") val boundingBox: CorridorBoundingBoxDto,
    @SerializedName("tile_pack_id") val tilePackId: String,
    @SerializedName("tile_url_template") val tileUrlTemplate: String,
    @SerializedName("min_zoom") val minZoom: Int,
    @SerializedName("max_zoom") val maxZoom: Int,
    @SerializedName("estimated_size_mb") val estimatedSizeMb: Double,
    @SerializedName("offline_routing_notice") val offlineRoutingNotice: String
)

interface LoadLinkApiService {
    @POST("tracking/batch")
    suspend fun ingestGPSBatch(
        @Header("Authorization") token: String,
        @Body request: GPSBatchIngestRequest
    ): Response<GPSBatchIngestResponse>

    @POST("sos/trigger")
    suspend fun triggerSOS(
        @Header("Authorization") token: String,
        @Body request: SOSTriggerRequest
    ): Response<SOSEventResponse>

    @GET("tracking/offline-metadata")
    suspend fun getOfflineCorridorMetadata(
        @Header("Authorization") token: String
    ): Response<OfflineCorridorMetadataResponse>
}
