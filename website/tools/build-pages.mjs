/**
 * Page scaffolder.
 *
 * The site is plain static HTML — every page in the repo is a finished file you
 * can open and edit directly. This script only exists so the shared chrome
 * (header, footer, WhatsApp button, dialogs, script tags) can be lifted from
 * index.html and stamped into the other pages when that chrome changes:
 *
 *   cd website && npm run pages
 *
 * If you edit the header in index.html, re-run it. If you are just editing the
 * body of one page, edit that page's HTML and ignore this file.
 */
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const index = await readFile(resolve(ROOT, "index.html"), "utf8");

const slice = (start, end, from = 0) => {
  const a = index.indexOf(start, from);
  const b = index.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error(`chrome block not found: ${start}`);
  return index.slice(a, b + end.length);
};

const HEADER = slice('<header class="header"', "</header>");
const FOOTER = slice('<footer class="footer">', "</footer>");
const FAB = slice('<a class="wa-fab"', "</a>");
const ENQUIRY = slice('<div class="modal" id="enquiry-modal"', "</div>\n</div>");
const SKIP = slice('<a class="skip-link"', "</a>");

const LIGHTBOX = `<div class="modal modal--lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="معرض الصور" hidden>
  <button class="modal__backdrop" tabindex="-1" aria-hidden="true"></button>
  <div class="modal__panel">
    <button class="lightbox__nav lightbox__nav--prev" type="button" aria-label="السابق" data-i18n-attr="aria-label:cta.prev">
      <span data-icon="chevron"></span></button>
    <div class="lightbox__body"></div>
    <button class="lightbox__nav lightbox__nav--next" type="button" aria-label="التالي" data-i18n-attr="aria-label:cta.next">
      <span data-icon="chevron"></span></button>
    <button class="modal__close" type="button" data-modal-close aria-label="إغلاق" data-i18n-attr="aria-label:cta.close"
      style="inset-block-start:-52px;inset-inline-end:0"><span data-icon="close"></span></button>
  </div>
</div>`;

const SITE = "https://www.generalsherman.jo";

function head({ file, title, desc, keywords = "", noindex = false }) {
  const url = `${SITE}/${file === "index.html" ? "" : file}`;
  return `<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<meta name="description" content="${desc}">${keywords ? `\n<meta name="keywords" content="${keywords}">` : ""}
${noindex ? '<meta name="robots" content="noindex">' : `<link rel="canonical" href="${url}">
<link rel="alternate" hreflang="ar" href="${url}">
<link rel="alternate" hreflang="en" href="${url}?lang=en">`}
<meta name="theme-color" content="#0F1518">
<meta property="og:type" content="website">
<meta property="og:site_name" content="شركة جنرال شيرمان للإسكان">
<meta property="og:title" content="${title}">
<meta property="og:description" content="${desc}">
<meta property="og:image" content="${SITE}/assets/img/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ar_JO">
<meta property="og:locale:alternate" content="en_US">
<meta property="og:url" content="${url}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preload" as="font" type="font/woff2" href="assets/fonts/plex-arabic-arabic-400.woff2" crossorigin>
<link rel="preload" as="font" type="font/woff2" href="assets/fonts/plex-arabic-arabic-600.woff2" crossorigin>
<link rel="stylesheet" href="assets/css/fonts.css">
<link rel="stylesheet" href="assets/css/main.css">`;
}

/** A dark page hero used by every inner page. */
function pageHero({ image, eyebrow, title, lead, crumb, extra = "" }) {
  return `  <section class="page-hero">
    <div class="page-hero__media">
      <img src="assets/img/${image}-1920.webp"
           srcset="assets/img/${image}-800.webp 800w, assets/img/${image}-1280.webp 1280w, assets/img/${image}-1920.webp 1920w"
           sizes="100vw" alt="" fetchpriority="high" width="1920" height="1080">
    </div>
    <div class="wrap">
      <ul class="crumbs">
        <li><a href="index.html" data-i18n="nav.home">الرئيسية</a></li>
        <li>${crumb}</li>
      </ul>
      <p class="eyebrow">${eyebrow}</p>
      <h1>${title}</h1>
      <p class="lead">${lead}</p>
      ${extra}
    </div>
  </section>`;
}

const PAGES = [];

/* ------------------------------------------------------------- projects */

PAGES.push({
  file: "projects.html",
  title: "مشاريعنا — شقق سكنية في عبدون ودير غبار والرابية | جنرال شيرمان",
  desc: "ثلاثة مشاريع سكنية من جنرال شيرمان في غرب عمّان: ريزيدنس ٧٦ في عبدون، ذا كريسنت في دير غبار، وحدائق الرابية.",
  keywords: "مشاريع سكنية عمان, شقق عبدون, شقق دير غبار, شقق الرابية",
  scripts: ["pages.js"],
  modals: [ENQUIRY],
  main: `
${pageHero({
    image: "hero-about",
    crumb: '<span data-i18n="nav.projects">مشاريعنا</span>',
    eyebrow: '<span data-i18n="projects.eyebrow">المشاريع</span>',
    title: '<span data-i18n="projects.title">ثلاثة مشاريع، ثلاث مناطق، منهج واحد</span>',
    lead: '<span data-i18n="projects.lead">نبني عدداً محدوداً من المشاريع في الوقت نفسه حتى يبقى كل مشروع تحت إشراف مباشر من فريقنا الهندسي حتى التسليم.</span>',
  })}

  <section class="section">
    <div class="wrap">
      <div class="tabs" id="project-filters" role="tablist">
        <button class="tab" role="tab" aria-selected="true" data-status="" data-i18n="projects.all">جميع المشاريع</button>
        <button class="tab" role="tab" aria-selected="false" data-status="ready" data-i18n="status.ready">جاهز للسكن</button>
        <button class="tab" role="tab" aria-selected="false" data-status="construction" data-i18n="status.construction">قيد الإنشاء</button>
      </div>
      <h2 class="sr-only" data-i18n="projects.eyebrow">المشاريع</h2>
      <div class="grid grid--3" id="projects-grid"></div>
    </div>
  </section>

  <section class="section section--stone">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="projects.mapEyebrow">أين نبني</p>
        <h2 data-i18n="projects.mapTitle">مناطق نعرفها جيداً</h2>
        <p class="lead" data-i18n="projects.mapLead">نعمل في نطاق جغرافي ضيق عمداً: ثلاث مناطق في غرب عمّان نعرف أسعار أراضيها وأنظمة البناء فيها وحركة الطلب عليها.</p>
      </div>
      <div class="grid grid--3">
        <article class="card reveal" style="padding:1.5rem">
          <h3 class="card__title" style="font-size:1.15rem" data-i18n="projects.d1Title">عبدون</h3>
          <p class="card__text" data-i18n="projects.d1Body">أعلى شريحة سعرية في عمّان، ومشترون يبحثون عن الخصوصية والمساحة الكبيرة أكثر من عدد الغرف.</p>
        </article>
        <article class="card reveal" style="padding:1.5rem">
          <h3 class="card__title" style="font-size:1.15rem" data-i18n="projects.d2Title">دير غبار</h3>
          <p class="card__text" data-i18n="projects.d2Body">أرض منحدرة تمنح إطلالات مفتوحة على الوادي، وهي الأنسب لمن يوازن بين السعر والموقع.</p>
        </article>
        <article class="card reveal" style="padding:1.5rem">
          <h3 class="card__title" style="font-size:1.15rem" data-i18n="projects.d3Title">الرابية</h3>
          <p class="card__text" data-i18n="projects.d3Body">كثافة بناء منخفضة ومساحات خارجية حقيقية، وهي الأنسب لمن يريد حديقة أو تراساً دون مغادرة عمّان.</p>
        </article>
      </div>
    </div>
  </section>`,
});

/* --------------------------------------------------------- project detail */

PAGES.push({
  file: "project.html",
  title: "تفاصيل المشروع | شركة جنرال شيرمان للإسكان",
  desc: "تفاصيل المشروع: المخططات، الوحدات المتاحة، جدول التوفّر، خطط الدفع، والموقع على الخريطة.",
  scripts: ["pages.js", "project.js"],
  modals: [ENQUIRY, LIGHTBOX],
  main: `
  <div id="project-page">
  <section class="page-hero">
    <div class="page-hero__media" id="p-hero-media"></div>
    <div class="wrap">
      <ul class="crumbs">
        <li><a href="index.html" data-i18n="nav.home">الرئيسية</a></li>
        <li><a href="projects.html" data-i18n="nav.projects">مشاريعنا</a></li>
        <li id="p-crumb"></li>
      </ul>
      <p><span class="badge" id="p-badge"></span></p>
      <h1 id="p-title" style="margin-block-start:1rem"></h1>
      <p class="lead" id="p-tagline"></p>
      <ul class="specs" id="p-meta" style="margin-block-start:1.5rem;color:rgba(250,247,241,.8);gap:.6rem 1.5rem"></ul>
      <div class="btn-row" style="margin-block-start:2rem">
        <a class="btn btn--brass" href="#availability" data-i18n="project.seeGrid">جدول التوفّر</a>
        <a class="btn btn--light" href="#" data-wa data-wa-project target="_blank" rel="noopener" data-i18n="cta.bookViewing">احجز زيارة</a>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap split split--wide">
      <div>
        <p class="eyebrow" data-i18n="project.aboutEyebrow">عن المشروع</p>
        <p class="lead" id="p-description"></p>
        <h2 style="font-size:var(--fs-h3);margin-block:2.5rem 1.25rem" data-i18n="project.highlights">أبرز ما يميّزه</h2>
        <ul class="tick-list" id="p-highlights"></ul>
      </div>
      <div>
        <div class="card" style="padding:clamp(1.4rem,3vw,2rem);gap:1rem">
          <h2 style="font-size:var(--fs-h3)" data-i18n="project.facts">أرقام المشروع</h2>
          <div class="unit-card__grid" id="p-facts" style="border:0;grid-template-columns:repeat(auto-fit,minmax(120px,1fr))"></div>
          <a class="btn btn--brass btn--block" href="#availability" data-i18n="project.seeGrid">جدول التوفّر</a>
        </div>
        <h2 style="font-size:var(--fs-h3);margin-block:2.5rem 1.25rem" data-i18n="project.amenities">مرافق المشروع</h2>
        <ul class="pill-list" id="p-amenities"></ul>
      </div>
    </div>
  </section>

  <section class="section section--stone" id="availability">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="grid.title">جدول توفّر الوحدات</p>
        <h2 data-i18n="project.gridTitle">اختر وحدتك من المبنى مباشرةً</h2>
        <p class="lead" data-i18n="grid.intro">كل خانة تمثّل وحدة فعلية في المبنى. اضغط على أي وحدة متاحة لعرض تفاصيلها.</p>
      </div>
      <div class="matrix-wrap">
        <table class="matrix" id="p-matrix"></table>
      </div>
      <ul class="legend" id="p-legend"></ul>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="nav.units">الوحدات المتاحة</p>
        <h2 data-i18n="project.unitsTitle">الوحدات في هذا المشروع</h2>
      </div>
      <div class="grid grid--3" id="p-units"></div>
      <p style="margin-block-start:2.5rem">
        <a class="link-arrow" id="p-units-more" href="units.html" hidden>
          <span data-i18n="project.allUnits">عرض جميع وحدات المشروع</span> <span data-icon="arrow" class="icon icon--dir"></span></a>
      </p>
    </div>
  </section>

  <section class="section section--paper">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="unit.plan">المخطط</p>
        <h2 data-i18n="project.plansTitle">المخططات الأفقية</h2>
        <p class="lead" data-i18n="project.plansLead">مخططات توضيحية بمقياس تقريبي. المساحات النهائية مذكورة في العقد.</p>
      </div>
      <div class="tabs" id="p-plan-tabs" role="tablist"></div>
      <div class="split split--wide">
        <div id="p-plan-img" class="reveal"></div>
        <div>
          <ul class="specs" id="p-plan-meta" style="gap:.75rem 1.5rem;margin-block-end:1.75rem"></ul>
          <h3 style="font-size:1.1rem;margin-block-end:1rem" data-i18n="project.legend">دليل الغرف</h3>
          <ul class="plan-legend" id="p-plan-legend"></ul>
          <p style="margin-block-start:2rem">
            <a class="btn btn--ghost" id="p-plan-dl" href="#" download>
              <span data-icon="download"></span><span data-i18n="cta.downloadPlan">تحميل المخطط</span></a>
          </p>
        </div>
      </div>
    </div>
  </section>

  <section class="section section--stone">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="nav.plans">خطط الدفع</p>
        <h2 data-i18n="project.paymentTitle">خطط الدفع المتاحة لهذا المشروع</h2>
      </div>
      <div class="grid grid--3" id="p-payment"></div>
      <p style="margin-block-start:2.5rem">
        <a class="link-arrow" href="payment-plans.html"><span data-i18n="project.calcLink">احسب قسطك الشهري</span> <span data-icon="arrow" class="icon icon--dir"></span></a>
      </p>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="project.location">الموقع</p>
        <h2 data-i18n="project.mapTitle">أين يقع المشروع</h2>
      </div>
      <div class="map-frame" id="p-map"></div>
      <p style="margin-block-start:1.5rem">
        <a class="link-arrow" id="p-map-link" href="#" target="_blank" rel="noopener">
          <span data-i18n="project.openMap">افتح في خرائط جوجل</span> <span data-icon="arrow" class="icon icon--dir"></span></a>
      </p>
    </div>
  </section>

  <section class="section section--paper">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="nav.gallery">معرض الصور</p>
        <h2 data-i18n="project.galleryTitle">صور المشروع</h2>
      </div>
      <div class="gallery-grid" id="p-gallery"></div>
    </div>
  </section>

  <section class="section section--stone">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="project.relatedEyebrow">مشاريع أخرى</p>
        <h2 data-i18n="project.relatedTitle">قد تهمّك أيضاً</h2>
      </div>
      <div class="grid grid--3" id="p-related"></div>
    </div>
  </section>
  </div>`,
});

/* ------------------------------------------------------------------ units */

PAGES.push({
  file: "units.html",
  title: "الوحدات المتاحة — شقق للبيع في عمّان بالمساحة والسعر | جنرال شيرمان",
  desc: "تصفّح جميع الشقق المتاحة للبيع في مشاريع جنرال شيرمان مع فلاتر للمنطقة وعدد الغرف والمساحة والسعر والطابق.",
  keywords: "شقق للبيع في عمان, أسعار الشقق في عمان, شقق 3 غرف عمان, شقق بحديقة عمان",
  scripts: ["pages.js", "units.js"],
  modals: [ENQUIRY],
  main: `
${pageHero({
    image: "hero-contact",
    crumb: '<span data-i18n="nav.units">الوحدات المتاحة</span>',
    eyebrow: '<span data-i18n="units.eyebrow">المخزون الحالي</span>',
    title: '<span data-i18n="units.title">كل وحدة متاحة، بسعرها ومساحتها</span>',
    lead: '<span data-i18n="units.lead">لا نُخفي الأسعار خلف نموذج تواصل. ما تراه هنا هو المخزون الفعلي المحدَّث، بما فيه الوحدات المحجوزة والمباعة.</span>',
  })}

  <section class="section">
    <div class="wrap">
      <form class="filters" id="filters" role="search" onsubmit="return false">
        <div class="filters__grid">
          <div><label for="f-project" data-i18n="filter.project">المشروع</label><select id="f-project" data-filter="project"></select></div>
          <div><label for="f-district" data-i18n="filter.district">المنطقة</label><select id="f-district" data-filter="district"></select></div>
          <div><label for="f-beds" data-i18n="filter.beds">غرف النوم</label><select id="f-beds" data-filter="beds"></select></div>
          <div><label for="f-type" data-i18n="filter.type">نوع الوحدة</label><select id="f-type" data-filter="type"></select></div>
          <div><label for="f-floor" data-i18n="filter.floor">الطابق</label><select id="f-floor" data-filter="floor"></select></div>
          <div><label for="f-minArea" data-i18n="filter.minArea">أقل مساحة (م²)</label><input id="f-minArea" data-filter="minArea" type="number" min="0" step="10" inputmode="numeric" placeholder="140"></div>
          <div><label for="f-maxPrice" data-i18n="filter.maxPrice">أعلى سعر (دينار)</label><input id="f-maxPrice" data-filter="maxPrice" type="number" min="0" step="5000" inputmode="numeric" placeholder="250000"></div>
          <div><label for="f-status" data-i18n="filter.status">الحالة</label><select id="f-status" data-filter="status"></select></div>
          <div><label for="f-sort" data-i18n="filter.sort">الترتيب</label><select id="f-sort" data-filter="sort"></select></div>
        </div>
        <div class="filters__foot">
          <p class="result-count" id="result-count"></p>
          <div class="chip-row" id="chips"></div>
          <button class="btn btn--ghost btn--sm" type="button" data-clear="all" data-i18n="cta.reset">مسح الفلاتر</button>
        </div>
      </form>

      <h2 class="sr-only" data-i18n="nav.units">الوحدات المتاحة</h2>
      <div class="grid grid--3" id="unit-grid" style="margin-block-start:2.5rem"></div>

      <p class="form-note" style="margin-block-start:2.5rem" data-i18n="units.note">الأسعار بالدينار الأردني وتشمل موقف السيارة والمستودع، ولا تشمل رسوم التسجيل ما لم يُذكر خلاف ذلك في خطة الدفع.</p>
    </div>
  </section>`,
});

/* --------------------------------------------------------- payment plans */

PAGES.push({
  file: "payment-plans.html",
  title: "خطط الدفع وحاسبة الأقساط — شركة جنرال شيرمان للإسكان",
  desc: "ثلاث خطط دفع: الحجز المبكر بخصم ٣٪، التسليم المريح بأقساط شهرية بدون فوائد، والتمويل البنكي حتى ٢٥ سنة. احسب قسطك الشهري على أي وحدة متاحة.",
  keywords: "خطط دفع شقق الأردن, تقسيط شقق عمان, حاسبة قرض سكني الأردن",
  scripts: ["pages.js", "plans.js"],
  modals: [],
  main: `
${pageHero({
    image: "hero-about",
    crumb: '<span data-i18n="nav.plans">خطط الدفع</span>',
    eyebrow: '<span data-i18n="plans.eyebrow">الدفع والتمويل</span>',
    title: '<span data-i18n="plans.title">ثلاث طرق لتملّك وحدتك</span>',
    lead: '<span data-i18n="plans.lead">اختر الخطة التي تناسب سيولتك، لا التي تناسبنا. جميع الأقساط الداخلية بدون فوائد أو رسوم إدارية.</span>',
  })}

  <section class="section">
    <div class="wrap">
      <h2 class="sr-only" data-i18n="nav.plans">خطط الدفع</h2>
      <div class="grid grid--3" id="plan-cards"></div>
    </div>
  </section>

  <section class="section section--stone" id="calculator">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="calc.title">حاسبة الأقساط</p>
        <h2 data-i18n="plans.calcTitle">كم سيكون قسطك الشهري؟</h2>
        <p class="lead" data-i18n="plans.calcLead">اختر وحدة من مخزوننا أو أدخل أي سعر، ثم عدّل الدفعة الأولى والمدة.</p>
      </div>

      <div class="calc">
        <div class="calc__panel">
          <div class="field" style="margin-block-end:1.5rem">
            <label for="c-unit" data-i18n="calc.pickUnit">اختر وحدة لتعبئة السعر</label>
            <select id="c-unit"></select>
          </div>
          <div class="field" style="margin-block-end:1.5rem">
            <label for="c-price" data-i18n="calc.price">سعر الوحدة (دينار)</label>
            <input id="c-price" type="number" min="20000" step="1000" inputmode="numeric">
          </div>

          <fieldset style="border:0;padding:0;margin:0 0 1.5rem">
            <legend class="field" style="padding:0"><span data-i18n="calc.plan">خطة الدفع</span></legend>
            <div class="plan-radios">
              <label class="plan-radio">
                <input type="radio" name="c-mode" value="company" checked>
                <span><strong data-i18n="plans.modeCompany">أقساط الشركة — بدون فوائد</strong>
                <span data-i18n="plans.modeCompanyNote">حتى ٥ سنوات، بدون فوائد أو رسوم إدارية.</span></span>
              </label>
              <label class="plan-radio">
                <input type="radio" name="c-mode" value="bank">
                <span><strong data-i18n="plans.modeBank">تمويل بنكي</strong>
                <span data-i18n="plans.modeBankNote">حتى ٢٥ سنة عبر البنوك الشريكة، بفائدة يحددها البنك.</span></span>
              </label>
            </div>
          </fieldset>

          <div class="field" style="margin-block-end:1.5rem">
            <div class="range-row"><label for="c-down" data-i18n="calc.down">الدفعة الأولى</label><output id="c-down-out">25%</output></div>
            <input id="c-down" type="range" min="10" max="60" step="5">
          </div>
          <div class="field" style="margin-block-end:1.5rem">
            <div class="range-row"><label for="c-years" data-i18n="calc.years">مدة التقسيط (سنوات)</label><output id="c-years-out">15</output></div>
            <input id="c-years" type="range" min="1" max="25" step="1">
          </div>
          <div class="field" id="c-rate-field">
            <div class="range-row"><label for="c-rate" data-i18n="calc.rate">الفائدة السنوية للبنك</label><output id="c-rate-out">6.5%</output></div>
            <input id="c-rate" type="range" min="3" max="10" step="0.25">
          </div>
        </div>

        <div class="calc__out">
          <p class="eyebrow" style="color:var(--brass-2)" data-i18n="calc.monthly">القسط الشهري التقريبي</p>
          <p class="calc__result num" id="c-monthly"></p>
          <dl class="calc__rows" id="c-rows"></dl>
          <p style="font-size:var(--fs-xs);color:#8E9BA1;margin-block-start:1.5rem" data-i18n="calc.disclaimer">الأرقام تقديرية لغرض التخطيط فقط ولا تمثّل عرضاً ملزماً.</p>
          <a class="btn btn--brass btn--block" style="margin-block-start:1.5rem" href="contact.html" data-i18n="plans.talkBtn">تحدّث مع فريق المبيعات</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap wrap--narrow">
      <div class="section-head">
        <p class="eyebrow" data-i18n="plans.faqEyebrow">أسئلة شائعة</p>
        <h2 data-i18n="plans.faqTitle">أسئلة عن الدفع والتملّك</h2>
      </div>
      <div class="accordion">
        <details>
          <summary data-i18n="plans.q1">هل يمكن تغيير خطة الدفع بعد التوقيع؟</summary>
          <div class="accordion__body" data-i18n="plans.a1">نعم، يمكن الانتقال من خطة إلى أخرى قبل التسليم بموافقة الطرفين وبإعادة جدولة مكتوبة تُلحق بالعقد. الانتقال إلى التمويل البنكي شائع عند اقتراب موعد التسليم.</div>
        </details>
        <details>
          <summary data-i18n="plans.q2">ماذا يحدث إذا تأخرت عن قسط؟</summary>
          <div class="accordion__body" data-i18n="plans.a2">هناك مهلة سماح ثلاثين يوماً بدون أي غرامة. بعدها نتواصل معك لإعادة الجدولة قبل اتخاذ أي إجراء تعاقدي — فسخ العقد هو الخيار الأخير لا الأول.</div>
        </details>
        <details>
          <summary data-i18n="plans.q3">هل يمكن السداد المبكر؟</summary>
          <div class="accordion__body" data-i18n="plans.a3">نعم، ودون أي رسوم على أقساط الشركة. أما في التمويل البنكي فتطبَّق شروط البنك المتعلقة بالسداد المبكر.</div>
        </details>
        <details>
          <summary data-i18n="plans.q4">ما هي الرسوم الحكومية المتوقعة؟</summary>
          <div class="accordion__body" data-i18n="plans.a4">رسوم التسجيل في دائرة الأراضي والمساحة تُحتسب كنسبة من قيمة العقد وتخضع للتشريعات النافذة وقت التسجيل. نوضح لك الرقم التقديري كتابةً قبل التوقيع، وخطة الحجز المبكر تشملها.</div>
        </details>
      </div>
    </div>
  </section>`,
});

/* ---------------------------------------------------------------- gallery */

PAGES.push({
  file: "gallery.html",
  title: "معرض الصور — مشاريع شركة جنرال شيرمان للإسكان في عمّان",
  desc: "معالجات معمارية للواجهات والمساحات الداخلية والمرافق المشتركة في مشاريع جنرال شيرمان بعمّان.",
  scripts: ["pages.js"],
  modals: [LIGHTBOX],
  main: `
${pageHero({
    image: "gallery-skyline-2",
    crumb: '<span data-i18n="nav.gallery">معرض الصور</span>',
    eyebrow: '<span data-i18n="gallery.eyebrow">المعرض</span>',
    title: '<span data-i18n="gallery.title">الواجهات والمساحات والتفاصيل</span>',
    lead: '<span data-i18n="gallery.lead">معالجات معمارية تُظهر نيّة التصميم: كيف يدخل الضوء، وكيف تتوزع الشرفات، وكيف يبدو المبنى في ساعات النهار المختلفة.</span>',
  })}

  <section class="section">
    <div class="wrap">
      <div class="tabs" id="gallery-filters" role="tablist">
        <button class="tab" role="tab" aria-selected="true" data-filter="" data-i18n="gallery.all">الكل</button>
        <button class="tab" role="tab" aria-selected="false" data-filter="project-" data-i18n="gallery.projects">المشاريع</button>
        <button class="tab" role="tab" aria-selected="false" data-filter="facade" data-i18n="gallery.facades">الواجهات</button>
        <button class="tab" role="tab" aria-selected="false" data-filter="interior" data-i18n="gallery.interiors">المساحات الداخلية</button>
        <button class="tab" role="tab" aria-selected="false" data-filter="courtyard" data-i18n="gallery.amenities">المرافق</button>
      </div>
      <div class="gallery-grid" id="gallery-grid"></div>
      <p class="form-note" style="margin-block-start:2.5rem" data-i18n="gallery.note">جميع الصور معالجات معمارية توضيحية أعدّها فريق التصميم، وقد تختلف عن التنفيذ النهائي في بعض التفاصيل.</p>
    </div>
  </section>`,
});

/* ------------------------------------------------------------------ about */

PAGES.push({
  file: "about.html",
  title: "عن الشركة — كيف تبني شركة جنرال شيرمان للإسكان في عمّان",
  desc: "كيف تختار جنرال شيرمان الأرض، وكيف تبني، وما الذي تضمنه بعد التسليم: أربعة التزامات ومسار واضح من الزيارة الأولى إلى تسليم المفتاح.",
  scripts: ["pages.js"],
  modals: [],
  main: `
${pageHero({
    image: "hero-about",
    crumb: '<span data-i18n="nav.about">عن الشركة</span>',
    eyebrow: '<span data-i18n="about.eyebrow">من نحن</span>',
    title: '<span data-i18n="about.title">مبنى واحد في كل مرة</span>',
    lead: '<span data-i18n="about.lead">نبني عدداً محدوداً من المشاريع في الوقت نفسه، ونلتزم بالمواصفات وموعد التسليم كتابةً. هذه صفحة عن كيف نعمل، لا عن كم بنينا.</span>',
  })}


  <section class="section section--stone">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="about.valuesEyebrow">كيف نعمل</p>
        <h2 data-i18n="about.valuesTitle">أربعة التزامات لا نساوم عليها</h2>
      </div>
      <div class="grid grid--4">
        <article class="card reveal" style="padding:1.75rem">
          <h3 class="card__title" style="font-size:1.1rem" data-i18n="about.v1Title">الأرض أولاً</h3>
          <p class="card__text" data-i18n="about.v1Body">نرفض أراضي كثيرة سنوياً بسبب الضجيج أو الإطلالة المحجوبة أو ضعف الوصول. المبنى الجيد على أرض سيئة يبقى استثماراً سيئاً.</p>
        </article>
        <article class="card reveal" style="padding:1.75rem">
          <h3 class="card__title" style="font-size:1.1rem" data-i18n="about.v2Title">التوزيع قبل الديكور</h3>
          <p class="card__text" data-i18n="about.v2Body">نصرف وقتاً أطول على مسار الحركة داخل الشقة وفصل جناح النوم عن الضيوف، أكثر مما نصرفه على واجهة المبنى.</p>
        </article>
        <article class="card reveal" style="padding:1.75rem">
          <h3 class="card__title" style="font-size:1.1rem" data-i18n="about.v3Title">ما لا يُرى</h3>
          <p class="card__text" data-i18n="about.v3Body">العزل الحراري والصوتي وتمديدات الميكانيك تُنفَّذ بمواصفات أعلى من الحد النظامي، لأن تعديلها بعد التسليم شبه مستحيل.</p>
        </article>
        <article class="card reveal" style="padding:1.75rem">
          <h3 class="card__title" style="font-size:1.1rem" data-i18n="about.v4Title">بعد التسليم</h3>
          <p class="card__text" data-i18n="about.v4Body">فريق الصيانة تابع للشركة وليس مقاولاً خارجياً، ويستجيب خلال ٤٨ ساعة في السنة الأولى.</p>
        </article>
      </div>
    </div>
  </section>

  <section class="section section--paper">
    <div class="wrap">
      <div class="section-head">
        <p class="eyebrow" data-i18n="home.processEyebrow">كيف نعمل</p>
        <h2 data-i18n="home.processTitle">من الزيارة الأولى إلى تسليم المفتاح</h2>
      </div>
      <div class="steps" id="home-process"></div>
    </div>
  </section>


  <section class="section section--stone">
    <div class="wrap">
      <div class="cta-band">
        <div>
          <h2 data-i18n="about.ctaTitle">تعال شاهد المشاريع على الطبيعة</h2>
          <p data-i18n="about.ctaBody">جولة الموقع تستغرق نحو ساعة، ونرافقك فيها بأنفسنا — بما في ذلك المشاريع قيد الإنشاء.</p>
        </div>
        <div class="btn-row">
          <a class="btn btn--brass" href="contact.html" data-i18n="cta.bookViewing">احجز زيارة</a>
          <a class="btn btn--light" href="#" data-wa target="_blank" rel="noopener" data-i18n="cta.whatsapp">واتساب</a>
        </div>
      </div>
    </div>
  </section>`,
});

/* ---------------------------------------------------------------- contact */

PAGES.push({
  file: "contact.html",
  title: "اتصل بنا — شركة جنرال شيرمان للإسكان، عمّان",
  desc: "تواصل مع فريق مبيعات جنرال شيرمان: هاتف، واتساب، بريد إلكتروني، أو احجز زيارة لأحد المشاريع في عمّان.",
  scripts: ["pages.js"],
  modals: [],
  main: `
${pageHero({
    image: "hero-contact",
    crumb: '<span data-i18n="nav.contact">اتصل بنا</span>',
    eyebrow: '<span data-i18n="contact.eyebrow">تواصل معنا</span>',
    title: '<span data-i18n="contact.title">تحدّث مع من يعرف المبنى</span>',
    lead: '<span data-i18n="contact.lead">فريق المبيعات لدينا مهندسون، لا وسطاء. اسألهم عن العزل أو المصاعد أو نسبة الإنجاز وستحصل على إجابة دقيقة.</span>',
  })}

  <section class="section">
    <div class="wrap split split--wide" style="align-items:start">
      <div>
        <h2 style="font-size:var(--fs-h3);margin-block-end:1.5rem" data-i18n="contact.formTitle">أرسل استفسارك</h2>
        <form class="form" data-form data-subject="استفسار من صفحة اتصل بنا" novalidate>
          <input class="sr-only" type="text" name="_gotcha" tabindex="-1" autocomplete="off" aria-hidden="true">
          <div class="form__row">
            <div class="field">
              <label for="c-name" data-i18n="form.name">الاسم الكامل</label>
              <input id="c-name" name="name" type="text" required autocomplete="name">
            </div>
            <div class="field">
              <label for="c-phone" data-i18n="form.phone">رقم الهاتف</label>
              <input id="c-phone" name="phone" type="tel" required autocomplete="tel" inputmode="tel" placeholder="07 9000 0000">
            </div>
          </div>
          <div class="form__row">
            <div class="field">
              <label for="c-email" data-i18n="form.email">البريد الإلكتروني</label>
              <input id="c-email" name="email" type="email" autocomplete="email">
            </div>
            <div class="field">
              <label for="contact-project" data-i18n="form.interest">المشروع الذي يهمّك</label>
              <select id="contact-project" name="project"></select>
            </div>
          </div>
          <div class="field">
            <label for="c-message" data-i18n="form.message">رسالتك</label>
            <textarea id="c-message" name="message" rows="5" required></textarea>
          </div>
          <label class="consent">
            <input type="checkbox" name="consent" required>
            <span data-i18n="form.consent">أوافق على أن تتواصل معي جنرال شيرمان بخصوص هذا الطلب.</span>
          </label>
          <button class="btn btn--brass" type="submit" data-i18n="form.send">إرسال الطلب</button>
          <p class="form-note" data-i18n="contact.formNote">نرد على الاستفسارات خلال يوم عمل واحد. إذا كان طلبك عاجلاً، الاتصال أو واتساب أسرع.</p>
        </form>
      </div>

      <div>
        <div class="card" style="padding:clamp(1.4rem,3vw,2rem)">
          <h2 style="font-size:var(--fs-h3);margin-block-end:1.25rem" data-i18n="contact.directTitle">تواصل مباشر</h2>
          <ul class="tick-list" style="gap:1.25rem">
            <li><span data-icon="phone"></span><span><strong data-i18n="cta.call">اتصل بنا</strong><br>
              <a data-tel href="#" data-company-phone class="link-arrow">+962 6 552 0176</a></span></li>
            <li><span data-icon="whatsapp"></span><span><strong data-i18n="cta.whatsapp">واتساب</strong><br>
              <a data-wa href="#" target="_blank" rel="noopener" class="link-arrow" data-i18n="contact.waLink">ابدأ محادثة</a></span></li>
            <li><span data-icon="mail"></span><span><strong data-i18n="form.email">البريد الإلكتروني</strong><br>
              <a data-mail="sales" href="#" class="link-arrow">sales@generalsherman.jo</a></span></li>
            <li><span data-icon="pin"></span><span><strong data-i18n="contact.office">مكتب المبيعات</strong><br>
              <span data-i18n="footer.address">شارع عبد الله غوشة، مبنى ٤٦، الطابق الثالث، عمّان ١١١٩٤، الأردن</span></span></li>
            <li><span data-icon="clock"></span><span><strong data-i18n="contact.hours">ساعات العمل</strong><br>
              <span data-i18n="footer.hours">السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً</span></span></li>
          </ul>
        </div>
        <div class="map-frame" id="contact-map" style="margin-block-start:1.5rem"></div>
      </div>
    </div>
  </section>

  <section class="section section--stone">
    <div class="wrap wrap--narrow">
      <div class="section-head">
        <p class="eyebrow" data-i18n="contact.faqEyebrow">أسئلة شائعة</p>
        <h2 data-i18n="contact.faqTitle">قبل أن تسأل</h2>
      </div>
      <div class="accordion">
        <details>
          <summary data-i18n="contact.q1">هل يمكن لغير الأردنيين تملّك شقة؟</summary>
          <div class="accordion__body" data-i18n="contact.a1">نعم. يستطيع مواطنو الدول العربية والأجانب التملّك في الأردن بموافقة من مجلس الوزراء، ونتولى نحن تجهيز المعاملة ومتابعتها. المدة المعتادة بين شهرين وأربعة أشهر.</div>
        </details>
        <details>
          <summary data-i18n="contact.q2">ما الذي يشمله السعر المعلن؟</summary>
          <div class="accordion__body" data-i18n="contact.a2">السعر يشمل الوحدة بمساحتها الصافية وحصتها من المساحات المشتركة، والتشطيبات المذكورة في العقد، وموقف السيارة والمستودع. لا يشمل رسوم التسجيل الحكومية إلا إذا نُصّ على ذلك في خطة الدفع.</div>
        </details>
        <details>
          <summary data-i18n="contact.q3">هل يمكن تعديل التشطيبات أو التوزيع الداخلي؟</summary>
          <div class="accordion__body" data-i18n="contact.a3">يمكن تعديل التشطيبات ومواد الأرضيات والمطبخ قبل مرحلة معينة من التنفيذ. تعديل الجدران الداخلية غير الإنشائية ممكن أيضاً بموافقة المهندس المشرف وبفارق تكلفة يُحتسب مسبقاً.</div>
        </details>
        <details>
          <summary data-i18n="contact.q4">ما هي الضمانات بعد التسليم؟</summary>
          <div class="accordion__body" data-i18n="contact.a4">سنتان على التشطيبات والأعمال الكهربائية والميكانيكية، وعشر سنوات على الهيكل الإنشائي، إضافةً إلى فريق صيانة يستجيب خلال ٤٨ ساعة في السنة الأولى.</div>
        </details>
      </div>
    </div>
  </section>`,
});

/* -------------------------------------------------------------------- 404 */

PAGES.push({
  file: "404.html",
  title: "الصفحة غير موجودة | شركة جنرال شيرمان للإسكان",
  desc: "الصفحة المطلوبة غير موجودة.",
  noindex: true,
  scripts: ["pages.js"],
  modals: [],
  main: `
  <section class="section" style="padding-block-start:calc(var(--header-h) + 6rem);text-align:center">
    <div class="wrap wrap--narrow">
      <p class="eyebrow" style="justify-content:center">404</p>
      <h1 data-i18n="e404.title">هذه الصفحة لم تعد موجودة</h1>
      <p class="lead" style="margin-block:1.25rem 2.5rem" data-i18n="e404.body">ربما تغيّر رابط المشروع أو بيعت الوحدة. جرّب صفحة الوحدات المتاحة أو تواصل معنا مباشرةً.</p>
      <div class="btn-row" style="justify-content:center">
        <a class="btn btn--brass" href="units.html" data-i18n="cta.viewUnits">تصفّح الوحدات المتاحة</a>
        <a class="btn btn--ghost" href="index.html" data-i18n="nav.home">الرئيسية</a>
      </div>
    </div>
  </section>`,
});

/* ------------------------------------------------------------------ write */

for (const page of PAGES) {
  const scripts = ["data.js", "i18n.js", "app.js", ...page.scripts]
    .map((s) => `<script src="assets/js/${s}"></script>`).join("\n");
  const html = `<!doctype html>
<html lang="ar" dir="rtl">
<head>
${head(page)}
</head>
<body>
${SKIP}

${HEADER}

<main id="main">
${page.main}
</main>

${FOOTER}

${FAB}

${(page.modals || []).join("\n\n")}

${scripts}
</body>
</html>
`;
  await writeFile(resolve(ROOT, page.file), html);
  console.log("  ✓", page.file);
}
console.log("Done.");
