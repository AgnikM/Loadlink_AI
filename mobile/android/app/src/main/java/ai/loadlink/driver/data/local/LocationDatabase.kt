package ai.loadlink.driver.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [LocationEntity::class, SOSEventEntity::class],
    version = 1,
    exportSchema = false
)
abstract class LocationDatabase : RoomDatabase() {
    abstract fun locationDao(): LocationDao
    abstract fun sosEventDao(): SOSEventDao

    companion object {
        @Volatile
        private var INSTANCE: LocationDatabase? = null

        fun getInstance(context: Context): LocationDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    LocationDatabase::class.java,
                    "loadlink_driver_offline.db"
                )
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
