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
  tagline: { ar: "سكنٌ يليق بمقامك", en: "Homes with standing" },
  founded: 2009,
  intro: {
    ar: "شركة أردنية للتطوير العقاري متخصصة في الشقق السكنية الفاخرة في غرب عمّان، تجمع بين العمارة الهادئة والتشطيبات عالية الجودة والتسليم في موعده.",
    en: "A Jordanian residential developer specialising in luxury apartments across West Amman — restrained architecture, high-specification finishes, and delivery on schedule.",
  },
  phone: "+962 6 552 0176",           // «REPLACE»
  phoneHref: "+96265520176",
  whatsapp: "962790000176",           // «REPLACE» — digits only, no + or spaces
  email: "info@generalsherman.jo",        // «REPLACE»
  salesEmail: "sales@generalsherman.jo",  // «REPLACE»
  domain: "https://www.generalsherman.jo",// «REPLACE»
  address: {
    ar: "شارع عبد الله غوشة، مبنى ٤٦، الطابق الثالث، عمّان ١١١٩٤، الأردن",
    en: "46 Abdullah Ghosheh Street, 3rd Floor, Amman 11194, Jordan",
  },
  hours: {
    ar: "السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً",
    en: "Saturday – Thursday, 9:00 – 18:00",
  },
  mapQuery: "Abdullah Ghosheh Street, Amman, Jordan",
  /* Where forms go. Leave empty and every form hands the enquiry to WhatsApp
     with an email fallback — no backend required. Paste a Formspree/Web3Forms
     endpoint here and the forms POST to it instead. */
  formEndpoint: "",                   // «REPLACE» e.g. "https://formspree.io/f/xxxxxxx"
  registration: {
    ar: "سجل تجاري رقم ٢٠٠٩/‏٤٤١٧٢ — نقابة المقاولين الأردنيين",
    en: "Commercial registration 44172/2009 — Jordanian Construction Contractors Association",
  },
  social: [
    { id: "instagram", label: "Instagram", href: "#" },  // «REPLACE»
    { id: "facebook", label: "Facebook", href: "#" },    // «REPLACE»
    { id: "linkedin", label: "LinkedIn", href: "#" },    // «REPLACE»
    { id: "youtube", label: "YouTube", href: "#" },      // «REPLACE»
  ],
  stats: [
    { value: "16", label: { ar: "مشروعاً مُسلَّماً", en: "Projects delivered" } },
    { value: "480+", label: { ar: "وحدة سكنية", en: "Homes handed over" } },
    { value: "17", label: { ar: "عاماً في السوق الأردني", en: "Years in the Jordanian market" } },
    { value: "98%", label: { ar: "تسليم في موعده", en: "Delivered on schedule" } },
  ],
};

/* --------------------------------------------------------------- districts */

const DISTRICTS = {
  abdoun: { ar: "عبدون", en: "Abdoun" },
  "deir-ghbar": { ar: "دير غبار", en: "Deir Ghbar" },
  khalda: { ar: "خلدا", en: "Khalda" },
  "um-uthaina": { ar: "أم أذينة", en: "Um Uthaina" },
  rabieh: { ar: "الرابية", en: "Rabieh" },
};

/* ---------------------------------------------------------------- projects
   Units are not listed one by one. Each project declares its floors and its
   unit lines (A, B, C …) — the layout that repeats on every floor, exactly how
   these buildings are actually planned and priced. `sold` and `reserved` hold
   the exceptions, written as "<floor>-<line>", floor 0 being the ground floor.

   Price = area × pricePerM2 × (1 + floorPremium × floor), rounded to JOD 500.
   -------------------------------------------------------------------------- */

const PROJECTS = [
  {
    id: "residence-76",
    name: { ar: "ريزيدنس ٧٦", en: "Residence 76" },
    district: "abdoun",
    status: "ready",
    image: "residence76",
    year: 2025,
    delivery: { ar: "جاهز للسكن", en: "Ready to move in" },
    address: { ar: "شارع الأميرة بسمة، عبدون الشمالي", en: "Princess Basma Street, North Abdoun" },
    mapQuery: "Abdoun, Amman, Jordan",
    tagline: {
      ar: "أربعٌ وعشرون شقة فوق أهدأ شوارع عبدون",
      en: "Twenty-four apartments above Abdoun's quietest street",
    },
    description: {
      ar: "مبنى سكني من ثمانية طوابق صُمِّم حول فناء داخلي يفتح كل شقة على واجهتين، فيدخل الضوء من الشرق صباحاً ومن الغرب عند الغروب. الواجهات من حجر البازلت الأردني والزجاج المعزول حرارياً، والمداخل بارتفاع طابقين مع استقبال على مدار الساعة. المشروع مُسلَّم بالكامل ومسكون منذ ربيع ٢٠٢٥.",
      en: "An eight-storey building planned around an internal courtyard, so every apartment opens onto two elevations — morning light from the east, evening light from the west. Elevations are Jordanian basalt and thermally broken glazing; the lobby is double height with 24-hour reception. Delivered and occupied since spring 2025.",
    },
    highlights: [
      { ar: "تشطيب كامل مع مطابخ إيطالية مركّبة", en: "Fully finished with fitted Italian kitchens" },
      { ar: "تدفئة أرضية مائية في كامل الشقة", en: "Hydronic underfloor heating throughout" },
      { ar: "موقفان مغطّيان لكل شقة ومستودع خاص", en: "Two covered parking bays and a private store per home" },
      { ar: "مولّد كهربائي يغطي المبنى بالكامل", en: "Standby generator covering the whole building" },
    ],
    amenities: ["gym", "reception", "generator", "parking", "security", "elevator", "storage", "garden"],
    floors: 8,
    groundFloorIsGarden: true,
    pricePerM2: 1450,
    floorPremium: 0.022,
    lines: [
      { code: "A", beds: 4, baths: 4, area: 292, type: "apartment", plan: "plan-4br", orientation: "west", balcony: 34 },
      { code: "B", beds: 3, baths: 3, area: 214, type: "apartment", plan: "plan-3br", orientation: "east", balcony: 22 },
      { code: "C", beds: 3, baths: 3, area: 196, type: "apartment", plan: "plan-3br", orientation: "north", balcony: 18 },
    ],
    sold: ["0-A", "0-B", "1-A", "1-B", "1-C", "2-B", "2-C", "3-A", "3-C", "4-A", "4-B", "5-C", "6-A", "7-A", "7-B"],
    reserved: ["2-A", "5-A"],
    plans: ["early", "handover", "bank"],
    gallery: ["project-residence76", "gallery-interior-1", "gallery-facade-1", "gallery-courtyard-1"],
  },
  {
    id: "the-crescent",
    name: { ar: "ذا كريسنت", en: "The Crescent" },
    district: "deir-ghbar",
    status: "construction",
    image: "crescent",
    year: 2028,
    delivery: { ar: "التسليم: الربع الثاني ٢٠٢٨", en: "Delivery: Q2 2028" },
    address: { ar: "شارع الملكة رانيا الفرعي، دير غبار", en: "Off Queen Rania Street, Deir Ghbar" },
    mapQuery: "Deir Ghbar, Amman, Jordan",
    tagline: {
      ar: "أكبر مشاريعنا: أربعون شقة على منحدر دير غبار",
      en: "Our largest scheme: forty apartments on the Deir Ghbar slope",
    },
    description: {
      ar: "يستفيد المشروع من انحدار الأرض ليمنح كل طابق إطلالة مفتوحة على وادي دير غبار دون أن يحجب أحدهم الآخر. عشرة طوابق فوق طابقي مواقف، بأربعة نماذج سكنية تبدأ من شقق الغرفتين المناسبة للأزواج الشابين وتصل إلى شقق الثلاث غرف العائلية. العمل الإنشائي مكتمل حتى الطابق السادس.",
      en: "The scheme uses the fall of the site so that every floor keeps an open view over the Deir Ghbar valley rather than the building below it. Ten residential storeys above two parking levels, in four layouts — from two-bedroom apartments suited to younger couples up to family three-bedrooms. Structure is complete to the sixth floor.",
    },
    highlights: [
      { ar: "إطلالة مفتوحة على الوادي من كل طابق", en: "Open valley view from every floor" },
      { ar: "طابقا مواقف تحت الأرض", en: "Two levels of underground parking" },
      { ar: "نادٍ رياضي ومسبح مشترك للسكان", en: "Residents' gym and shared pool" },
      { ar: "عزل حراري وصوتي بمواصفات أوروبية", en: "Thermal and acoustic insulation to European specification" },
    ],
    amenities: ["gym", "pool", "reception", "generator", "parking", "security", "elevator", "playground"],
    floors: 10,
    groundFloorIsGarden: true,
    pricePerM2: 1080,
    floorPremium: 0.018,
    lines: [
      { code: "A", beds: 3, baths: 3, area: 232, type: "apartment", plan: "plan-3br", orientation: "west", balcony: 26 },
      { code: "B", beds: 2, baths: 2, area: 158, type: "apartment", plan: "plan-2br", orientation: "west", balcony: 16 },
      { code: "C", beds: 2, baths: 2, area: 146, type: "apartment", plan: "plan-2br", orientation: "east", balcony: 14 },
      { code: "D", beds: 3, baths: 3, area: 205, type: "apartment", plan: "plan-3br", orientation: "east", balcony: 20 },
    ],
    sold: ["0-B", "0-C", "1-B", "1-C", "2-C", "3-B", "4-D", "5-B", "5-C"],
    reserved: ["1-A", "2-A", "3-D", "6-B"],
    plans: ["early", "handover", "bank"],
    gallery: ["project-crescent", "gallery-facade-2", "gallery-interior-2", "gallery-skyline-1"],
  },
  {
    id: "bayt-al-sarw",
    name: { ar: "بيت السرو", en: "Bayt Al Sarw" },
    district: "khalda",
    status: "construction",
    image: "sarw",
    year: 2027,
    delivery: { ar: "التسليم: الربع الرابع ٢٠٢٧", en: "Delivery: Q4 2027" },
    address: { ar: "شارع وصفي التل الفرعي، خلدا", en: "Off Wasfi Al-Tal Street, Khalda" },
    mapQuery: "Khalda, Amman, Jordan",
    tagline: {
      ar: "ثمانية عشر بيتاً عائلياً بين أشجار السرو",
      en: "Eighteen family homes among the cypress trees",
    },
    description: {
      ar: "مشروع هادئ من ستة طوابق في قلب خلدا، صُمِّم لعائلات تبحث عن مساحة حقيقية قرب المدارس والخدمات. حافظنا على صفّ أشجار السرو القائم على حدود الأرض وبنينا حوله، فصار فاصلاً طبيعياً عن الشارع. التوزيع الداخلي يفصل جناح النوم عن مساحات الاستقبال، بمدخل خدمة مستقل لكل شقة.",
      en: "A quiet six-storey building in the middle of Khalda, planned for families who want genuine space near schools and services. We kept the existing row of cypress trees on the boundary and built around it, so it screens the building from the street. Internally, the sleeping wing is separated from the reception rooms, and every apartment keeps its own service entrance.",
    },
    highlights: [
      { ar: "مدخل خدمة مستقل لكل شقة", en: "Separate service entrance for every apartment" },
      { ar: "غرفة خادمة بحمّام مستقل", en: "Maid's room with its own bathroom" },
      { ar: "قرب المدارس الدولية ومراكز التسوق", en: "Minutes from international schools and retail" },
      { ar: "خزانات مياه مستقلة لكل وحدة", en: "Independent water tanks per unit" },
    ],
    amenities: ["reception", "generator", "parking", "security", "elevator", "storage", "playground", "garden"],
    floors: 6,
    groundFloorIsGarden: true,
    pricePerM2: 890,
    floorPremium: 0.016,
    lines: [
      { code: "A", beds: 3, baths: 3, area: 188, type: "apartment", plan: "plan-3br", orientation: "south", balcony: 20 },
      { code: "B", beds: 3, baths: 2, area: 175, type: "apartment", plan: "plan-3br", orientation: "north", balcony: 16 },
      { code: "C", beds: 2, baths: 2, area: 142, type: "apartment", plan: "plan-2br", orientation: "west", balcony: 12 },
    ],
    sold: ["0-A", "0-C", "1-B", "2-A", "3-C"],
    reserved: ["1-A", "4-B"],
    plans: ["early", "handover", "bank"],
    gallery: ["project-sarw", "gallery-interior-3", "gallery-facade-3", "gallery-courtyard-2"],
  },
  {
    id: "alto",
    name: { ar: "ألتو", en: "Alto" },
    district: "um-uthaina",
    status: "ready",
    image: "alto",
    year: 2024,
    delivery: { ar: "جاهز للسكن", en: "Ready to move in" },
    address: { ar: "شارع عبد الرحيم الحاج محمد، أم أذينة", en: "Abdul Rahim Al-Haj Mohammad Street, Um Uthaina" },
    mapQuery: "Um Uthaina, Amman, Jordan",
    tagline: {
      ar: "مبنى بوتيك من عشر شقق — تبقّت وحدتان",
      en: "A ten-apartment boutique building — two homes remain",
    },
    description: {
      ar: "أصغر مشاريعنا وأكثرها خصوصية: خمسة طوابق بشقتين فقط في كل طابق، لكل منهما مصعد خاص يفتح داخل الشقة. التشطيبات من البلوط الطبيعي والرخام الأردني، والمطابخ مصنوعة حسب الطلب. سُلِّم المشروع في ٢٠٢٤ وبيعت ثماني وحدات منه.",
      en: "Our smallest and most private building: five floors with only two apartments each, both served by a lift that opens directly into the home. Finishes are natural oak and Jordanian marble, with kitchens made to order. Delivered in 2024, with eight of the ten homes now sold.",
    },
    highlights: [
      { ar: "مصعد خاص يفتح داخل الشقة", en: "Private lift opening into the apartment" },
      { ar: "شقتان فقط في كل طابق", en: "Only two apartments per floor" },
      { ar: "مطابخ مصنوعة حسب الطلب", en: "Made-to-order kitchens" },
      { ar: "على بعد دقائق من دوار الواحة", en: "Minutes from Al-Waha Circle" },
    ],
    amenities: ["reception", "generator", "parking", "security", "elevator", "storage"],
    floors: 5,
    groundFloorIsGarden: false,
    pricePerM2: 1180,
    floorPremium: 0.025,
    lines: [
      { code: "A", beds: 2, baths: 2, area: 152, type: "apartment", plan: "plan-2br", orientation: "east", balcony: 14 },
      { code: "B", beds: 3, baths: 3, area: 198, type: "apartment", plan: "plan-3br", orientation: "west", balcony: 24 },
    ],
    sold: ["0-A", "0-B", "1-A", "1-B", "2-B", "3-A", "3-B", "4-A"],
    reserved: [],
    topFloorIsPenthouse: true,
    plans: ["handover", "bank"],
    gallery: ["project-alto", "gallery-interior-2", "gallery-skyline-2", "gallery-facade-1"],
  },
  {
    id: "rabieh-gardens",
    name: { ar: "حدائق الرابية", en: "Rabieh Gardens" },
    district: "rabieh",
    status: "construction",
    image: "rabieh",
    year: 2027,
    delivery: { ar: "التسليم: الربع الأول ٢٠٢٧", en: "Delivery: Q1 2027" },
    address: { ar: "شارع الأمير هاشم، الرابية", en: "Prince Hashem Street, Rabieh" },
    mapQuery: "Rabieh, Amman, Jordan",
    tagline: {
      ar: "شقق بحدائق خاصة ودوبلكسات على السطح",
      en: "Garden apartments below, roof duplexes above",
    },
    description: {
      ar: "أربعة طوابق فقط على أرض واسعة، ما سمح بتخصيص حديقة خاصة لكل شقة أرضية ودوبلكس بتراس مفتوح في الطابق الأخير. المساحات المشتركة تضم مسبحاً وممشى بين الأشجار المعمّرة التي حافظنا عليها. مناسب لمن يريد مساحة خارجية حقيقية دون الخروج من عمّان.",
      en: "Only four storeys on a generous plot, which is what makes a private garden possible for each ground-floor apartment and a roof duplex with an open terrace at the top. Shared space includes a pool and a walk among the mature trees we kept on site. For buyers who want real outdoor space without leaving Amman.",
    },
    highlights: [
      { ar: "حديقة خاصة لكل شقة أرضية", en: "Private garden with every ground-floor home" },
      { ar: "دوبلكسات بتراس مفتوح على السطح", en: "Roof duplexes with open terraces" },
      { ar: "مسبح وممشى بين الأشجار المعمّرة", en: "Pool and walkway among mature trees" },
      { ar: "أربعة طوابق فقط — كثافة منخفضة", en: "Four storeys only — low density" },
    ],
    amenities: ["pool", "garden", "reception", "generator", "parking", "security", "elevator", "playground"],
    floors: 4,
    groundFloorIsGarden: true,
    topFloorIsDuplex: true,
    pricePerM2: 1020,
    floorPremium: 0.02,
    lines: [
      { code: "A", beds: 3, baths: 3, area: 216, type: "apartment", plan: "plan-3br", orientation: "south", balcony: 28 },
      { code: "B", beds: 4, baths: 4, area: 268, type: "apartment", plan: "plan-4br", orientation: "west", balcony: 32 },
      { code: "C", beds: 4, baths: 4, area: 340, type: "apartment", plan: "plan-duplex", orientation: "north", balcony: 46 },
    ],
    sold: ["0-B", "1-C", "2-A"],
    reserved: ["0-A", "3-C"],
    plans: ["early", "handover", "bank"],
    gallery: ["project-rabieh", "gallery-courtyard-1", "gallery-interior-1", "gallery-facade-2"],
  },
];

/* ----------------------------------------------------------- payment plans */

const PAYMENT_PLANS = [
  {
    id: "early",
    name: { ar: "خطة الحجز المبكر", en: "Early reservation plan" },
    summary: {
      ar: "للمشترين في مرحلة الإنشاء — أفضل سعر مقابل دفعات موزّعة على فترة البناء.",
      en: "For buyers during construction — the best price in exchange for payments spread across the build.",
    },
    badge: { ar: "خصم ٣٪ على سعر الوحدة", en: "3% off the unit price" },
    downPayment: 15,
    steps: [
      { pct: 15, label: { ar: "عند توقيع عقد الحجز", en: "On signing the reservation contract" } },
      { pct: 45, label: { ar: "أقساط ربعية خلال فترة الإنشاء", en: "Quarterly instalments through construction" } },
      { pct: 40, label: { ar: "عند التسليم ونقل الملكية", en: "On handover and transfer of title" } },
    ],
    notes: [
      { ar: "السعر مثبّت من تاريخ التوقيع ولا يتأثر بارتفاع أسعار المواد.", en: "The price is fixed from signing and is not affected by material cost increases." },
      { ar: "يشمل رسوم تسجيل الوحدة في دائرة الأراضي والمساحة.", en: "Includes Department of Lands and Survey registration fees." },
    ],
    availableFor: { ar: "المشاريع قيد الإنشاء", en: "Projects under construction" },
  },
  {
    id: "handover",
    name: { ar: "خطة التسليم المريح", en: "Comfortable handover plan" },
    summary: {
      ar: "استلم مفتاحك أولاً وادفع الباقي على ٣٦ قسطاً شهرياً بدون أي فوائد.",
      en: "Take the keys first, then pay the balance over 36 monthly instalments with no interest.",
    },
    badge: { ar: "بدون فوائد", en: "Interest-free" },
    downPayment: 10,
    steps: [
      { pct: 10, label: { ar: "دفعة الحجز", en: "Reservation payment" } },
      { pct: 30, label: { ar: "عند توقيع عقد البيع", en: "On signing the sale contract" } },
      { pct: 60, label: { ar: "٣٦ قسطاً شهرياً بعد التسليم", en: "36 monthly instalments after handover" } },
    ],
    notes: [
      { ar: "الأقساط بدون فوائد أو رسوم إدارية.", en: "Instalments carry no interest and no administrative fees." },
      { ar: "تُنقل الملكية بعد سداد القسط الأخير.", en: "Title transfers once the final instalment is settled." },
    ],
    availableFor: { ar: "جميع المشاريع", en: "All projects" },
  },
  {
    id: "bank",
    name: { ar: "التمويل البنكي", en: "Bank financing" },
    summary: {
      ar: "دفعة أولى ٢٥٪ والباقي قرض سكني حتى ٢٥ سنة عبر بنوكنا الشريكة.",
      en: "A 25% down payment, with the balance financed for up to 25 years through our partner banks.",
    },
    badge: { ar: "حتى ٢٥ سنة", en: "Up to 25 years" },
    downPayment: 25,
    steps: [
      { pct: 25, label: { ar: "دفعة أولى من المشتري", en: "Buyer's down payment" } },
      { pct: 75, label: { ar: "تمويل بنكي يُصرف للشركة", en: "Bank financing released to the company" } },
    ],
    notes: [
      { ar: "نتولى إجراءات التقييم والتسجيل مع البنك نيابةً عنك.", en: "We handle valuation and registration with the bank on your behalf." },
      { ar: "أسعار الفائدة تحددها البنوك وتخضع للتغيير.", en: "Interest rates are set by the banks and are subject to change." },
    ],
    availableFor: { ar: "المشاريع الجاهزة والقريبة من التسليم", en: "Completed projects and those near handover" },
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

const TESTIMONIALS = [
  {
    name: { ar: "رنا العُمري", en: "Rana Al-Omari" },
    role: { ar: "مالكة شقة في ريزيدنس ٧٦", en: "Owner, Residence 76" },
    quote: {
      ar: "اشترينا على المخطط وكنّا نتوقع التأخير المعتاد. سُلِّمت الشقة قبل الموعد بأسبوعين، وبنفس التشطيبات التي وُعدنا بها في العقد لا نسخة أرخص منها.",
      en: "We bought off-plan and braced ourselves for the usual delay. The apartment was handed over two weeks early, with the same finishes written into the contract — not a cheaper version of them.",
    },
  },
  {
    name: { ar: "سامر حدّاد", en: "Samer Haddad" },
    role: { ar: "مالك شقة في ألتو", en: "Owner, Alto" },
    quote: {
      ar: "ما أقنعني هو أنهم أجابوا عن أسئلتي التقنية بالتفصيل: نوع العزل، وسماكة الزجاج، ومصدر المصاعد. لم أشعر أنني أمام بائع بل أمام مهندس يعرف مبناه.",
      en: "What convinced me was that they answered the technical questions properly — the insulation, the glazing thickness, where the lifts came from. It felt like talking to an engineer who knew the building, not a salesman.",
    },
  },
  {
    name: { ar: "د. ليلى الشوابكة", en: "Dr. Laila Al-Shawabkeh" },
    role: { ar: "مالكة شقة في بيت السرو", en: "Owner, Bayt Al Sarw" },
    quote: {
      ar: "كنت أبحث عن شقة عائلية تفصل غرف النوم عن مساحة الضيوف، وهذا نادر في عمّان. التوزيع هنا كان الوحيد الذي لم أحتج لتعديله.",
      en: "I was looking for a family apartment that separates the bedrooms from the guest space, which is rare in Amman. This was the only layout I did not want to change.",
    },
  },
  {
    name: { ar: "خالد المجالي", en: "Khaled Al-Majali" },
    role: { ar: "مستثمر — ثلاث وحدات", en: "Investor — three units" },
    quote: {
      ar: "أتعامل معهم منذ ٢٠١٨ في ثلاث وحدات. التقارير الربعية عن نسبة الإنجاز تصل في موعدها، وهذا وحده يوفّر عليّ متابعة أسبوعية.",
      en: "I have bought three units with them since 2018. The quarterly progress reports arrive when they say they will, which alone saves me chasing them every week.",
    },
  },
];

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

/** Floor label: 0 is the ground floor; the top floor may be a penthouse. */
function floorMeta(project, floor) {
  const isTop = floor === project.floors - 1;
  if (floor === 0) return { key: "ground", ar: "الطابق الأرضي", en: "Ground floor" };
  if (isTop && project.topFloorIsPenthouse) return { key: "penthouse", ar: "الطابق الأخير (روف)", en: "Top floor (penthouse)" };
  if (isTop && project.topFloorIsDuplex) return { key: "duplex", ar: "الطابق الأخير (دوبلكس)", en: "Top floor (duplex)" };
  return { key: String(floor), ar: `الطابق ${["", "الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن", "التاسع", "العاشر"][floor] || floor}`, en: `Floor ${floor}` };
}

/** Expand the line/floor grid into the flat unit list the site works with. */
function buildUnits() {
  const units = [];
  for (const p of PROJECTS) {
    for (let floor = 0; floor < p.floors; floor++) {
      for (const line of p.lines) {
        const key = `${floor}-${line.code}`;
        const status = p.sold.includes(key) ? UNIT_STATUS.sold
          : p.reserved.includes(key) ? UNIT_STATUS.reserved
          : UNIT_STATUS.available;
        const isTop = floor === p.floors - 1;
        let type = line.type;
        if (floor === 0 && p.groundFloorIsGarden) type = "garden";
        else if (isTop && p.topFloorIsDuplex) type = "duplex";
        else if (isTop && p.topFloorIsPenthouse) type = "penthouse";

        // Ground-floor homes trade the view for a garden; the top floor pays for it.
        const areaBonus = type === "garden" ? 0 : type === "duplex" ? Math.round(line.area * 0.28) : 0;
        const area = line.area + areaBonus;
        const outdoor = type === "garden" ? Math.round(line.area * 0.45) : type === "duplex" || type === "penthouse" ? Math.round(line.balcony * 2.4) : line.balcony;
        const raw = area * p.pricePerM2 * (1 + p.floorPremium * floor) * (type === "garden" ? 0.94 : 1);

        units.push({
          id: `${p.id}-${key}`,
          code: `${line.code}${floor === 0 ? "G" : floor}`,
          projectId: p.id,
          district: p.district,
          floor,
          floorLabel: floorMeta(p, floor),
          line: line.code,
          type,
          beds: line.beds,
          baths: line.baths,
          area,
          outdoor,
          orientation: line.orientation,
          plan: line.plan,
          price: Math.round(raw / 500) * 500,
          status,
        });
      }
    }
  }
  return units;
}

const UNITS = buildUnits();

const UNIT_TYPES = {
  apartment: { ar: "شقة", en: "Apartment" },
  garden: { ar: "شقة بحديقة", en: "Garden apartment" },
  duplex: { ar: "دوبلكس", en: "Duplex" },
  penthouse: { ar: "بنتهاوس", en: "Penthouse" },
};

const ORIENTATIONS = {
  north: { ar: "شمالية", en: "North facing" },
  south: { ar: "جنوبية", en: "South facing" },
  east: { ar: "شرقية", en: "East facing" },
  west: { ar: "غربية", en: "West facing" },
};

const PROJECT_STATUS = {
  ready: { ar: "جاهز للسكن", en: "Ready to move in" },
  construction: { ar: "قيد الإنشاء", en: "Under construction" },
  soldout: { ar: "بيعت بالكامل", en: "Sold out" },
};

/** Rooms shown beside every floor plan; the plan drawings carry the numbers. */
const PLAN_LEGEND = {
  1: { ar: "الصالة والمعيشة", en: "Living and reception" },
  2: { ar: "المطبخ", en: "Kitchen" },
  3: { ar: "حمّام الضيوف", en: "Guest bathroom" },
  4: { ar: "غرفة النوم الرئيسية", en: "Master bedroom" },
  5: { ar: "غرفة نوم", en: "Bedroom" },
  6: { ar: "حمّام", en: "Bathroom" },
  7: { ar: "حمّام داخل الغرفة", en: "En-suite bathroom" },
  8: { ar: "غرفة الطعام", en: "Dining room" },
  9: { ar: "غرفة الخادمة", en: "Maid's room" },
  10: { ar: "غرفة المكتب", en: "Study" },
  11: { ar: "غرفة الغسيل", en: "Laundry" },
  12: { ar: "درج داخلي", en: "Internal stair" },
};

const DATA = {
  COMPANY, DISTRICTS, PROJECTS, UNITS, PAYMENT_PLANS, AMENITIES, TESTIMONIALS,
  PROCESS, FAQS, UNIT_TYPES, ORIENTATIONS, PROJECT_STATUS, PLAN_LEGEND, floorMeta,
};

if (typeof window !== "undefined") window.DATA = DATA;
if (typeof module !== "undefined") module.exports = DATA;
