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
  "brand.tagline": { ar: "نبني مستقبلك", en: "We build your future" },

  /* home page */
  "home.eyebrow": { ar: "تطوير عقاري في مرج الحمام", en: "Residential development in Marj Al-Hamam" },
  "home.heroTitle": { ar: "شققٌ مبنيّة لتُسكن، لا لتُباع فقط.", en: "Apartments built to be lived in, not only sold." },
  "home.heroSub": {
    ar: "ثلاثة مشاريع في مرج الحمام: واحد مُسلَّم، وواحد متاح للبيع الآن، وثالث قادم. تشطيبات مذكورة بالاسم، ومواصفات مكتوبة.",
    en: "Three schemes in Marj Al-Hamam: one delivered, one selling now, a third on the way. Finishes named, specifications written down.",
  },
  "home.searchBtn": { ar: "اعرض الوحدات", en: "Show units" },
  "home.scroll": { ar: "تابع", en: "Scroll" },
  "home.projectsEyebrow": { ar: "المشاريع", en: "Projects" },
  "home.projectsTitle": { ar: "ثلاثة مشاريع في مرج الحمام", en: "Three schemes in Marj Al-Hamam" },
  "home.projectsLead": {
    ar: "مشروعٌ مُسلَّم، ومشروعٌ متاح للبيع الآن، وثالثٌ قيد التصميم.",
    en: "One scheme delivered, one selling now, and a third in design.",
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
  "home.ctaTitle": { ar: "احسب قسطك الشهري قبل أن تتصل", en: "Work out your instalment before you call" },
  "home.ctaBody": {
    ar: "اختر وحدة من المتاح، أو أدخل أي سعر، وستعرف القسط التقريبي خلال ثوانٍ. ثم تواصل معنا لمعرفة خطط الدفع على تلك الوحدة.",
    en: "Pick an available unit, or type any price, and see the approximate instalment in seconds. Then talk to us about the payment plans on that unit.",
  },
  "home.ctaBtn": { ar: "حاسبة الأقساط", en: "Instalment calculator" },

  /* footer */
  "footer.about": {
    ar: "شركة أردنية متخصصة في الشقق السكنية الفاخرة في مرج الحمام، عمّان.",
    en: "A Jordanian developer specialising in luxury apartments in Marj Al-Hamam, Amman.",
  },
  "footer.explore": { ar: "تصفّح", en: "Explore" },
  "footer.contact": { ar: "تواصل معنا", en: "Contact" },
  "footer.hours": { ar: "السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً", en: "Saturday – Thursday, 9:00 – 18:00" },
  "footer.rights": { ar: "شركة جنرال شيرمان للإسكان. جميع الحقوق محفوظة.", en: "General Sherman Housing. All rights reserved." },
  "footer.note": {
    ar: "الأسعار والتوفّر قابلة للتغيير دون إشعار مسبق.",
    en: "Prices and availability are subject to change without notice.",
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
  "project.nearbyEyebrow": { ar: "الموقع والخدمات", en: "Location and services" },
  "project.nearbyTitle": { ar: "ما حول المشروع", en: "What is around the project" },
  "project.nearbyLead": { ar: "أزمنة الوصول بالسيارة كما وردت في كتيّب المشروع.", en: "Drive times as published in the project brochure." },
  "unit.mins": { ar: "دقائق", en: "min" },
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
  "empty.projectsTitle": { ar: "لا توجد مشاريع معروضة حالياً", en: "No projects listed yet" },
  "empty.projectsBody": {
    ar: "سنعرض مشاريعنا وتفاصيل وحداتها على هذه الصفحة فور اعتمادها. للاستفسار عن المتاح الآن، تواصل معنا مباشرةً.",
    en: "Our schemes and their unit details will appear here as soon as they are released. To ask what is available now, contact us directly.",
  },
  "empty.unitsTitle": { ar: "لا توجد وحدات معروضة حالياً", en: "No units listed yet" },
  "empty.unitsBody": {
    ar: "سيُنشر جدول الوحدات المتاحة بأسعارها ومساحاتها هنا. للاستفسار عن المتاح الآن، تواصل معنا مباشرةً.",
    en: "The available units, with their prices and areas, will be published here. To ask what is available now, contact us directly.",
  },
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
  "projects.title": { ar: "منهج واحد في كل مشروع", en: "One method, every scheme" },
  "projects.lead": {
    ar: "نبني عدداً محدوداً من المشاريع في الوقت نفسه حتى يبقى كل مشروع تحت إشراف مباشر من فريقنا الهندسي حتى التسليم.",
    en: "We keep only a few schemes running at once, so each one stays under our own engineers' direct supervision through to handover.",
  },
  "projects.all": { ar: "جميع المشاريع", en: "All projects" },
  "status.selling": { ar: "متاح للبيع", en: "Now selling" },
  "status.delivered": { ar: "مُسلَّم", en: "Delivered" },
  "status.upcoming": { ar: "مشروع قادم", en: "Coming soon" },
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
  "plans.title": { ar: "احسب قسطك الشهري", en: "Work out your monthly instalment" },
  "plans.lead": {
    ar: "أداة تقديرية تساعدك على تقدير القسط قبل الحديث مع فريق المبيعات. لمعرفة خطط الدفع المتاحة لكل وحدة، تواصل معنا مباشرةً.",
    en: "An estimate to work from before you speak to the sales team. For the payment plans available on a specific unit, contact us directly.",
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
  "gallery.eyebrow": { ar: "المعرض", en: "Gallery" },
  "gallery.title": { ar: "الواجهات والمساحات والتفاصيل", en: "Elevations, spaces and details" },
  "gallery.lead": {
    ar: "معالجات معمارية تُظهر نيّة التصميم: كيف يدخل الضوء، وكيف تتوزع الشرفات، وكيف يبدو المبنى في ساعات النهار المختلفة.",
    en: "Architectural studies showing the design intent: how the light enters, how the balconies are arranged, and how the building reads at different hours.",
  },
  "gallery.all": { ar: "الكل", en: "All" },
  "gallery.sherman2": { ar: "جنرال شيرمان ٢", en: "General Sherman 2" },
  "gallery.exteriors": { ar: "الواجهات", en: "Exteriors" },
  "gallery.lobbies": { ar: "المداخل", en: "Lobbies" },
  "gallery.interiors": { ar: "المساحات الداخلية", en: "Interiors" },
  "gallery.note": {
    ar: "صور المشاريع المُسلَّمة فوتوغرافية. صور مشروع جنرال شيرمان ٣ تصاميم ثلاثية الأبعاد وقد تختلف عن التنفيذ النهائي.",
    en: "Photographs are of the delivered schemes. Images of General Sherman 3 are 3D design studies and may differ from the built result.",
  },

  /* about */
  "about.eyebrow": { ar: "من نحن", en: "Who we are" },
  "about.title": { ar: "مبنى واحد في كل مرة", en: "One building at a time" },
  "about.lead": {
    ar: "نبني عدداً محدوداً من المشاريع في الوقت نفسه، ونلتزم بالمواصفات وموعد التسليم كتابةً. هذه صفحة عن كيف نعمل، لا عن كم بنينا.",
    en: "We keep only a few schemes running at once, and we put the specification and the handover date in writing. This page is about how we work, not how much we have built.",
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
