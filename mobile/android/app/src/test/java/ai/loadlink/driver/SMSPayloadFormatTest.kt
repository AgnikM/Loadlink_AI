package ai.loadlink.driver

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SMSPayloadFormatTest {

    private fun formatSmsFallback(
        sosId: String,
        driverId: Int,
        truckId: Int,
        lat: Double,
        lon: Double,
        category: String,
        timestamp: String
    ): String {
        return "LOADLINK_SOS|$sosId|$driverId|$truckId|$lat,$lon|$category|$timestamp"
    }

    @Test
    fun testSmsPayloadStructure() {
        val payload = formatSmsFallback(
            sosId = "sos-uuid-1234",
            driverId = 42,
            truckId = 108,
            lat = 22.5726,
            lon = 88.3639,
            category = "ACCIDENT_OR_ROLLOVER",
            timestamp = "2026-11-22T10:30:00Z"
        )

        assertTrue(payload.startsWith("LOADLINK_SOS|"))
        val parts = payload.split("|")
        assertEquals(7, parts.size)
        assertEquals("LOADLINK_SOS", parts[0])
        assertEquals("sos-uuid-1234", parts[1])
        assertEquals("42", parts[2])
        assertEquals("108", parts[3])
        assertEquals("22.5726,88.3639", parts[4])
        assertEquals("ACCIDENT_OR_ROLLOVER", parts[5])
        assertEquals("2026-11-22T10:30:00Z", parts[6])
        
        // Single SMS standard character limit is 160 characters
        assertTrue("SMS payload should fit within 160 chars standard SMS segment (${payload.length})", payload.length <= 160)
    }
}
