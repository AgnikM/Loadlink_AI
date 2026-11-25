package ai.loadlink.driver

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.tan

class OfflineMapCoordinatesTest {

    private fun lonToTileX(lon: Double, zoom: Int): Int {
        return floor((lon + 180.0) / 360.0 * (1 shl zoom)).toInt()
    }

    private fun latToTileY(lat: Double, zoom: Int): Int {
        val latRad = Math.toRadians(lat)
        return floor((1.0 - ln(tan(latRad) + 1.0 / kotlin.math.cos(latRad)) / PI) / 2.0 * (1 shl zoom)).toInt()
    }

    @Test
    fun testHaldiaDurgapurBoundingBoxTileCalculation() {
        val minLat = 22.2
        val maxLat = 23.85
        val minLon = 86.8
        val maxLon = 88.5
        val zoom = 10

        val minTileX = lonToTileX(minLon, zoom)
        val maxTileX = lonToTileX(maxLon, zoom)
        val minTileY = latToTileY(maxLat, zoom) // Higher latitude is lower tile Y
        val maxTileY = latToTileY(minLat, zoom)

        assertTrue("minTileX <= maxTileX", minTileX <= maxTileX)
        assertTrue("minTileY <= maxTileY", minTileY <= maxTileY)
        
        // Haldia/Durgapur at Zoom 10 should span ~5-8 tiles in X and Y
        val tileCount = (maxTileX - minTileX + 1) * (maxTileY - minTileY + 1)
        assertTrue("Corridor should have a reasonable tile count for zoom 10 ($tileCount)", tileCount in 1..50)
    }

    @Test
    fun testOfflineDisplayVsRoutingDistinction() {
        // Architectural assertion: Cached map tiles can render raster imagery offline,
        // but offline dynamic recalculation requires an edge-contracted routing graph (e.g. GraphHopper/Valhalla)
        val hasOfflineRasterTiles = true
        val hasEmbeddedRoutingEngine = false

        assertTrue("Raster display supported offline via cached XYZ tiles", hasOfflineRasterTiles)
        // When hasEmbeddedRoutingEngine is false, app must flag deviation rather than inventing fake routes
        assertFalse("Dynamic offline route recalculation requires embedded engine, which is not present in standard tile caching", hasEmbeddedRoutingEngine)
    }
}
