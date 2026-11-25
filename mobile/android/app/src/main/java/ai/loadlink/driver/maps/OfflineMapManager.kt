package ai.loadlink.driver.maps

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.net.URL
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.tan

/**
 * LoadLink Driver - Offline Map & Corridor Tile Caching Manager
 *
 * Coordinates caching of map tiles for the West Bengal freight corridor
 * (Haldia Port - Durgapur Industrial Corridor):
 *  - Bounding Box: [22.2, 86.8, 23.8, 88.5]
 *  - Zoom Levels: 10 through 14
 *
 * CRITICAL ARCHITECTURAL DISTINCTION:
 * Tile caching provides visual geometry offline. It DOES NOT provide offline dynamic
 * route recalculation or turn-by-turn guidance if the vehicle deviates from the corridor,
 * unless a native routing graph (Valhalla/GraphHopper/OSRM) is embedded on-device.
 */
class OfflineMapManager(private val context: Context) {

    companion object {
        const val CORRIDOR_NAME = "Haldia-Durgapur-Industrial-Corridor"
        const val MIN_LAT = 22.2
        const val MIN_LON = 86.8
        const val MAX_LAT = 23.85
        const val MAX_LON = 88.5

        const val MIN_ZOOM = 10
        const val MAX_ZOOM = 14
    }

    private val cacheDir: File
        get() = File(context.filesDir, "offline_corridor_tiles").apply {
            if (!exists()) mkdirs()
        }

    fun isCorridorCached(): Boolean {
        val corridorDir = File(cacheDir, CORRIDOR_NAME)
        return corridorDir.exists() && (corridorDir.listFiles()?.size ?: 0) > 0
    }

    fun getLocalTileUrlTemplate(): String {
        return "file://${cacheDir.absolutePath}/$CORRIDOR_NAME/{z}/{x}/{y}.png"
    }

    suspend fun downloadCorridorTiles(
        tileUrlPattern: String = "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        progressListener: (downloaded: Int, total: Int) -> Unit
    ): Boolean = withContext(Dispatchers.IO) {
        val corridorFolder = File(cacheDir, CORRIDOR_NAME).apply { mkdirs() }
        var totalTiles = 0
        val tileCoords = mutableListOf<Triple<Int, Int, Int>>() // z, x, y

        for (z in MIN_ZOOM..MAX_ZOOM) {
            val minX = lonToTileX(MIN_LON, z)
            val maxX = lonToTileX(MAX_LON, z)
            val minY = latToTileY(MAX_LAT, z)
            val maxY = latToTileY(MIN_LAT, z)

            for (x in minX..maxX) {
                for (y in minY..maxY) {
                    tileCoords.add(Triple(z, x, y))
                    totalTiles++
                }
            }
        }

        var downloadedCount = 0
        for ((z, x, y) in tileCoords) {
            val tileFile = File(corridorFolder, "$z/$x/$y.png").apply {
                parentFile?.mkdirs()
            }
            if (!tileFile.exists()) {
                val urlString = tileUrlPattern
                    .replace("{z}", z.toString())
                    .replace("{x}", x.toString())
                    .replace("{y}", y.toString())
                try {
                    val input = URL(urlString).openStream()
                    val output = FileOutputStream(tileFile)
                    input.copyTo(output)
                    input.close()
                    output.close()
                } catch (e: Exception) {
                    // Ignore transient network tile drop
                }
            }
            downloadedCount++
            if (downloadedCount % 20 == 0 || downloadedCount == totalTiles) {
                progressListener(downloadedCount, totalTiles)
            }
        }

        true
    }

    private fun lonToTileX(lon: Double, zoom: Int): Int {
        return floor((lon + 180.0) / 360.0 * (1 shl zoom)).toInt()
    }

    private fun latToTileY(lat: Double, zoom: Int): Int {
        val latRad = Math.toRadians(lat)
        return floor((1.0 - ln(tan(latRad) + 1.0 / kotlin.math.cos(latRad)) / Math.PI) / 2.0 * (1 shl zoom)).toInt()
    }
}
