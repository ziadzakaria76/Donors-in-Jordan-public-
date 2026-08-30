package com.gs3.marketingops.core.data.seed

import com.gs3.marketingops.campaigns.data.MarketBudgetEntity
import com.gs3.marketingops.compliance.data.ContractClaim
import com.gs3.marketingops.compliance.data.ContractClaimEntity
import com.gs3.marketingops.domain.budget.Gs3Budget
import com.gs3.marketingops.domain.inventory.Gs3Schedule
import com.gs3.marketingops.inventory.data.UnitEntity
import com.gs3.marketingops.outreach.data.MessageTemplateEntity
import com.gs3.marketingops.outreach.data.ObjectionEntity
import java.time.Instant

/**
 * What the database contains on first launch.
 *
 * The two halves of this file are different in kind, and it is worth being
 * explicit about which is which.
 *
 * **Units and budgets are derived, not typed.** They are read straight from
 * `Gs3Schedule` and `Gs3Budget` in `:domain`, which are themselves
 * cross-checked against `website/assets/js/data.js`. Re-typing fourteen prices
 * here would create a third copy that can disagree with the other two, and the
 * disagreement would surface as a client being quoted a price the website does
 * not show. A test asserts the seed matches the domain exactly.
 *
 * **Templates and objections are authored.** Arabic first, English derived from
 * it — and constrained by what the company is actually entitled to say.
 */
object Gs3Seed {

    fun units(): List<UnitEntity> =
        Gs3Schedule.apartments.map(UnitEntity.Companion::fromDomain)

    /**
     * Five rows, all expatriate.
     *
     * There were nine. IRQ, GULF, PSE and TEST were the non-Jordanian markets
     * and are gone with the track (DECISIONS.md → D-23). Because the seed
     * only inserts, deleting them here is not enough on its own to clear them
     * from a phone that already has them — `Gs3Database.MIGRATION_1_2` does
     * that.
     */
    fun marketBudgets(): List<MarketBudgetEntity> =
        Gs3Budget.externalTrackMarkets.map(MarketBudgetEntity.Companion::fromDomain)

    /** When the owner answered B-2. Fixed, so the seed is deterministic. */
    private val b2AnsweredAt: Instant = Instant.parse("2026-08-29T00:00:00Z")

    private val confirmedClaims = setOf(
        ContractClaim.FINISHING_SPECIFICATIONS_ANNEX,
        ContractClaim.QUARTERLY_PHOTOGRAPHIC_PROGRESS_REPORT,
    )

    /**
     * Both remaining contract claims ship confirmed.
     *
     * **B-2 was answered in part** (2026-08-29). The owner confirmed the signed
     * contract carries the finishing-specifications annex and the quarterly
     * photographic progress report, and did not confirm the delay penalty or
     * the two-year and ten-year warranty. On 2026-08-30 the owner removed those
     * two unconfirmed claims outright (D-30), so what is left is the confirmed
     * half.
     *
     * That means **every row this seeds is confirmed**, and the design that
     * exists to carry a partial answer is not carrying one at the moment. It
     * still earns its place: the next claim added starts unconfirmed, and the
     * row is what keeps it out of client text until someone reads the contract.
     *
     * No clause references were supplied, so [ContractClaimEntity.contractReference]
     * stays null on both. Worth filling in when someone next has the contract
     * open — nothing else records which clause these rest on.
     */
    fun contractClaims(): List<ContractClaimEntity> =
        ContractClaim.entries.map { claim ->
            if (claim in confirmedClaims) {
                ContractClaimEntity.confirmed(claim, at = b2AnsweredAt)
            } else {
                ContractClaimEntity.unverified(claim)
            }
        }

    /**
     * WhatsApp templates.
     *
     * Every one of these is *pre-filled text for a person to send*, never a
     * message the app sends by itself. A buyer weighing a six-figure purchase
     * can tell an automated message from a written one, and the automated one
     * costs more than it saves.
     *
     * Placeholders use the `{snake_case}` syntax `MessageTemplate` understands,
     * and only names from `MessageTemplate.UNIT_VARIABLES`. An unfilled
     * placeholder makes `render` return null rather than sending a client the
     * literal text "{price}".
     */
    fun messageTemplates(): List<MessageTemplateEntity> = listOf(
        MessageTemplateEntity(
            templateKey = "first_response",
            bodyAr = "أهلاً وسهلاً 👋\n" +
                "شكراً لتواصلك بخصوص مشروع جنرال شيرمان ٣ في مرج الحمام.\n" +
                "الشقة رقم {unit_number} مساحتها {area} م² وسعرها {price}.\n" +
                "تفاصيل الشقة والصور: {link}\n" +
                "بخدمتك لأي استفسار — {contact}",
            bodyEn = "Hello 👋\n" +
                "Thank you for your enquiry about General Sherman 3 in Marj Al-Hamam.\n" +
                "Apartment {unit_number} is {area} m² at {price}.\n" +
                "Details and photographs: {link}\n" +
                "Happy to answer any question — {contact}",
            trackKey = null,
            isEditable = true,
        ),
        MessageTemplateEntity(
            templateKey = "out_of_hours_acknowledgement",
            // The only template the app may send without a person, and it
            // promises nothing except that a human will follow. Sent outside
            // business hours so an enquiry is never met with silence; the SLA
            // engine still requires a human reply by 10:00 the next working day.
            bodyAr = "وصلنا استفسارك، شكراً لك.\n" +
                "فريق المبيعات خارج الدوام حالياً، وسيتواصل معك أول يوم عمل قبل الساعة ١٠:٠٠ صباحاً.",
            bodyEn = "We have received your enquiry, thank you.\n" +
                "The sales team is outside working hours; someone will contact you before 10:00 on the next working day.",
            trackKey = null,
            isEditable = false,
        ),
        MessageTemplateEntity(
            templateKey = "viewing_confirmation",
            bodyAr = "تم تثبيت موعد معاينة الشقة رقم {unit_number}.\n" +
                "الموقع: مرج الحمام — بالقرب من دوار الكتاب.\n" +
                "{link}\n" +
                "بانتظارك — {contact}",
            bodyEn = "Your viewing of apartment {unit_number} is confirmed.\n" +
                "Location: Marj Al-Hamam — near Al-Kitab Circle.\n" +
                "{link}\n" +
                "See you there — {contact}",
            trackKey = null,
            isEditable = true,
        ),
        MessageTemplateEntity(
            templateKey = "written_offer",
            bodyAr = "تجد أدناه العرض الخطّي للشقة رقم {unit_number}:\n" +
                "المساحة الداخلية {area} م² — المساحة الخارجية {external_area} م²\n" +
                "السعر {price}\n" +
                "{link}\n" +
                "العرض قابل للنقاش خلال المدة المتفق عليها — {contact}",
            bodyEn = "Here is the written offer for apartment {unit_number}:\n" +
                "Internal area {area} m² — external area {external_area} m²\n" +
                "Price {price}\n" +
                "{link}\n" +
                "The offer is open for discussion within the agreed period — {contact}",
            trackKey = null,
            isEditable = true,
        ),
        MessageTemplateEntity(
            templateKey = "external_track_update",
            // The ten-day update to expatriate clients. Its whole purpose is to
            // say something when there is nothing new, because silence across a
            // time zone reads as the project having gone quiet.
            bodyAr = "تحديث بخصوص مشروع جنرال شيرمان ٣:\n" +
                "الشقة رقم {unit_number} ما زالت متاحة.\n" +
                "{link}\n" +
                "إن أحببت ترتيب جولة مباشرة عبر الفيديو، أخبرني بالوقت المناسب لك — {contact}",
            bodyEn = "An update on General Sherman 3:\n" +
                "Apartment {unit_number} is still available.\n" +
                "{link}\n" +
                "If you would like a live video tour, tell me a time that suits you — {contact}",
            trackKey = "EXPAT",
            isEditable = true,
        ),
    )

    /**
     * The objection library.
     *
     * Written because the alternative is each salesperson inventing an answer
     * under pressure, and answers invented under pressure over-promise.
     *
     * One hard rule, enforced by a test rather than by memory:
     *
     * **Nothing guarantees an outcome that belongs to someone else.** Not a
     * government approval, not a market yield. `verifyStrings` blocks the worst
     * phrasings outright; these answers avoid the shape of the claim, not just
     * the words.
     *
     * There was a second rule — no unverified B-2 contract claim, so no delay
     * penalty and no warranty. D-30 removed both claims and the test that
     * enforced it. The answers below still avoid them, but that is now a
     * property of the text rather than something the build checks.
     *
     * What they *do* lean on is what the company already publishes on its own
     * website: the two street frontages, the named finishing specifications, the
     * schools and hospitals nearby. Those are checkable, which is what makes
     * them persuasive.
     */
    fun objections(): List<ObjectionEntity> = listOf(
        ObjectionEntity(
            objectionKey = "price_too_high",
            objectionAr = "السعر أعلى من مشاريع ثانية في المنطقة",
            objectionEn = "The price is higher than other projects in the area",
            responseAr = "المقارنة الأدقّ هي سعر المتر المربّع وليس سعر الشقة، لأن المساحات تختلف. " +
                "احسب معي: سعر متر هذه الشقة مقابل المشروع الذي تقارن به. " +
                "والفرق الثاني في التشطيبات المذكورة بالاسم — الحجر والبورسلان والأبواب والشبابيك — " +
                "وهي منشورة على موقع الشركة ويمكنك التحقق منها بنفسك.",
            responseEn = "The fairer comparison is price per square metre rather than price per apartment, " +
                "because the areas differ. Let us work it out together for this unit against the one you are " +
                "comparing it with. The second difference is the finishes, specified by name — the stone, the " +
                "porcelain, the doors and the windows — all published on the company's website, so you can check them yourself.",
            displayOrder = 1,
        ),
        ObjectionEntity(
            objectionKey = "location_far",
            objectionAr = "مرج الحمام بعيدة عليّ",
            objectionEn = "Marj Al-Hamam is too far for me",
            responseAr = "المشروع قريب من دوار الكتاب، وحوله مدارس وجامعات ومراكز صحية ومراكز تسوّق. " +
                "اسألني عن المسافة من المكان الذي تنطلق منه يومياً وسأحسبها معك بدل التقدير، " +
                "فغالباً تكون أقصر مما يبدو على الخريطة.",
            responseEn = "The project sits near Al-Kitab Circle, with schools, universities, health facilities and " +
                "shopping around it. Tell me where you travel from each day and we will work out the real journey " +
                "rather than estimate it — it is usually shorter than it looks on a map.",
            displayOrder = 2,
        ),
        ObjectionEntity(
            objectionKey = "payment_terms",
            objectionAr = "شروط الدفع لا تناسبني",
            objectionEn = "The payment terms do not suit me",
            responseAr = "أخبرني بالدفعة الأولى المريحة لك وبالمدة التي تفكّر بها، وسأعرضها على الإدارة. " +
                "وإن كان التمويل عن طريق البنك، يمكنني أن أحسب لك قسطاً استرشادياً الآن — " +
                "مع التنويه أن شروط التمويل الفعلية يحدّدها البنك وحده.",
            responseEn = "Tell me the down payment that works for you and the period you have in mind, and I will put " +
                "it to management. If you are financing through a bank I can calculate an indicative instalment now — " +
                "noting that the actual financing terms are set by the bank alone.",
            displayOrder = 3,
        ),
        ObjectionEntity(
            objectionKey = "finishing_quality",
            objectionAr = "كيف أتأكّد من جودة التشطيب؟",
            objectionEn = "How can I be sure of the finishing quality?",
            // Deliberately does not mention a finishing-specifications annex or
            // any warranty: both are B-2 claims, unverified against the signed
            // contract. It points instead at what is already published and at
            // what the buyer can see with their own eyes.
            responseAr = "المواصفات مذكورة بالاسم لا بالوصف العام — نوع الحجر ومقاس البورسلان ومصدر الأبواب والشبابيك — " +
                "وهي منشورة على موقع الشركة. وأفضل من ذلك أن تراها بنفسك: صور المدخل من التنفيذ الفعلي، " +
                "ويسعدني ترتيب زيارة للموقع لتعاين المواد على الطبيعة.",
            responseEn = "The specifications are named rather than described in general terms — the type of stone, the " +
                "size of the porcelain, the source of the doors and windows — and they are published on the company's " +
                "website. Better still, see them yourself: the entrance photographs are of the building as built, and " +
                "I would be glad to arrange a site visit so you can inspect the materials in person.",
            displayOrder = 4,
        ),
        ObjectionEntity(
            objectionKey = "delivery_timing",
            objectionAr = "متى التسليم، وماذا لو تأخّر؟",
            objectionEn = "When is delivery, and what if it is late?",
            // Deliberately still promises no delay penalty, though nothing
            // stops it any more: D-30 removed that claim and the guard that
            // banned the phrase. The text is unchanged because the reason for
            // it is unchanged -- nobody has read the signed contract and
            // confirmed a penalty is in it, and this answer is given to a buyer
            // weighing a six-figure purchase. What is offered instead is the
            // delivery date and a commitment to keep in touch, and the second
            // is backed by the app's own ten-day update rule, so it is a
            // promise the team is actually held to.
            responseAr = "أعطيك تاريخ التسليم المعتمد للمشروع خطّياً ضمن العرض. " +
                "وألتزم بإبقائك على اطّلاع بسير العمل أولاً بأول حتى لا تكون بعيداً عمّا يجري، " +
                "وخصوصاً إن كنت خارج الأردن. أما ما يترتّب على التأخير فيحدّده نصّ العقد، وتُراجعه قبل التوقيع.",
            responseEn = "I will give you the project's approved delivery date in writing as part of the offer, " +
                "and I will keep you up to date on progress as it happens so you are not left guessing — " +
                "particularly if you are outside Jordan. What follows from a delay is set by the text of the " +
                "contract, which you review before signing.",
            displayOrder = 5,
        ),
        ObjectionEntity(
            objectionKey = "rental_yield",
            objectionAr = "كم العائد الإيجاري المتوقّع؟",
            objectionEn = "What rental yield should I expect?",
            responseAr = "أستطيع أن أحسب لك نطاقاً تقديرياً بناءً على إيجارات مشابهة في المنطقة، " +
                "وأوضّح لك الافتراضات التي بُني عليها حتى تحكم عليها بنفسك. " +
                "وهو تقدير مبني على السوق، لا وعداً من الشركة.",
            responseEn = "I can work out an estimated range from comparable rents in the area and show you the " +
                "assumptions behind it so you can judge them yourself. It is an estimate based on the market, " +
                "not a promise from the company.",
            displayOrder = 6,
        ),
        ObjectionEntity(
            objectionKey = "registration_fees",
            objectionAr = "كم تبلغ رسوم التسجيل؟",
            objectionEn = "How much are the registration fees?",
            responseAr = "أحسبها لك الآن، مع التنويه أن الرسوم وضريبة بيع العقار تُحتسب على القيمة المقدَّرة " +
                "من دائرة الأراضي والمساحة وليس بالضرورة على سعر البيع، وأن النسب عرضة للتغيير. " +
                "وتساهم الشركة في جزء من الرسوم بحدّ أقصى متفق عليه — وهي مساهمة، لا إسقاط للرسوم.",
            responseEn = "I will calculate it for you now, noting that the fee and the property sale tax are " +
                "calculated on the value assessed by the Department of Lands and Survey, not necessarily on the sale " +
                "price, and that the rates are subject to change. The company contributes toward the fees up to an " +
                "agreed cap — a contribution, not a waiver.",
            displayOrder = 7,
        ),
        ObjectionEntity(
            objectionKey = "non_jordanian_eligibility",
            objectionAr = "أنا غير أردني — هل يحقّ لي التملّك؟",
            objectionEn = "I am not Jordanian — am I allowed to own?",
            // This answer stays although the non-Jordanian track has gone
            // (D-23), and it is rewritten rather than kept as it was.
            //
            // It stays because removing a track the company markets does not
            // stop the question being asked at a stand or on the phone, and the
            // objection library exists so that nobody has to invent an answer
            // under pressure — inventing one is exactly how an over-promise
            // gets made to the buyer the app is most exposed on.
            //
            // It is rewritten because the old text said the written statement
            // and the legal opinion "are being sought" and promised to pass on
            // the answer. B-1 came back no on 2026-08-29 and the owner chose to
            // drop the track rather than keep chasing it, so that sentence had
            // become a commitment nobody is working to. What replaces it
            // promises nothing, offers nothing, refuses nobody, and points at
            // the only two places that can actually answer.
            responseAr = "هذا سؤال تجيب عنه الجهات المختصّة وحدها، ولا أعطيك فيه رأياً شخصياً. " +
                "ولا يوجد لدينا اليوم كتاب خطّي من دائرة الأراضي والمساحة بخصوص تصنيف وحدات المشروع، " +
                "ولذلك لا أعدك بشيء في هذا الأمر، ولا نسوّق المشروع لغير الأردنيين ما دام الحال كذلك. " +
                "وإن أردت متابعة الموضوع، فدائرة الأراضي والمساحة ومحامٍ مرخّص هما المرجع الصحيح.",
            responseEn = "That is a question only the competent authorities can answer, and I will not give you a " +
                "personal opinion on it. We hold no written statement from the Department of Lands and Survey on " +
                "how this project's units are classified, so I will not promise you anything on it, and we are not " +
                "marketing the project to non-Jordanian buyers while that is the case. If you want to take it " +
                "further, the Department of Lands and Survey and a licensed lawyer are the right places to ask.",
            displayOrder = 8,
        ),
    )
}
