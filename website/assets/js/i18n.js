/* =============================================================================
   Bilingual layer. Arabic is the primary language: it is written directly into
   the HTML (so it is what crawlers and no-JS visitors get) and repeated here so
   that switching back from English restores it. Keep the two in step — if you
   edit a string in the HTML, edit its twin below.
   ========================================================================== */

const T = {
  /* brand + chrome */
  "brand.name": { ar: "جنرال شيرمان", en: "General Sherman" },
  "brand.full": { ar: "شركة جنرال شيرمان للإسكان", en: "General Sherman Housing" },
  "brand.tag": { ar: "General Sherman Housing", en: "شركة جنرال شيرمان للإسكان" },

  /* home page */
  "home.eyebrow": { ar: "تطوير عقاري في عمّان منذ ٢٠٠٩", en: "Developing in Amman since 2009" },
  "home.heroTitle": { ar: "شققٌ مبنيّة لتُسكن، لا لتُباع فقط.", en: "Apartments built to be lived in, not only sold." },
  "home.heroSub": {
    ar: "خمسة مشاريع سكنية في عبدون ودير غبار وخلدا وأم أذينة والرابية — تصميم هادئ، تشطيبات نعرف مصدرها، وعقود تحدد موعد التسليم بوضوح.",
    en: "Five residential schemes across Abdoun, Deir Ghbar, Khalda, Um Uthaina and Rabieh — restrained design, finishes we can trace, and contracts that state the handover date plainly.",
  },
  "home.searchBtn": { ar: "اعرض الوحدات", en: "Show units" },
  "home.scroll": { ar: "تابع", en: "Scroll" },
  "home.projectsEyebrow": { ar: "المشاريع", en: "Projects" },
  "home.projectsTitle": { ar: "خمسة عناوين في غرب عمّان", en: "Five addresses in West Amman" },
  "home.projectsLead": {
    ar: "مشروعان جاهزان للسكن وثلاثة قيد الإنشاء. كل مشروع صُمِّم لأرضه ولمن سيسكنه، لا نسخةً مكررة عن سابقه.",
    en: "Two buildings ready to move into and three under construction. Each one is designed for its own plot and its own buyers, not copied from the last.",
  },
  "home.whyEyebrow": { ar: "لماذا جنرال شيرمان", en: "Why General Sherman" },
  "home.whyTitle": { ar: "ما نعد به مكتوبٌ في العقد", en: "What we promise is written into the contract" },
  "home.whyLead": {
    ar: "لأن الفرق بين شركة تطوير وأخرى لا يظهر في المخطط، بل بعد التسليم بسنتين.",
    en: "The difference between one developer and another does not show in the drawings. It shows two years after handover.",
  },
  "home.why1": { ar: "مواصفات التشطيب مذكورة بالاسم والمصدر في ملحق العقد — لا عبارات فضفاضة.", en: "Finishes are named by brand and origin in the contract annexe — no vague wording." },
  "home.why2": { ar: "غرامة تأخير محددة لصالح المشتري إذا تجاوزنا موعد التسليم.", en: "A defined late-delivery penalty payable to the buyer if we miss the handover date." },
  "home.why3": { ar: "تقرير ربعي مصوّر عن نسبة الإنجاز يصل لكل مشترٍ على المخطط.", en: "A photographed quarterly progress report sent to every off-plan buyer." },
  "home.why4": { ar: "ضمان سنتين على التشطيبات وعشر سنوات على الهيكل الإنشائي.", en: "Two years' warranty on finishes and ten years on the structure." },
  "home.why5": { ar: "فريق صيانة يستجيب خلال ٤٨ ساعة خلال السنة الأولى بعد التسليم.", en: "A maintenance team that responds within 48 hours during the first year." },
  "home.aboutLink": { ar: "تعرّف على الشركة", en: "About the company" },
  "home.unitsEyebrow": { ar: "الوحدات", en: "Units" },
  "home.unitsTitle": { ar: "أفضل ما هو متاح الآن", en: "The best of what is available now" },
  "home.unitsLead": {
    ar: "ثلاث وحدات مختارة بأعلى مساحة مقابل السعر من بين الوحدات المتاحة حالياً.",
    en: "Three units picked for the most space per dinar among everything currently available.",
  },
  "home.processEyebrow": { ar: "كيف نعمل", en: "How we work" },
  "home.processTitle": { ar: "من الزيارة الأولى إلى تسليم المفتاح", en: "From the first visit to the handover of keys" },
  "home.quotesEyebrow": { ar: "آراء الملّاك", en: "Owners" },
  "home.quotesTitle": { ar: "ما يقوله من سكن معنا", en: "What the people who live there say" },
  "home.ctaTitle": { ar: "خطط دفع تبدأ بـ ١٠٪ وأقساط بدون فوائد", en: "Payment plans from 10% down, with interest-free instalments" },
  "home.ctaBody": {
    ar: "احسب قسطك الشهري على أي وحدة متاحة خلال ثوانٍ، أو اطلب من فريق المبيعات دراسة مخصصة لوضعك.",
    en: "Work out the monthly instalment on any available unit in seconds, or ask our sales team for a plan built around your situation.",
  },
  "home.ctaBtn": { ar: "حاسبة الأقساط", en: "Instalment calculator" },

  /* footer */
  "footer.about": {
    ar: "شركة أردنية للتطوير العقاري متخصصة في الشقق السكنية الفاخرة في غرب عمّان منذ عام ٢٠٠٩.",
    en: "A Jordanian residential developer specialising in luxury apartments across West Amman since 2009.",
  },
  "footer.explore": { ar: "تصفّح", en: "Explore" },
  "footer.projects": { ar: "المشاريع", en: "Projects" },
  "footer.contact": { ar: "تواصل معنا", en: "Contact" },
  "footer.address": { ar: "شارع عبد الله غوشة، مبنى ٤٦، الطابق الثالث، عمّان ١١١٩٤، الأردن", en: "46 Abdullah Ghosheh Street, 3rd Floor, Amman 11194, Jordan" },
  "footer.hours": { ar: "السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً", en: "Saturday – Thursday, 9:00 – 18:00" },
  "footer.rights": { ar: "شركة جنرال شيرمان للإسكان. جميع الحقوق محفوظة.", en: "General Sherman Housing. All rights reserved." },
  "footer.note": {
    ar: "الصور معالجات معمارية توضيحية، والأسعار قابلة للتغيير دون إشعار مسبق.",
    en: "Images are illustrative architectural studies. Prices are subject to change without notice.",
  },

  /* nav + chrome */
  "nav.home": { ar: "الرئيسية", en: "Home" },
  "nav.about": { ar: "عن الشركة", en: "About" },
  "nav.projects": { ar: "مشاريعنا", en: "Projects" },
  "nav.units": { ar: "الوحدات المتاحة", en: "Available units" },
  "nav.plans": { ar: "خطط الدفع", en: "Payment plans" },
  "nav.gallery": { ar: "معرض الصور", en: "Gallery" },
  "nav.contact": { ar: "اتصل بنا", en: "Contact" },
  "nav.menu": { ar: "القائمة", en: "Menu" },
  "nav.skip": { ar: "تخطَّ إلى المحتوى", en: "Skip to content" },
  "lang.switch": { ar: "English", en: "العربية" },
  "lang.switchLabel": { ar: "Switch to English", en: "التبديل إلى العربية" },

  /* generic actions */
  "cta.enquire": { ar: "استفسر عن الوحدة", en: "Enquire about this unit" },
  "cta.viewProject": { ar: "تفاصيل المشروع", en: "View project" },
  "cta.viewUnits": { ar: "تصفّح الوحدات المتاحة", en: "Browse available units" },
  "cta.bookViewing": { ar: "احجز زيارة", en: "Book a viewing" },
  "cta.whatsapp": { ar: "واتساب", en: "WhatsApp" },
  "cta.call": { ar: "اتصل بنا", en: "Call us" },
  "cta.allProjects": { ar: "جميع المشاريع", en: "All projects" },
  "cta.contactUs": { ar: "تواصل معنا", en: "Get in touch" },
  "cta.close": { ar: "إغلاق", en: "Close" },
  "cta.prev": { ar: "السابق", en: "Previous" },
  "cta.next": { ar: "التالي", en: "Next" },
  "cta.reset": { ar: "مسح الفلاتر", en: "Clear filters" },
  "cta.downloadPlan": { ar: "تحميل المخطط", en: "Download plan" },

  /* unit + project vocabulary */
  "unit.unit": { ar: "الوحدة", en: "Unit" },
  "unit.beds": { ar: "غرف نوم", en: "Bedrooms" },
  "unit.baths": { ar: "حمّامات", en: "Bathrooms" },
  "unit.area": { ar: "المساحة", en: "Area" },
  "unit.outdoor": { ar: "مساحة خارجية", en: "Outdoor space" },
  "unit.floor": { ar: "الطابق", en: "Floor" },
  "unit.price": { ar: "السعر", en: "Price" },
  "unit.priceFrom": { ar: "تبدأ من", en: "From" },
  "unit.perM2": { ar: "سعر المتر", en: "Per m²" },
  "unit.type": { ar: "النوع", en: "Type" },
  "unit.orientation": { ar: "الاتجاه", en: "Orientation" },
  "unit.status": { ar: "الحالة", en: "Status" },
  "unit.project": { ar: "المشروع", en: "Project" },
  "unit.district": { ar: "المنطقة", en: "Area" },
  "unit.plan": { ar: "المخطط", en: "Floor plan" },
  "unit.sqm": { ar: "م²", en: "m²" },
  "unit.jod": { ar: "دينار", en: "JOD" },
  "status.available": { ar: "متاحة", en: "Available" },
  "status.reserved": { ar: "محجوزة", en: "Reserved" },
  "status.sold": { ar: "مباعة", en: "Sold" },
  "project.units": { ar: "وحدة", en: "units" },
  "project.available": { ar: "متاحة الآن", en: "available now" },
  "project.floors": { ar: "طوابق", en: "floors" },
  "project.delivery": { ar: "التسليم", en: "Delivery" },
  "project.amenities": { ar: "مرافق المشروع", en: "Building amenities" },
  "project.highlights": { ar: "أبرز ما يميّزه", en: "What sets it apart" },
  "project.location": { ar: "الموقع", en: "Location" },
  "project.soldOut": { ar: "بيعت بالكامل", en: "Fully sold" },

  /* filters */
  "filter.title": { ar: "تصفية الوحدات", en: "Filter units" },
  "filter.project": { ar: "المشروع", en: "Project" },
  "filter.district": { ar: "المنطقة", en: "District" },
  "filter.beds": { ar: "غرف النوم", en: "Bedrooms" },
  "filter.type": { ar: "نوع الوحدة", en: "Unit type" },
  "filter.floor": { ar: "الطابق", en: "Floor" },
  "filter.minArea": { ar: "أقل مساحة (م²)", en: "Min area (m²)" },
  "filter.maxPrice": { ar: "أعلى سعر (دينار)", en: "Max price (JOD)" },
  "filter.status": { ar: "الحالة", en: "Availability" },
  "filter.sort": { ar: "الترتيب", en: "Sort by" },
  "filter.any": { ar: "الكل", en: "Any" },
  "filter.plus": { ar: "فأكثر", en: "or more" },
  "filter.ground": { ar: "أرضي", en: "Ground" },
  "sort.priceAsc": { ar: "السعر: من الأقل", en: "Price: low to high" },
  "sort.priceDesc": { ar: "السعر: من الأعلى", en: "Price: high to low" },
  "sort.areaDesc": { ar: "المساحة: الأكبر أولاً", en: "Area: largest first" },
  "sort.floorAsc": { ar: "الطابق: من الأسفل", en: "Floor: lowest first" },
  "results.count": { ar: "وحدة مطابقة", en: "matching units" },
  "results.emptyTitle": { ar: "لا توجد وحدات مطابقة", en: "No units match those filters" },
  "results.emptyBody": {
    ar: "جرّب توسيع نطاق السعر أو المساحة، أو تواصل معنا مباشرةً — بعض الوحدات تُعرض قبل إدراجها هنا.",
    en: "Try widening the price or area range, or contact us directly — some units are released before they are listed here.",
  },

  /* availability grid */
  "grid.title": { ar: "جدول توفّر الوحدات", en: "Unit availability" },
  "grid.intro": {
    ar: "كل خانة تمثّل وحدة فعلية في المبنى. اضغط على أي وحدة متاحة لعرض تفاصيلها.",
    en: "Each cell is a real unit in the building. Select any available unit to see its details.",
  },
  "grid.line": { ar: "الخط", en: "Line" },

  /* calculator */
  "calc.title": { ar: "حاسبة الأقساط", en: "Instalment calculator" },
  "calc.price": { ar: "سعر الوحدة (دينار)", en: "Unit price (JOD)" },
  "calc.down": { ar: "الدفعة الأولى", en: "Down payment" },
  "calc.years": { ar: "مدة التقسيط (سنوات)", en: "Instalment period (years)" },
  "calc.rate": { ar: "الفائدة السنوية للبنك", en: "Annual bank interest" },
  "calc.plan": { ar: "خطة الدفع", en: "Payment plan" },
  "calc.monthly": { ar: "القسط الشهري التقريبي", en: "Estimated monthly instalment" },
  "calc.downAmount": { ar: "الدفعة الأولى", en: "Down payment" },
  "calc.financed": { ar: "المبلغ المقسّط", en: "Amount financed" },
  "calc.total": { ar: "إجمالي المدفوع", en: "Total paid" },
  "calc.interest": { ar: "إجمالي الفوائد", en: "Total interest" },
  "calc.months": { ar: "عدد الأقساط", en: "Number of instalments" },
  "calc.pickUnit": { ar: "اختر وحدة لتعبئة السعر", en: "Pick a unit to fill in the price" },
  "calc.custom": { ar: "سعر مخصص", en: "Custom price" },
  "calc.disclaimer": {
    ar: "الأرقام تقديرية لغرض التخطيط فقط ولا تمثّل عرضاً ملزماً. تُحتسب أقساط الشركة بدون فوائد، بينما يعتمد التمويل البنكي على سعر الفائدة الذي يحدده البنك.",
    en: "These figures are estimates for planning only and are not a binding offer. Company instalments carry no interest; bank financing depends on the rate your bank sets.",
  },

  /* forms */
  "form.name": { ar: "الاسم الكامل", en: "Full name" },
  "form.phone": { ar: "رقم الهاتف", en: "Phone number" },
  "form.email": { ar: "البريد الإلكتروني", en: "Email address" },
  "form.interest": { ar: "المشروع الذي يهمّك", en: "Project of interest" },
  "form.budget": { ar: "الميزانية التقريبية", en: "Approximate budget" },
  "form.message": { ar: "رسالتك", en: "Your message" },
  "form.preferred": { ar: "طريقة التواصل المفضّلة", en: "Preferred contact method" },
  "form.optional": { ar: "اختياري", en: "optional" },
  "form.send": { ar: "إرسال الطلب", en: "Send enquiry" },
  "form.sending": { ar: "جارٍ الإرسال…", en: "Sending…" },
  "form.consent": {
    ar: "أوافق على أن تتواصل معي جنرال شيرمان بخصوص هذا الطلب.",
    en: "I agree to be contacted by General Sherman about this enquiry.",
  },
  "form.errRequired": { ar: "هذا الحقل مطلوب.", en: "This field is required." },
  "form.errName": { ar: "يرجى كتابة الاسم الكامل.", en: "Please enter your full name." },
  "form.errPhone": { ar: "يرجى إدخال رقم هاتف صحيح، مثال: 0790000000", en: "Enter a valid phone number, e.g. 0790000000." },
  "form.errEmail": { ar: "يرجى إدخال بريد إلكتروني صحيح.", en: "Enter a valid email address." },
  "form.errConsent": { ar: "نحتاج موافقتك لنتمكن من الرد عليك.", en: "We need your consent in order to reply." },
  "form.okTitle": { ar: "تم استلام طلبك", en: "Enquiry received" },
  "form.okWhatsapp": {
    ar: "فتحنا محادثة واتساب بتفاصيل طلبك — أرسلها لنا وسيتواصل معك فريق المبيعات خلال يوم عمل واحد.",
    en: "We have opened a WhatsApp chat with your details — send it and our sales team will reply within one working day.",
  },
  "form.okPosted": {
    ar: "شكراً لك. وصلنا طلبك وسيتواصل معك فريق المبيعات خلال يوم عمل واحد.",
    en: "Thank you. We have your enquiry and our sales team will be in touch within one working day.",
  },
  "form.errSend": {
    ar: "تعذّر إرسال الطلب. يمكنك مراسلتنا على واتساب أو الاتصال بنا مباشرةً.",
    en: "We could not send that. Please message us on WhatsApp or call us directly.",
  },
  "form.emailFallback": { ar: "أو أرسل بريداً إلكترونياً", en: "Or send it by email" },

  /* enquiry modal */
  "modal.enquiryTitle": { ar: "استفسار عن وحدة", en: "Unit enquiry" },
  "modal.enquiryIntro": {
    ar: "اترك بياناتك وسنرسل لك المخططات والسعر التفصيلي وخطط الدفع المتاحة لهذه الوحدة.",
    en: "Leave your details and we will send you the plans, the detailed price and the payment plans available for this unit.",
  },

  /* projects index */
  "projects.eyebrow": { ar: "المشاريع", en: "Projects" },
  "projects.title": { ar: "خمسة مشاريع، خمس مناطق، منهج واحد", en: "Five schemes, five districts, one method" },
  "projects.lead": {
    ar: "نبني عدداً محدوداً من المشاريع في الوقت نفسه حتى يبقى كل مشروع تحت إشراف مباشر من فريقنا الهندسي حتى التسليم.",
    en: "We keep only a few schemes running at once, so each one stays under our own engineers' direct supervision through to handover.",
  },
  "projects.all": { ar: "جميع المشاريع", en: "All projects" },
  "status.ready": { ar: "جاهز للسكن", en: "Ready to move in" },
  "status.construction": { ar: "قيد الإنشاء", en: "Under construction" },
  "projects.mapEyebrow": { ar: "أين نبني", en: "Where we build" },
  "projects.mapTitle": { ar: "مناطق نعرفها جيداً", en: "Districts we know well" },
  "projects.mapLead": {
    ar: "نعمل في نطاق جغرافي ضيق عمداً: خمس مناطق في غرب عمّان نعرف أسعار أراضيها وأنظمة البناء فيها وحركة الطلب عليها.",
    en: "We work in a deliberately narrow area: five districts of West Amman whose land prices, building regulations and demand we know first-hand.",
  },
  "projects.d1Title": { ar: "عبدون وأم أذينة", en: "Abdoun and Um Uthaina" },
  "projects.d1Body": {
    ar: "أعلى شريحة سعرية في عمّان، ومشترون يبحثون عن الخصوصية والمساحة الكبيرة أكثر من عدد الغرف.",
    en: "Amman's highest price bracket, where buyers want privacy and generous space more than an extra bedroom.",
  },
  "projects.d2Title": { ar: "دير غبار والرابية", en: "Deir Ghbar and Rabieh" },
  "projects.d2Body": {
    ar: "مناطق منحدرة تمنح إطلالات مفتوحة، وهي الأنسب لمن يوازن بين السعر والموقع.",
    en: "Sloping ground that keeps views open — the best balance of price and address.",
  },
  "projects.d3Title": { ar: "خلدا", en: "Khalda" },
  "projects.d3Body": {
    ar: "منطقة عائلية بامتياز: مدارس وخدمات ضمن دقائق، وطلب مستقر على الشقق الكبيرة.",
    en: "Family territory: schools and services minutes away, and steady demand for larger apartments.",
  },

  /* project detail */
  "project.seeGrid": { ar: "جدول التوفّر", en: "Availability grid" },
  "project.aboutEyebrow": { ar: "عن المشروع", en: "About the scheme" },
  "project.facts": { ar: "أرقام المشروع", en: "Project at a glance" },
  "project.gridTitle": { ar: "اختر وحدتك من المبنى مباشرةً", en: "Pick your unit straight off the building" },
  "project.unitsTitle": { ar: "الوحدات في هذا المشروع", en: "Units in this project" },
  "project.allUnits": { ar: "عرض جميع وحدات المشروع", en: "See every unit in this project" },
  "project.plansTitle": { ar: "المخططات الأفقية", en: "Floor plans" },
  "project.plansLead": {
    ar: "مخططات توضيحية بمقياس تقريبي. المساحات النهائية مذكورة في العقد.",
    en: "Indicative drawings, approximately to scale. Final areas are stated in the contract.",
  },
  "project.legend": { ar: "دليل الغرف", en: "Room key" },
  "project.paymentTitle": { ar: "خطط الدفع المتاحة لهذا المشروع", en: "Payment plans available here" },
  "project.calcLink": { ar: "احسب قسطك الشهري", en: "Work out your monthly instalment" },
  "project.mapTitle": { ar: "أين يقع المشروع", en: "Where the project is" },
  "project.openMap": { ar: "افتح في خرائط جوجل", en: "Open in Google Maps" },
  "project.galleryTitle": { ar: "صور المشروع", en: "Project images" },
  "project.relatedEyebrow": { ar: "مشاريع أخرى", en: "Other projects" },
  "project.relatedTitle": { ar: "قد تهمّك أيضاً", en: "You may also want to see" },

  /* units page */
  "units.eyebrow": { ar: "المخزون الحالي", en: "Current inventory" },
  "units.title": { ar: "كل وحدة متاحة، بسعرها ومساحتها", en: "Every available unit, with its price and area" },
  "units.lead": {
    ar: "لا نُخفي الأسعار خلف نموذج تواصل. ما تراه هنا هو المخزون الفعلي المحدَّث، بما فيه الوحدات المحجوزة والمباعة.",
    en: "We do not hide prices behind a contact form. This is the live inventory, including what is reserved and what has sold.",
  },
  "units.note": {
    ar: "الأسعار بالدينار الأردني وتشمل موقف السيارة والمستودع، ولا تشمل رسوم التسجيل ما لم يُذكر خلاف ذلك في خطة الدفع.",
    en: "Prices are in Jordanian dinars and include the parking bay and store. Registration fees are excluded unless your payment plan says otherwise.",
  },

  /* payment plans page */
  "plans.eyebrow": { ar: "الدفع والتمويل", en: "Payment and financing" },
  "plans.title": { ar: "ثلاث طرق لتملّك وحدتك", en: "Three ways to own your home" },
  "plans.lead": {
    ar: "اختر الخطة التي تناسب سيولتك، لا التي تناسبنا. جميع الأقساط الداخلية بدون فوائد أو رسوم إدارية.",
    en: "Choose the plan that fits your cash flow, not ours. Every in-house instalment is free of interest and administrative fees.",
  },
  "plans.calcTitle": { ar: "كم سيكون قسطك الشهري؟", en: "What would your monthly instalment be?" },
  "plans.calcLead": {
    ar: "اختر وحدة من مخزوننا أو أدخل أي سعر، ثم عدّل الدفعة الأولى والمدة.",
    en: "Pick a unit from our inventory or type any price, then adjust the down payment and the term.",
  },
  "plans.modeCompany": { ar: "أقساط الشركة — بدون فوائد", en: "Company instalments — interest-free" },
  "plans.modeCompanyNote": { ar: "حتى ٥ سنوات، بدون فوائد أو رسوم إدارية.", en: "Up to 5 years, with no interest and no admin fees." },
  "plans.modeBank": { ar: "تمويل بنكي", en: "Bank financing" },
  "plans.modeBankNote": { ar: "حتى ٢٥ سنة عبر البنوك الشريكة، بفائدة يحددها البنك.", en: "Up to 25 years through partner banks, at the bank's rate." },
  "plans.talkBtn": { ar: "تحدّث مع فريق المبيعات", en: "Talk to the sales team" },
  "plans.faqEyebrow": { ar: "أسئلة شائعة", en: "Common questions" },
  "plans.faqTitle": { ar: "أسئلة عن الدفع والتملّك", en: "Questions about paying and owning" },
  "plans.q1": { ar: "هل يمكن تغيير خطة الدفع بعد التوقيع؟", en: "Can the payment plan change after signing?" },
  "plans.a1": {
    ar: "نعم، يمكن الانتقال من خطة إلى أخرى قبل التسليم بموافقة الطرفين وبإعادة جدولة مكتوبة تُلحق بالعقد. الانتقال إلى التمويل البنكي شائع عند اقتراب موعد التسليم.",
    en: "Yes. You can move between plans before handover, by mutual agreement and a written rescheduling annexed to the contract. Switching to bank financing as handover approaches is common.",
  },
  "plans.q2": { ar: "ماذا يحدث إذا تأخرت عن قسط؟", en: "What happens if I miss an instalment?" },
  "plans.a2": {
    ar: "هناك مهلة سماح ثلاثين يوماً بدون أي غرامة. بعدها نتواصل معك لإعادة الجدولة قبل اتخاذ أي إجراء تعاقدي — فسخ العقد هو الخيار الأخير لا الأول.",
    en: "There is a 30-day grace period with no penalty. After that we contact you to reschedule before any contractual step is taken — cancelling the contract is the last resort, not the first.",
  },
  "plans.q3": { ar: "هل يمكن السداد المبكر؟", en: "Can I settle early?" },
  "plans.a3": {
    ar: "نعم، ودون أي رسوم على أقساط الشركة. أما في التمويل البنكي فتطبَّق شروط البنك المتعلقة بالسداد المبكر.",
    en: "Yes, with no fee on company instalments. With bank financing, the bank's own early-settlement terms apply.",
  },
  "plans.q4": { ar: "ما هي الرسوم الحكومية المتوقعة؟", en: "What government fees should I expect?" },
  "plans.a4": {
    ar: "رسوم التسجيل في دائرة الأراضي والمساحة تُحتسب كنسبة من قيمة العقد وتخضع للتشريعات النافذة وقت التسجيل. نوضح لك الرقم التقديري كتابةً قبل التوقيع، وخطة الحجز المبكر تشملها.",
    en: "Department of Lands and Survey registration fees are a percentage of the contract value, set by the legislation in force at the time. We put the estimate in writing before you sign, and the early reservation plan covers them.",
  },

  /* gallery */
  "gallery.eyebrow": { ar: "المعرض", en: "Gallery" },
  "gallery.title": { ar: "الواجهات والمساحات والتفاصيل", en: "Elevations, spaces and details" },
  "gallery.lead": {
    ar: "معالجات معمارية تُظهر نيّة التصميم: كيف يدخل الضوء، وكيف تتوزع الشرفات، وكيف يبدو المبنى في ساعات النهار المختلفة.",
    en: "Architectural studies showing the design intent: how the light enters, how the balconies are arranged, and how the building reads at different hours.",
  },
  "gallery.all": { ar: "الكل", en: "All" },
  "gallery.projects": { ar: "المشاريع", en: "Projects" },
  "gallery.facades": { ar: "الواجهات", en: "Elevations" },
  "gallery.interiors": { ar: "المساحات الداخلية", en: "Interiors" },
  "gallery.amenities": { ar: "المرافق", en: "Amenities" },
  "gallery.note": {
    ar: "جميع الصور معالجات معمارية توضيحية أعدّها فريق التصميم، وقد تختلف عن التنفيذ النهائي في بعض التفاصيل.",
    en: "All images are illustrative architectural studies prepared by the design team, and may differ from the built result in some details.",
  },

  /* about */
  "about.eyebrow": { ar: "من نحن", en: "Who we are" },
  "about.title": { ar: "سبعة عشر عاماً، ومبنى واحد في كل مرة", en: "Seventeen years, one building at a time" },
  "about.lead": {
    ar: "بدأنا عام ٢٠٠٩ بمبنى واحد في خلدا. اليوم سلّمنا ١٦ مشروعاً و٤٨٠ وحدة، وما زلنا نبني عدداً محدوداً في الوقت نفسه.",
    en: "We started in 2009 with a single building in Khalda. We have since delivered 16 projects and 480 homes — and still keep only a few on site at once.",
  },
  "about.storyEyebrow": { ar: "القصة", en: "The story" },
  "about.storyTitle": { ar: "لماذا نبني قليلاً", en: "Why we build slowly" },
  "about.story1": {
    ar: "تأسست جنرال شيرمان عام ٢٠٠٩ على قاعدة بسيطة: ألا نبدأ مشروعاً جديداً قبل أن يصل السابق إلى مرحلة التشطيبات. هذا يعني نمواً أبطأ من غيرنا، لكنه يعني أيضاً أن المهندس المشرف على مبناك ليس مسؤولاً عن ستة مبانٍ أخرى في الوقت نفسه.",
    en: "General Sherman was founded in 2009 on a simple rule: no new project starts until the previous one reaches finishing stage. That makes us grow more slowly than others — and it also means the engineer supervising your building is not running six others at the same time.",
  },
  "about.story2": {
    ar: "نشتري الأرض نقداً قبل التصميم، فلا نضطر لضغط المواصفات لاحقاً لتغطية كلفة التمويل. ونشتري مواد التشطيب الأساسية — البلاط والأدوات الصحية والمصاعد — دفعةً واحدة عند التعاقد، حتى لا يتغير ما وعدناك به إذا تغيرت الأسعار.",
    en: "We buy the land outright before design begins, so we are never squeezing the specification later to cover financing costs. And we buy the main finishing materials — tiling, sanitary ware, lifts — in one order at contract stage, so what we promised does not quietly change when prices do.",
  },
  "about.valuesEyebrow": { ar: "كيف نعمل", en: "How we work" },
  "about.valuesTitle": { ar: "أربعة التزامات لا نساوم عليها", en: "Four commitments we do not trade away" },
  "about.v1Title": { ar: "الأرض أولاً", en: "The land comes first" },
  "about.v1Body": {
    ar: "نرفض أراضي كثيرة سنوياً بسبب الضجيج أو الإطلالة المحجوبة أو ضعف الوصول. المبنى الجيد على أرض سيئة يبقى استثماراً سيئاً.",
    en: "We turn down plots every year over noise, a blocked outlook or poor access. A good building on a bad plot is still a bad investment.",
  },
  "about.v2Title": { ar: "التوزيع قبل الديكور", en: "Layout before decoration" },
  "about.v2Body": {
    ar: "نصرف وقتاً أطول على مسار الحركة داخل الشقة وفصل جناح النوم عن الضيوف، أكثر مما نصرفه على واجهة المبنى.",
    en: "We spend longer on circulation inside the apartment, and on separating the sleeping wing from the guest rooms, than we do on the elevation.",
  },
  "about.v3Title": { ar: "ما لا يُرى", en: "What you cannot see" },
  "about.v3Body": {
    ar: "العزل الحراري والصوتي وتمديدات الميكانيك تُنفَّذ بمواصفات أعلى من الحد النظامي، لأن تعديلها بعد التسليم شبه مستحيل.",
    en: "Thermal and acoustic insulation and the mechanical services are built above code, because they are close to impossible to change after handover.",
  },
  "about.v4Title": { ar: "بعد التسليم", en: "After handover" },
  "about.v4Body": {
    ar: "فريق الصيانة تابع للشركة وليس مقاولاً خارجياً، ويستجيب خلال ٤٨ ساعة في السنة الأولى.",
    en: "The maintenance team is our own staff, not an outside contractor, and responds within 48 hours during the first year.",
  },
  "about.ctaTitle": { ar: "تعال شاهد المشاريع على الطبيعة", en: "Come and see the buildings for yourself" },
  "about.ctaBody": {
    ar: "جولة الموقع تستغرق نحو ساعة، ونرافقك فيها بأنفسنا — بما في ذلك المشاريع قيد الإنشاء.",
    en: "A site visit takes about an hour and we walk it with you — including the projects still under construction.",
  },

  /* contact */
  "contact.eyebrow": { ar: "تواصل معنا", en: "Contact" },
  "contact.title": { ar: "تحدّث مع من يعرف المبنى", en: "Talk to someone who knows the building" },
  "contact.lead": {
    ar: "فريق المبيعات لدينا مهندسون، لا وسطاء. اسألهم عن العزل أو المصاعد أو نسبة الإنجاز وستحصل على إجابة دقيقة.",
    en: "Our sales team are engineers, not brokers. Ask them about the insulation, the lifts or the current progress and you will get a precise answer.",
  },
  "contact.formTitle": { ar: "أرسل استفسارك", en: "Send your enquiry" },
  "contact.formNote": {
    ar: "نرد على الاستفسارات خلال يوم عمل واحد. إذا كان طلبك عاجلاً، الاتصال أو واتساب أسرع.",
    en: "We answer enquiries within one working day. If it is urgent, calling or WhatsApp is faster.",
  },
  "contact.directTitle": { ar: "تواصل مباشر", en: "Reach us directly" },
  "contact.waLink": { ar: "ابدأ محادثة", en: "Start a chat" },
  "contact.office": { ar: "مكتب المبيعات", en: "Sales office" },
  "contact.hours": { ar: "ساعات العمل", en: "Opening hours" },
  "contact.faqEyebrow": { ar: "أسئلة شائعة", en: "Common questions" },
  "contact.faqTitle": { ar: "قبل أن تسأل", en: "Before you ask" },
  "contact.q1": { ar: "هل يمكن لغير الأردنيين تملّك شقة؟", en: "Can non-Jordanians buy an apartment?" },
  "contact.a1": {
    ar: "نعم. يستطيع مواطنو الدول العربية والأجانب التملّك في الأردن بموافقة من مجلس الوزراء، ونتولى نحن تجهيز المعاملة ومتابعتها. المدة المعتادة بين شهرين وأربعة أشهر.",
    en: "Yes. Arab and foreign nationals may own property in Jordan subject to Cabinet approval, and we prepare and follow up the application for you. It usually takes two to four months.",
  },
  "contact.q2": { ar: "ما الذي يشمله السعر المعلن؟", en: "What does the quoted price include?" },
  "contact.a2": {
    ar: "السعر يشمل الوحدة بمساحتها الصافية وحصتها من المساحات المشتركة، والتشطيبات المذكورة في العقد، وموقف السيارة والمستودع. لا يشمل رسوم التسجيل الحكومية إلا إذا نُصّ على ذلك في خطة الدفع.",
    en: "The price covers the unit's net area and its share of common areas, the finishes listed in the contract, the parking bay and the store. Government registration fees are excluded unless your payment plan states otherwise.",
  },
  "contact.q3": { ar: "هل يمكن تعديل التشطيبات أو التوزيع الداخلي؟", en: "Can finishes or the internal layout be changed?" },
  "contact.a3": {
    ar: "يمكن تعديل التشطيبات ومواد الأرضيات والمطبخ قبل مرحلة معينة من التنفيذ. تعديل الجدران الداخلية غير الإنشائية ممكن أيضاً بموافقة المهندس المشرف وبفارق تكلفة يُحتسب مسبقاً.",
    en: "Finishes, flooring and the kitchen can be changed up to a defined construction stage. Non-structural internal walls can also be adjusted with the supervising engineer's approval, at a cost difference agreed in advance.",
  },
  "contact.q4": { ar: "ما هي الضمانات بعد التسليم؟", en: "What warranties apply after handover?" },
  "contact.a4": {
    ar: "سنتان على التشطيبات والأعمال الكهربائية والميكانيكية، وعشر سنوات على الهيكل الإنشائي، إضافةً إلى فريق صيانة يستجيب خلال ٤٨ ساعة في السنة الأولى.",
    en: "Two years on finishes and on electrical and mechanical works, ten years on the structure, plus a maintenance team that responds within 48 hours during the first year.",
  },

  /* 404 */
  "e404.title": { ar: "هذه الصفحة لم تعد موجودة", en: "This page is no longer here" },
  "e404.body": {
    ar: "ربما تغيّر رابط المشروع أو بيعت الوحدة. جرّب صفحة الوحدات المتاحة أو تواصل معنا مباشرةً.",
    en: "The project link may have changed, or the unit may have sold. Try the available units page, or contact us directly.",
  },

  /* misc */
  "misc.moreDetails": { ar: "تفاصيل أكثر", en: "More details" },
  "misc.readMore": { ar: "اقرأ المزيد", en: "Read more" },
  "misc.of": { ar: "من", en: "of" },
  "misc.image": { ar: "صورة", en: "Image" },
  "misc.rights": { ar: "جميع الحقوق محفوظة.", en: "All rights reserved." },
  "misc.placeholderNote": {
    ar: "الصور معالجات معمارية توضيحية للمشروع.",
    en: "Images are illustrative architectural studies of the scheme.",
  },
};

const LANGS = { ar: { dir: "rtl", locale: "ar-JO" }, en: { dir: "ltr", locale: "en-JO" } };

const I18N = {
  lang: "ar",

  /** Resolve a key, or a { ar, en } object, in the active language. */
  t(key, lang = I18N.lang) {
    const entry = typeof key === "string" ? T[key] : key;
    if (!entry) return typeof key === "string" ? key : "";
    return entry[lang] ?? entry.ar ?? "";
  },

  /** Format a number in Western digits, which is what Jordanian sites use. */
  num(value) {
    return new Intl.NumberFormat("en-US").format(Math.round(value));
  },

  /** Prices always read as a figure plus the currency word in-language. */
  price(value) {
    return `${I18N.num(value)} ${I18N.t("unit.jod")}`;
  },

  area(value) {
    return `${I18N.num(value)} ${I18N.t("unit.sqm")}`;
  },

  detect() {
    const fromUrl = new URLSearchParams(location.search).get("lang");
    const stored = (() => { try { return localStorage.getItem("dao-lang"); } catch { return null; } })();
    const lang = fromUrl || stored || document.documentElement.lang || "ar";
    return LANGS[lang] ? lang : "ar";
  },

  apply(lang, { persist = true } = {}) {
    if (!LANGS[lang]) lang = "ar";
    I18N.lang = lang;
    const { dir } = LANGS[lang];
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    document.body.dir = dir;
    if (persist) { try { localStorage.setItem("dao-lang", lang); } catch { /* private mode */ } }

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const value = I18N.t(el.dataset.i18n, lang);
      if (value) el.textContent = value;
    });
    // data-i18n-attr="placeholder:form.name, aria-label:cta.close"
    document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split(",").forEach((pair) => {
        const [attr, key] = pair.split(":").map((s) => s.trim());
        const value = I18N.t(key, lang);
        if (attr && value) el.setAttribute(attr, value);
      });
    });
    // Swap the <html lang> alternates and the visible switcher label
    document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
      btn.setAttribute("aria-label", I18N.t("lang.switchLabel", lang));
      btn.dataset.targetLang = lang === "ar" ? "en" : "ar";
    });
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang, dir } }));
  },

  toggle() {
    I18N.apply(I18N.lang === "ar" ? "en" : "ar");
    const url = new URL(location.href);
    url.searchParams.set("lang", I18N.lang);
    history.replaceState(null, "", url);
  },
};

if (typeof window !== "undefined") { window.I18N = I18N; window.T = T; }
