package ai.loadlink.driver.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update

@Dao
interface SOSEventDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertSOS(event: SOSEventEntity): Long

    @Query("SELECT * FROM offline_sos_events WHERE syncStatus = 'PENDING_SYNC' ORDER BY deviceTimestamp ASC")
    suspend fun getPendingSOSEvents(): List<SOSEventEntity>

    @Query("SELECT * FROM offline_sos_events WHERE eventId = :eventId LIMIT 1")
    suspend fun getSOSByEventId(eventId: String): SOSEventEntity?

    @Update
    suspend fun updateSOS(event: SOSEventEntity)

    @Query("UPDATE offline_sos_events SET syncStatus = :status, backendResponseId = :backendId WHERE eventId = :eventId")
    suspend fun markSOSSynced(eventId: String, status: String, backendId: String?)

    @Query("UPDATE offline_sos_events SET syncStatus = 'SMS_ATTEMPTED' WHERE eventId = :eventId")
    suspend fun markSOSSmsSent(eventId: String)

    @Query("UPDATE offline_sos_events SET syncStatus = :status WHERE eventId = :eventId")
    suspend fun updateSyncStatus(eventId: String, status: String)
}
