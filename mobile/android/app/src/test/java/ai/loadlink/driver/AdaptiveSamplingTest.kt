package ai.loadlink.driver

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptiveSamplingTest {

    private fun calculateSamplingInterval(speedKmh: Float, idleMinutes: Long): Long {
        return when {
            speedKmh > 45.0f -> 30_000L      // Highway: 30 seconds
            speedKmh >= 5.0f -> 60_000L      // City / Congestion: 60 seconds
            idleMinutes >= 5 -> 300_000L     // Idle / Halt (>5 min): 300 seconds (5 min)
            else -> 60_000L                  // Recent stop (<5 min): 60 seconds
        }
    }

    @Test
    fun testHighwaySpeedSampling() {
        val interval = calculateSamplingInterval(65.5f, 0L)
        assertEquals("Speed > 45 km/h must sample at 30 seconds (30000ms)", 30_000L, interval)
    }

    @Test
    fun testCitySpeedSampling() {
        val interval = calculateSamplingInterval(28.0f, 0L)
        assertEquals("Speed between 5 and 45 km/h must sample at 60 seconds (60000ms)", 60_000L, interval)
    }

    @Test
    fun testProlongedIdleSampling() {
        val interval = calculateSamplingInterval(0.0f, 15L)
        assertEquals("Idle for > 5 min must sample at 300 seconds (300000ms)", 300_000L, interval)
    }

    @Test
    fun testBriefStopSampling() {
        val interval = calculateSamplingInterval(0.0f, 2L)
        assertEquals("Brief stop < 5 min must stay on 60 seconds (60000ms)", 60_000L, interval)
    }
}
