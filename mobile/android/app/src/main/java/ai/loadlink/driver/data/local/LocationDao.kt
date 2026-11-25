package ai.loadlink.driver.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface LocationDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLocation(location: LocationEntity): Long

    @Query("SELECT * FROM pending_locations WHERE isSynced = 0 ORDER BY sequenceNumber ASC LIMIT :limit")
    suspend fun getPendingLocations(limit: Int = 50): List<LocationEntity>

    @Query("UPDATE pending_locations SET isSynced = 1 WHERE id IN (:ids)")
    suspend fun markAsSynced(ids: List<Long>)

    @Query("DELETE FROM pending_locations WHERE isSynced = 1 AND createdAt < :olderThanTimestamp")
    suspend fun purgeSyncedLocations(olderThanTimestamp: Long)

    @Query("SELECT COUNT(*) FROM pending_locations WHERE isSynced = 0")
    suspend fun getPendingCount(): Int
}
