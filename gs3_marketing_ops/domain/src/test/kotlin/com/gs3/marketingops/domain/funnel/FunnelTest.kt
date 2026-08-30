package com.gs3.marketingops.domain.funnel

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class FunnelTest {

    @Test
    fun `the overall funnel projects the strategy's own numbers`() {
        val projection = FunnelModel.OVERALL.project()
        assertEquals(900, projection.rawLeads)
        assertEquals(315, projection.qualified)
        assertEquals(95, projection.viewings)
        assertEquals(52, projection.offers)
        assertEquals(11, projection.contracts)
    }

    @Test
    fun `the external funnel projects three units from a hundred and sixty leads`() {
        // The strategy's own figures. A 2026-08-29 decision briefly derived
        // the lead count from the budget at 45 JOD each; that assumption is
        // removed, so these five
        // numbers stand on their own again and nothing in the app converts
        // money into leads.
        val projection = FunnelModel.EXTERNAL.project()
        assertEquals(160, projection.rawLeads)
        assertEquals(48, projection.qualified)
        assertEquals(17, projection.viewings)
        assertEquals(3, projection.contracts)
    }

    @Test
    fun `each stage is taken from the rounded stage before it`() {
        // 315 x 0.30 = 94.5, which the plan calls 95 -- and 95 is then what the
        // offer count comes from. Carrying the half through instead gives 51.975
        // offers and quietly disagrees with the document the team works to.
        val projection = FunnelModel.OVERALL.project()
        val unrounded = BigDecimal("315").multiply(BigDecimal("0.30")).multiply(BigDecimal("0.55"))
        assertEquals(52, projection.offers)
        assertTrue(unrounded < BigDecimal("52"))
    }

    @Test
    fun `the external track carries its share of the eleven units`() {
        val external = FunnelModel.EXTERNAL.project().contracts
        val overall = FunnelModel.OVERALL.project().contracts
        assertEquals(3, external)
        assertEquals(11, overall)
        val share = BigDecimal(external).divide(BigDecimal(overall), 4, java.math.RoundingMode.HALF_UP)
        assertTrue(share >= BigDecimal("0.27"))
    }

    @Test
    fun `expat is external, local is not, and there is no third track`() {
        assertTrue(Track.EXPAT.isExternal)
        assertFalse(Track.LOCAL.isExternal)

        // D-23: the non-Jordanian track was deleted, not disabled. Asserted
        // structurally so that reintroducing the enum value fails here and
        // sends whoever did it to the decision rather than letting a track with
        // no gate behind it quietly reappear.
        assertEquals(listOf("LOCAL", "EXPAT"), Track.entries.map { it.name })
    }

    @Test
    fun `target state colours the dashboard`() {
        assertEquals(TargetState.ON_TARGET, FunnelTargets.stateOf(actual = 95, target = 100))
        assertEquals(TargetState.BEHIND, FunnelTargets.stateOf(actual = 75, target = 100))
        assertEquals(TargetState.AT_RISK, FunnelTargets.stateOf(actual = 40, target = 100))
        assertEquals(TargetState.ON_TARGET, FunnelTargets.stateOf(actual = 120, target = 100))
        // A zero target is not a failure to hit it.
        assertEquals(TargetState.ON_TARGET, FunnelTargets.stateOf(actual = 0, target = 0))
    }
}

class DiagnosisTest {

    private val benchmarks = DiagnosisBenchmarks(
        minimumImpressions = 10_000,
        enquiryRate = BigDecimal("0.01"),
        viewingRate = BigDecimal("0.30"),
        contractRate = BigDecimal("0.20"),
    )

    @Test
    fun `too few impressions is a targeting problem, and price is not the answer`() {
        val result = FunnelDiagnosis.diagnose(
            ChannelPerformance(impressions = 500, enquiries = 0, viewings = 0, contracts = 0),
            benchmarks,
        )
        assertEquals(Diagnosis.TARGETING_OR_BUDGET, result)
        assertFalse(result.priceIsACandidate)
    }

    @Test
    fun `low impressions is tested first, or everything downstream lies`() {
        // With almost no reach every later count is low too. A checker that read
        // the stages in the order the strategy lists them would confidently
        // diagnose a pricing problem on a campaign nobody was shown.
        val barelyRan = ChannelPerformance(impressions = 100, enquiries = 0, viewings = 0, contracts = 0)
        assertEquals(Diagnosis.TARGETING_OR_BUDGET, FunnelDiagnosis.diagnose(barelyRan, benchmarks))
    }

    @Test
    fun `plenty of impressions and no enquiries points at price or imagery`() {
        val result = FunnelDiagnosis.diagnose(
            ChannelPerformance(impressions = 100_000, enquiries = 20, viewings = 6, contracts = 1),
            benchmarks,
        )
        assertEquals(Diagnosis.PRICING_OR_IMAGERY, result)
        assertTrue(result.priceIsACandidate, "this is the one case where price is even a candidate")
    }

    @Test
    fun `enquiries that never become viewings is a speed or copy problem`() {
        val result = FunnelDiagnosis.diagnose(
            ChannelPerformance(impressions = 100_000, enquiries = 1_000, viewings = 20, contracts = 4),
            benchmarks,
        )
        assertEquals(Diagnosis.RESPONSE_SPEED_OR_COPY, result)
        assertFalse(result.priceIsACandidate)
    }

    @Test
    fun `viewings that never become contracts is product, terms or competition`() {
        val result = FunnelDiagnosis.diagnose(
            ChannelPerformance(impressions = 100_000, enquiries = 1_000, viewings = 300, contracts = 5),
            benchmarks,
        )
        assertEquals(Diagnosis.PRODUCT_TERMS_OR_COMPETITION, result)
        assertFalse(result.priceIsACandidate)
    }

    @Test
    fun `a healthy channel is left alone`() {
        val result = FunnelDiagnosis.diagnose(
            ChannelPerformance(impressions = 100_000, enquiries = 1_000, viewings = 300, contracts = 60),
            benchmarks,
        )
        assertEquals(Diagnosis.ON_TRACK, result)
    }

    @Test
    fun `only one of the five diagnoses ever puts price on the table`() {
        // The app must discourage cutting price to solve a non-price problem.
        assertEquals(1, Diagnosis.entries.count { it.priceIsACandidate })
    }
}
