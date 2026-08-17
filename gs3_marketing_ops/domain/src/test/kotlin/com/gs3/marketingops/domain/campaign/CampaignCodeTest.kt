package com.gs3.marketingops.domain.campaign

import com.gs3.marketingops.domain.funnel.Track
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class CampaignCodeTest {

    private val spec = CampaignSpec(
        track = Track.EXPAT,
        market = "UAE",
        objective = Objective.CONV,
        audience = "LAL2",
        format = "Reel30s",
        version = 3,
        platform = Platform.META,
    )

    @Test
    fun `the code follows the naming convention exactly`() {
        assertEquals("GS3-EXPAT-UAE-CONV-LAL2-Reel30s-v3", spec.code)
    }

    @Test
    fun `the UTMs are derived from the same object, so they cannot drift from the code`() {
        // This is the whole reason the type exists. Typed separately, the code
        // and the UTMs diverge within a fortnight, and then spend sits under one
        // name while leads arrive under another and cost per lead is unknowable.
        val utm = spec.utmParameters()
        assertEquals("meta", utm["utm_source"])
        assertEquals("paid_social", utm["utm_medium"])
        assertEquals(spec.code.lowercase(), utm["utm_campaign"])
        assertEquals("lal2-reel30s-v3", utm["utm_content"])
    }

    @Test
    fun `changing one field moves the code and the UTMs together`() {
        val next = spec.copy(version = 4)
        assertEquals("GS3-EXPAT-UAE-CONV-LAL2-Reel30s-v4", next.code)
        assertEquals(next.code.lowercase(), next.utmParameters()["utm_campaign"])
        assertEquals("lal2-reel30s-v4", next.utmParameters()["utm_content"])
    }

    @Test
    fun `the tagged URL is built on the company's own site`() {
        val url = spec.taggedUrl()
        assertTrue(url.startsWith("https://general-sherman-housing.com/?"))
        assertTrue(url.contains("utm_source=meta"))
        assertTrue(url.contains("utm_campaign=gs3-expat-uae-conv-lal2-reel30s-v3"))
    }

    @Test
    fun `a base URL that already has a query gets an ampersand, not a second question mark`() {
        val url = spec.taggedUrl("https://general-sherman-housing.com/units.html?project=gs3")
        assertTrue(url.contains("?project=gs3&utm_source=meta"))
        assertEquals(1, url.count { it == '?' })
    }

    @Test
    fun `each platform brings its own medium`() {
        assertEquals("cpc", spec.copy(platform = Platform.GOOGLE).utmParameters()["utm_medium"])
        assertEquals("listing", spec.copy(platform = Platform.OPENSOOQ).utmParameters()["utm_medium"])
        assertEquals("video", spec.copy(platform = Platform.YOUTUBE).utmParameters()["utm_medium"])
    }

    @Test
    fun `a code round-trips through parsing`() {
        val parsed = CampaignSpec.parse(spec.code)
        assertEquals(spec.code, parsed?.code)
        assertEquals(Track.EXPAT, parsed?.track)
        assertEquals(Objective.CONV, parsed?.objective)
        assertEquals(3, parsed?.version)
    }

    @Test
    fun `nonsense does not parse into a campaign`() {
        assertNull(CampaignSpec.parse("not-a-campaign-code"))
        assertNull(CampaignSpec.parse("GS3-EXPAT-UAE-CONV-LAL2-Reel30s"))
        assertNull(CampaignSpec.parse("XX3-EXPAT-UAE-CONV-LAL2-Reel30s-v3"))
        assertNull(CampaignSpec.parse("GS3-MARTIAN-UAE-CONV-LAL2-Reel30s-v3"))
        assertNull(CampaignSpec.parse("GS3-EXPAT-UAE-CONV-LAL2-Reel30s-vX"))
    }

    @Test
    fun `a separator or a space inside a field is rejected, because it would corrupt the code`() {
        listOf("UA-E", "U AE").forEach { market ->
            val thrown = runCatching { spec.copy(market = market) }.exceptionOrNull()
            assertTrue(thrown is IllegalArgumentException, "market '$market' should be rejected")
        }
        assertTrue(runCatching { spec.copy(audience = "") }.exceptionOrNull() is IllegalArgumentException)
        assertTrue(runCatching { spec.copy(version = 0) }.exceptionOrNull() is IllegalArgumentException)
    }

    @Test
    fun `a non-Jordanian campaign cannot go live until eligibility is confirmed in writing`() {
        // The gate, in domain terms. This is not a UI convention that someone
        // can click past: a NONJO campaign simply cannot be activated until the
        // Department of Lands and Survey statement exists.
        val nonJordanian = spec.copy(track = Track.NONJO, market = "IRQ")
        assertFalse(nonJordanian.canActivate(nonJordanianEligibilityCleared = false))
        assertTrue(nonJordanian.canActivate(nonJordanianEligibilityCleared = true))
    }

    @Test
    fun `the gate blocks only the non-Jordanian track and nothing else`() {
        assertTrue(spec.canActivate(nonJordanianEligibilityCleared = false))
        assertTrue(spec.copy(track = Track.LOCAL, market = "JOR").canActivate(false))
    }
}
