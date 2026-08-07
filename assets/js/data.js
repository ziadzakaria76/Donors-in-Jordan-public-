/* =============================================================================
   SITE CONTENT — this is the only file you need to edit to change what the
   site says or sells. Every text field is an object: { ar: "…", en: "…" }.

   PLACEHOLDER CONTENT: the company, its projects, the people quoted and all
   contact details below are invented for this build. Replace anything marked
   «REPLACE» before going live.
   ========================================================================== */

const COMPANY = {
  name: { ar: "شركة جنرال شيرمان للإسكان", en: "General Sherman Housing" },   // «REPLACE»
  short: { ar: "جنرال شيرمان", en: "General Sherman" },                              // «REPLACE»
  tagline: { ar: "نبني مستقبلك", en: "We build your future" },
  founded: null,                      // «REPLACE» — unverified, so no page states one
  intro: {
    ar: "شركة أردنية للتطوير العقاري متخصصة في الشقق السكنية الفاخرة في غرب عمّان، تجمع بين العمارة الهادئة والتشطيبات عالية الجودة والتسليم في موعده.",
    en: "A Jordanian residential developer specialising in luxury apartments across West Amman — restrained architecture, high-specification finishes, and delivery on schedule.",
  },
  phone: "+962 7 9073 0903",
  phoneHref: "+962790730903",
  whatsapp: "962790730903",           // same mobile as `phone` — change if WhatsApp is on another line
  email: "Mohammed.Zakaria90@hotmail.com",
  salesEmail: "Mohammed.Zakaria90@hotmail.com",   // one address for both for now
  domain: "https://generalshermanhousing.com",
                                      // this feeds canonical/og:url and the sitemap.
                                      // Kept in step with SITE in tools/build-pages.mjs
                                      // and with the CNAME file GitHub Pages reads.
  /* Deliberately blank. The footer's address line, the contact page's office
     row and the office map are all removed while these are empty; fill either
     one in and restore the markup (README → "Removed sections") to bring the
     office back. */
  address: { ar: "", en: "" },
  hours: {
    ar: "السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً",
    en: "Saturday – Thursday, 9:00 – 18:00",
  },
  mapQuery: "",
  /* Where forms go. Leave empty and every form hands the enquiry to WhatsApp
     with an email fallback — no backend required. Paste a Formspree/Web3Forms
     endpoint here and the forms POST to it instead. */
  formEndpoint: "",                   // «REPLACE» e.g. "https://formspree.io/f/xxxxxxx"
  registration: {                     // «REPLACE»
    ar: "سجل تجاري رقم ٢٠٠٩/‏٤٤١٧٢ — نقابة المقاولين الأردنيين",
    en: "Commercial registration 44172/2009 — Jordanian Construction Contractors Association",
  },
  /* No social accounts yet. When there are, add them here and restore the
     .socials list in the footer (README → "Removed sections"). */
  social: [],
  /* Track record. Empty because the figures that were here were invented for
     the build, and the site now carries the real name and logo. To bring the
     band back: add entries here and restore the stats <section> in index.html
     and about.html (see README → "Restoring the stats and testimonials"). */
  stats: [],
};

/* --------------------------------------------------------------- districts */

const DISTRICTS = {
  "marj-al-hamam": { ar: "مرج الحمام", en: "Marj Al-Hamam" },
};

/* ---------------------------------------------------------------- projects
   Each project carries its own schedule of units, stated one at a time as the
   sales brochure publishes them. Prices are stated, never calculated — real
   schedules do not follow a formula — and a sold unit carries no price,
   because the brochure publishes none.
   -------------------------------------------------------------------------- */

const PROJECTS = [
  {
    id: "sherman-2",
    name: { ar: "جنرال شيرمان ٢", en: "General Sherman 2" },
    district: "marj-al-hamam",
    status: "selling",
    image: "sherman2-exterior-day",
    address: {
      ar: "مرج الحمام — طريق ناعور، بعد كازية السلام",
      en: "Marj Al-Hamam — Naour Road, past the Al-Salam petrol station",
    },
    mapQuery: "Marj Al Hamam, Amman, Jordan",
    tagline: {
      ar: "ثلاث عشرة شقة في مرج الحمام، أربعٌ منها ما تزال متاحة",
      en: "Thirteen apartments in Marj Al-Hamam, four of them still available",
    },
    description: {
      ar: "يتميّز المشروع بموقعه الاستراتيجي الحيوي، حيث يوفّر إطلالة رائعة ويقع بالقرب من مجموعة من الخدمات الأساسية مثل المؤسسات التعليمية والمرافق الصحية، إضافةً إلى قربه من مراكز التسوق التي تتيح سهولة الوصول إلى احتياجات السكان اليومية. كما يبرز المشروع بفضل التشطيبات الفاخرة عالية الجودة التي توفّر راحة وفخامة.",
      en: "The building sits on a well-connected site with an open outlook, close to schools and universities, health facilities, and the shopping that covers daily needs. Its finishes are the other half of the argument: high-specification throughout, and specified by name.",
    },
    highlights: [
      { ar: "المشروع بالكامل حجر رويشد قاسي نخب أول، معزول بوليسترين", en: "Clad throughout in first-grade hard Ruwaished stone, fully polystyrene-insulated" },
      { ar: "الشقة بالكامل بورسلان، وأرضيات رخام للصالونات", en: "Porcelain throughout each apartment, with marble floors to the reception rooms" },
      { ar: "تدفئة غاز مركزي مركّبة من شركة جوغاز، وتأسيس نحاس للتكييف", en: "Central gas heating installed by JoGas, and copper pipework prepared for air conditioning" },
      { ar: "مصعد إيطالي من مصاعد استرا مكفول ٢٤ شهراً", en: "Italian Astra lift, guaranteed for 24 months" },
      { ar: "كراج ومستودع خاصّان لكل شقة", en: "A private garage bay and a private store for every apartment" },
      { ar: "أبواب أمان رئيسية تركية نخب أول، وأبواب داخلية خشب سويد بقشرة بلوط ودهان إيطالي", en: "First-grade Turkish security entrance doors; internal doors in Swedish timber with oak veneer and Italian lacquer" },
      { ar: "شبابيك ألمنيوم دبل جلاس بمقطع فلسطيني خاص وأباجورات كهربائية", en: "Double-glazed aluminium windows on a bespoke Palestinian profile, with electric shutters" },
      { ar: "أطقم حمامات معلّقة تركية ومغاسل بورسلان فاخرة", en: "Turkish wall-hung sanitaryware and porcelain basins" },
      { ar: "كاميرات مراقبة للعمارة وإنتركم كاميرا مع ACCESS POINT", en: "Building CCTV, and video intercom with access point" },
      { ar: "خاصية تغيير لون إضاءة السبوت: أبيض، صحراوي، كول", en: "Spot lighting switchable between white, warm and cool" },
      { ar: "خزّانا مياه مع مضخة", en: "Two water tanks with a pump" },
    ],
    amenities: ["elevator", "parking", "storage", "security", "generator"],
    /* Drive times as published in the project brochure. */
    nearby: [
      {
        group: { ar: "الخدمات التعليمية", en: "Education" },
        items: [
          { name: { ar: "مدارس كراون أكاديمي", en: "Crown Academy Schools" }, mins: 5 },
          { name: { ar: "مدارس كوفنتري", en: "Coventry Schools" }, mins: 6 },
          { name: { ar: "كلية لومينوس", en: "Luminus College" }, mins: 8 },
          { name: { ar: "جامعة البتراء", en: "University of Petra" }, mins: 11 },
        ],
      },
      {
        group: { ar: "المراكز الصحية", en: "Health" },
        items: [
          { name: { ar: "عيادات هيلث كير", en: "Health Care Clinics" }, mins: 5 },
          { name: { ar: "مستشفى الأندلس (قيد الإنشاء)", en: "Al-Andalus Hospital (under construction)" }, mins: 5 },
          { name: { ar: "مستشفى دار السلام", en: "Dar Al-Salam Hospital" }, mins: 13 },
          { name: { ar: "مستشفى الحمايدة", en: "Al-Hamaydeh Hospital" }, mins: 22 },
        ],
      },
      {
        group: { ar: "الخدمات ومراكز التسوّق", en: "Services and shopping" },
        items: [
          { name: { ar: "دوار الدلة — مرج الحمام", en: "Al-Dallah Circle — Marj Al-Hamam" }, mins: 7 },
          { name: { ar: "دوار الجندي — مرج الحمام", en: "Al-Jundi Circle — Marj Al-Hamam" }, mins: 7 },
          { name: { ar: "دوار عبدون", en: "Abdoun Circle" }, mins: 14 },
          { name: { ar: "الدوار السابع", en: "7th Circle" }, mins: 22 },
        ],
      },
    ],
    gallery: [
      "sherman2-exterior-day", "sherman2-exterior-dusk", "sherman2-lobby-1", "sherman2-lobby-2",
      "sherman2-entrance", "sherman2-living-1", "sherman2-living-2", "sherman2-interior-1",
      "sherman2-interior-3", "sherman2-interior-5", "sherman2-interior-7", "sherman2-lobby-3",
    ],
    /* Every apartment as listed in the brochure's schedule. Prices are per unit
       and do not follow a formula, so they are stated, not derived. */
    units: [
      { code: "0",  floor: -1, floorLabel: { ar: "طابق التسوية", en: "Lower ground floor" }, orientation: "south",     area: 190, outdoor: 120, beds: 3, baths: 4, type: "apartment", plan: "plan-a", price: 117000, status: "available" },
      { code: "1",  floor: 0,  floorLabel: { ar: "الطابق الأرضي", en: "Ground floor" },      orientation: "west",      area: 154, outdoor: 50,  beds: 3, baths: 3, type: "apartment", plan: "plan-b", price: 105000, status: "available" },
      { code: "2",  floor: 0,  floorLabel: { ar: "الطابق الأرضي", en: "Ground floor" },      orientation: "northeast", area: 152, outdoor: 110, beds: 3, baths: 3, type: "apartment", plan: "plan-c", status: "sold" },
      { code: "3",  floor: 0,  floorLabel: { ar: "الطابق الأرضي", en: "Ground floor" },      orientation: "southeast", area: 147, outdoor: 60,  beds: 3, baths: 3, type: "apartment", plan: "plan-d", status: "sold" },
      { code: "4",  floor: 1,  floorLabel: { ar: "الطابق الأول", en: "First floor" },        orientation: "west",      area: 154, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-e", status: "sold" },
      { code: "5",  floor: 1,  floorLabel: { ar: "الطابق الأول", en: "First floor" },        orientation: "northeast", area: 152, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-f", price: 88000, status: "available" },
      { code: "6",  floor: 1,  floorLabel: { ar: "الطابق الأول", en: "First floor" },        orientation: "southeast", area: 147, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-g", status: "sold" },
      { code: "7",  floor: 2,  floorLabel: { ar: "الطابق الثاني", en: "Second floor" },      orientation: "west",      area: 154, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-e", status: "sold" },
      { code: "8",  floor: 2,  floorLabel: { ar: "الطابق الثاني", en: "Second floor" },      orientation: "northeast", area: 152, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-f", status: "sold" },
      { code: "9",  floor: 2,  floorLabel: { ar: "الطابق الثاني", en: "Second floor" },      orientation: "southeast", area: 147, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-g", status: "sold" },
      { code: "10", floor: 3,  floorLabel: { ar: "الطابق الثالث مع روف", en: "Third floor with roof" }, orientation: "west",      area: 190, outdoor: 89, beds: 3, baths: 3, type: "roof", plan: "plan-h", status: "sold" },
      { code: "11", floor: 3,  floorLabel: { ar: "الطابق الثالث", en: "Third floor" },       orientation: "northeast", area: 152, outdoor: 0,   beds: 3, baths: 3, type: "apartment", plan: "plan-f", price: 88000, status: "available" },
      { code: "12", floor: 3,  floorLabel: { ar: "الطابق الثالث مع روف", en: "Third floor with roof" }, orientation: "southeast", area: 181, outdoor: 89, beds: 3, baths: 3, type: "roof", plan: "plan-i", status: "sold" },
    ],
  },
  {
    id: "sherman-1",
    name: { ar: "جنرال شيرمان ١", en: "General Sherman 1" },
    district: "marj-al-hamam",
    status: "delivered",
    image: "sherman1-1",
    tagline: { ar: "مشروعنا السابق، مُسلَّم ومسكون", en: "Our previous scheme, delivered and occupied" },
    description: {
      ar: "المشروع الأول لشركة جنرال شيرمان للإسكان، وقد سُلِّم بالكامل. تفاصيل المشروع ووحداته متاحة عند الطلب.",
      en: "General Sherman Housing's first scheme, delivered in full. Details are available on request.",
    },
    gallery: ["sherman1-1", "sherman1-2", "sherman1-3", "sherman1-4"],
    units: [],
  },
  {
    id: "sherman-3",
    name: { ar: "جنرال شيرمان ٣", en: "General Sherman 3" },
    district: "marj-al-hamam",
    status: "upcoming",
    image: "sherman3-1",
    tagline: { ar: "مشروعنا القادم — التصاميم جاهزة", en: "Our next scheme — designs complete" },
    description: {
      ar: "المشروع القادم لشركة جنرال شيرمان للإسكان. الصور المعروضة تصاميم ثلاثية الأبعاد للمشروع. للاستفسار عن مواعيد الطرح والأسعار تواصل معنا.",
      en: "The next General Sherman Housing scheme. The images shown are 3D design studies. Contact us about release dates and pricing.",
    },
    gallery: ["sherman3-1", "sherman3-2", "sherman3-3", "sherman3-4"],
    units: [],
  },
];

/* ---------------------------------------------------------------- amenities */

const AMENITIES = {
  gym: { ar: "نادٍ رياضي", en: "Gym" },
  pool: { ar: "مسبح", en: "Swimming pool" },
  reception: { ar: "استقبال ٢٤ ساعة", en: "24-hour reception" },
  generator: { ar: "مولّد كهربائي", en: "Standby generator" },
  parking: { ar: "مواقف مغطّاة", en: "Covered parking" },
  security: { ar: "حراسة ومراقبة", en: "Security and CCTV" },
  elevator: { ar: "مصاعد", en: "Lifts" },
  storage: { ar: "مستودع خاص", en: "Private storage" },
  garden: { ar: "حديقة", en: "Landscaped garden" },
  playground: { ar: "منطقة ألعاب", en: "Children's play area" },
};

/* ------------------------------------------------------------ testimonials */

/* Empty for the same reason: the quotes here were invented. Add real,
   permissioned quotes and restore the section markup to bring it back. */
const TESTIMONIALS = [];

/* ---------------------------------------------------------------- process */

const PROCESS = [
  {
    step: "01",
    title: { ar: "زيارة الموقع", en: "Visit the site" },
    body: { ar: "نرافقك في جولة على المشروع والوحدة التي تهمّك، ونشرح مراحل التنفيذ على الطبيعة.", en: "We walk you through the project and the specific unit, and explain the construction stage on site." },
  },
  {
    step: "02",
    title: { ar: "اختيار الوحدة والخطة", en: "Choose the unit and plan" },
    body: { ar: "نراجع معك المخططات والمساحات والأسعار، ونحدد خطة الدفع الأنسب لوضعك.", en: "We go through layouts, areas and pricing together, and settle on the payment plan that fits you." },
  },
  {
    step: "03",
    title: { ar: "توقيع العقد", en: "Sign the contract" },
    body: { ar: "عقد موثّق يحدد المواصفات وموعد التسليم والغرامة في حال التأخير.", en: "A registered contract setting out the specification, the handover date, and the penalty if we are late." },
  },
  {
    step: "04",
    title: { ar: "التسليم والضمان", en: "Handover and warranty" },
    body: { ar: "تسليم مع كشف فحص مشترك، وضمان سنتين على التشطيبات وعشر سنوات على الهيكل الإنشائي.", en: "Handover with a joint inspection report, a two-year finishes warranty and ten years on the structure." },
  },
];

/* -------------------------------------------------------------------- FAQ */

const FAQS = [
  {
    q: { ar: "هل يمكن لغير الأردنيين تملّك شقة؟", en: "Can non-Jordanians buy an apartment?" },
    a: {
      ar: "نعم. يستطيع مواطنو الدول العربية والأجانب التملّك في الأردن بموافقة من رئاسة الوزراء، ونتولى نحن تجهيز المعاملة ومتابعتها. المدة المعتادة بين شهرين وأربعة أشهر.",
      en: "Yes. Arab and foreign nationals may own property in Jordan subject to Cabinet approval, and we prepare and follow up the application for you. It usually takes two to four months.",
    },
  },
  {
    q: { ar: "ما الذي يشمله السعر المعلن؟", en: "What does the quoted price include?" },
    a: {
      ar: "السعر يشمل الوحدة بمساحتها الصافية وحصتها من المساحات المشتركة، والتشطيبات المذكورة في العقد، وموقف السيارة والمستودع. لا يشمل رسوم التسجيل الحكومية إلا إذا نُصّ على ذلك في خطة الدفع.",
      en: "The price covers the unit's net area and its share of common areas, the finishes listed in the contract, the parking bay and the store. Government registration fees are excluded unless your payment plan states otherwise.",
    },
  },
  {
    q: { ar: "هل يمكن تعديل التشطيبات أو التوزيع الداخلي؟", en: "Can finishes or the internal layout be changed?" },
    a: {
      ar: "يمكن تعديل التشطيبات ومواد الأرضيات والمطبخ قبل مرحلة معينة من التنفيذ. تعديل الجدران الداخلية غير الإنشائية ممكن أيضاً بموافقة المهندس المشرف وبفارق تكلفة يُحتسب مسبقاً.",
      en: "Finishes, flooring and kitchen specifications can be changed up to a defined construction stage. Non-structural internal walls can also be adjusted with the supervising engineer's approval, at a cost difference agreed in advance.",
    },
  },
  {
    q: { ar: "ما هي الضمانات بعد التسليم؟", en: "What warranties apply after handover?" },
    a: {
      ar: "سنتان على التشطيبات والأعمال الكهربائية والميكانيكية، وعشر سنوات على الهيكل الإنشائي، إضافةً إلى فريق صيانة يستجيب خلال ٤٨ ساعة في السنة الأولى.",
      en: "Two years on finishes and on electrical and mechanical works, ten years on the structure, plus a maintenance team that responds within 48 hours during the first year.",
    },
  },
  {
    q: { ar: "هل يمكن الشراء بغرض الاستثمار والتأجير؟", en: "Can I buy purely to rent out?" },
    a: {
      ar: "نعم، وعدد من ملّاكنا يفعلون ذلك. نستطيع تزويدك ببيانات الإيجارات الفعلية في المنطقة وربطك بشركة إدارة أملاك إذا رغبت.",
      en: "Yes, and a number of our owners do. We can share actual rental figures for the area and introduce you to a property management company if you want one.",
    },
  },
];

/* ------------------------------------------------------- derived inventory */

const UNIT_STATUS = { available: "available", reserved: "reserved", sold: "sold" };

/**
 * Expand each project's units into the flat list the site works with.
 *
 * Real schedules do not follow a formula — in General Sherman 2 the same
 * 152 m² layout is 88,000 on the first floor and 88,000 again on the third,
 * while a 190 m² lower-ground unit is 117,000 — so prices are stated per unit
 * rather than derived from a rate and a floor premium. A sold unit carries no
 * price at all, because the brochure does not publish one.
 */
function buildUnits() {
  const units = [];
  for (const p of PROJECTS) {
    for (const u of p.units || []) {
      units.push({
        ...u,
        id: `${p.id}-${u.code}`,
        projectId: p.id,
        district: p.district,
        outdoor: u.outdoor ?? 0,
        price: u.price ?? null,
      });
    }
  }
  return units;
}

const UNITS = buildUnits();

const UNIT_TYPES = {
  apartment: { ar: "شقة", en: "Apartment" },
  roof: { ar: "شقة مع روف", en: "Apartment with roof terrace" },
};

const ORIENTATIONS = {
  north: { ar: "شمالية", en: "North facing" },
  south: { ar: "جنوبية", en: "South facing" },
  east: { ar: "شرقية", en: "East facing" },
  west: { ar: "غربية", en: "West facing" },
  northeast: { ar: "شمالية شرقية", en: "North-east facing" },
  southeast: { ar: "جنوبية شرقية", en: "South-east facing" },
};

const PROJECT_STATUS = {
  selling: { ar: "متاح للبيع", en: "Now selling" },
  delivered: { ar: "مُسلَّم", en: "Delivered" },
  upcoming: { ar: "مشروع قادم", en: "Coming soon" },
  soldout: { ar: "بيعت بالكامل", en: "Fully sold" },
};


const DATA = {
  COMPANY, DISTRICTS, PROJECTS, UNITS, AMENITIES, TESTIMONIALS,
  PROCESS, FAQS, UNIT_TYPES, ORIENTATIONS, PROJECT_STATUS,
};

if (typeof window !== "undefined") window.DATA = DATA;
if (typeof module !== "undefined") module.exports = DATA;
