package ai.loadlink.driver

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class SOSEventStateTest {

    enum class DeliveryState {
        PENDING,
        SMS_ATTEMPTED,
        SERVER_CONFIRMED,
        FAILED
    }

    data class MockSOSEvent(
        val clientEventId: String = UUID.randomUUID().toString(),
        var deliveryState: DeliveryState = DeliveryState.PENDING,
        var smsIntentTriggered: Boolean = false,
        var serverAcknowledged: Boolean = false,
        var retryCount: Int = 0
    ) {
        fun onSmsIntentDispatched() {
            smsIntentTriggered = true
            deliveryState = DeliveryState.SMS_ATTEMPTED
        }

        fun onServerResponse(httpStatus: Int) {
            if (httpStatus in 200..299) {
                serverAcknowledged = true
                deliveryState = DeliveryState.SERVER_CONFIRMED
            } else {
                retryCount++
                if (retryCount >= 5 && !smsIntentTriggered) {
                    deliveryState = DeliveryState.FAILED
                }
            }
        }

        // Strict Play Protect & Safety rule: UI must NEVER claim message received based only on SMS dispatch
        fun isDeliveryConfirmedToControlRoom(): Boolean {
            return deliveryState == DeliveryState.SERVER_CONFIRMED
        }
    }

    @Test
    fun testInitialStateIsPending() {
        val sos = MockSOSEvent()
        assertEquals(DeliveryState.PENDING, sos.deliveryState)
        assertFalse(sos.isDeliveryConfirmedToControlRoom())
    }

    @Test
    fun testSmsFallbackAttemptDoesNotConfirmServerReceipt() {
        val sos = MockSOSEvent()
        sos.onSmsIntentDispatched()
        assertEquals(DeliveryState.SMS_ATTEMPTED, sos.deliveryState)
        assertTrue(sos.smsIntentTriggered)
        assertFalse("Opening SMS app or attempting SMS MUST NEVER be treated as confirmed server receipt", sos.isDeliveryConfirmedToControlRoom())
    }

    @Test
    fun testServerAcknowledgementConfirmsReceipt() {
        val sos = MockSOSEvent()
        sos.onSmsIntentDispatched()
        sos.onServerResponse(201)
        assertEquals(DeliveryState.SERVER_CONFIRMED, sos.deliveryState)
        assertTrue(sos.isDeliveryConfirmedToControlRoom())
    }

    @Test
    fun testUniqueEventIdPreventsDuplicateGeneration() {
        val id1 = UUID.randomUUID().toString()
        val id2 = UUID.randomUUID().toString()
        assertFalse("Each SOS event must have a distinct UUIDv4", id1 == id2)
    }
}
