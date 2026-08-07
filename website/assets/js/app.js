/* =============================================================================
   Shared behaviour: header, navigation, language switch, reveals, modals,
   lightbox, forms, and the render helpers the page modules build on.
   ========================================================================== */

const IMG_WIDTHS = [480, 800, 1280, 1920];
const BASE = document.documentElement.dataset.base || "";

/* ------------------------------------------------------------------ icons */

const ICONS = {
  bed: '<path d="M2 17v-6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v6M2 17v3M22 17v3M2 17h20M6 9V7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"/>',
  bath: '<path d="M4 12V6a2 2 0 0 1 4 0M2 12h20v3a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4v-3ZM6 19l-1 2M18 19l1 2"/>',
  area: '<path d="M3 3h18v18H3zM9 3v18M3 9h18"/>',
  floor: '<path d="M3 20h4v-4h5v-4h5V8h4"/><path d="M3 20V4"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/>',
  mail: '<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/><path d="m22 7-10 6L2 7"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  download: '<path d="M12 3v12M7 11l5 5 5-5M4 21h16"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  building: '<path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h2a2 2 0 0 1 2 2v10M8 7h4M8 11h4M8 15h4M2 21h20"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m11 12 8-8 3 3-2 2-2-2-2 2 2 2-3 3-2-2"/>',
  gym: '<path d="M6 6v12M18 6v12M3 9v6M21 9v6M6 12h12"/>',
  pool: '<path d="M2 18c2 0 2-1.5 4-1.5S8 18 10 18s2-1.5 4-1.5S16 18 18 18s2-1.5 4-1.5M6 14V5a2 2 0 0 1 4 0v9M14 14V5a2 2 0 0 1 4 0v9M6 8h4M14 8h4"/>',
  reception: '<path d="M4 18h16M6 18v-4a6 6 0 0 1 12 0v4M12 5V3M9 21h6"/>',
  generator: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
  parking: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V7h3.5a3 3 0 0 1 0 6H9"/>',
  security: '<path d="M12 3 5 6v5c0 4.5 3 8.5 7 10 4-1.5 7-5.5 7-10V6l-7-3Z"/><path d="m9.5 12 1.8 1.8L15 10"/>',
  elevator: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="m9 9 1.5-2L12 9M12 15l1.5 2L15 15M12 3v18"/>',
  storage: '<path d="M3 8 12 3l9 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8Z"/><path d="M9 21v-7h6v7"/>',
  garden: '<path d="M12 22v-6M12 16c-3.5 0-6-2.5-6-6s2.5-7 6-7 6 3.5 6 7-2.5 6-6 6ZM5 22h14"/>',
  playground: '<path d="M4 21V9l8-6 8 6v12M9 21v-6h6v6M2 9h20"/>',
  whatsapp: '<path d="M12.04 2A9.9 9.9 0 0 0 2.1 11.9a9.8 9.8 0 0 0 1.4 5.1L2 22l5.2-1.4a9.9 9.9 0 0 0 4.8 1.2h.01A9.9 9.9 0 0 0 22 11.9 9.9 9.9 0 0 0 12.04 2Zm5.8 14.1c-.25.7-1.45 1.35-2 1.4-.5.05-1.15.08-1.85-.12a16 16 0 0 1-1.7-.63c-3-1.3-4.95-4.3-5.1-4.5-.15-.2-1.2-1.6-1.2-3.05s.75-2.17 1.02-2.47c.27-.3.6-.37.8-.37h.57c.18 0 .43-.07.67.52l.92 2.23c.07.15.12.33.02.53l-.35.5c-.12.15-.26.33-.11.63.15.3.66 1.1 1.42 1.78.98.87 1.8 1.14 2.1 1.29.3.15.47.12.65-.08l.92-1.07c.2-.25.4-.2.67-.1l1.9.9c.28.15.47.22.54.35.07.12.07.72-.18 1.42Z" stroke="none" fill="currentColor"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/>',
  facebook: '<path d="M14 8.5h2.5V5.2h-2.6c-2.4 0-3.9 1.6-3.9 4v2H8v3.3h2v7h3.3v-7h2.4l.5-3.3h-2.9V9.5c0-.7.3-1 .7-1Z" fill="currentColor" stroke="none"/>',
  linkedin: '<path d="M6.94 6.5A1.94 1.94 0 1 1 3.06 6.5a1.94 1.94 0 0 1 3.88 0ZM3.4 20.5h3.1V9.4H3.4v11.1Zm6 0h3.1v-6.2c0-1.6 1.9-1.8 2.6-.5v6.7h3.1v-6.9c0-3.6-3.6-3.5-5.7-1.7V9.4H9.4v11.1Z" fill="currentColor" stroke="none"/>',
  youtube: '<path d="M21.5 7.6a2.6 2.6 0 0 0-1.8-1.8C18 5.3 12 5.3 12 5.3s-6 0-7.7.5A2.6 2.6 0 0 0 2.5 7.6 27 27 0 0 0 2 12a27 27 0 0 0 .5 4.4 2.6 2.6 0 0 0 1.8 1.8c1.7.5 7.7.5 7.7.5s6 0 7.7-.5a2.6 2.6 0 0 0 1.8-1.8A27 27 0 0 0 22 12a27 27 0 0 0-.5-4.4ZM10.2 14.9V9.1l4.8 2.9-4.8 2.9Z" fill="currentColor" stroke="none"/>',
};

function iconSvg(name, cls = "icon") {
  const path = ICONS[name];
  if (!path) return "";
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${path}</svg>`;
}

/** Replace <span data-icon="bed"></span> placeholders in static markup. */
function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    if (el.dataset.iconDone) return;
    el.outerHTML = iconSvg(el.dataset.icon, el.className || "icon");
  });
}

/* ------------------------------------------------------------- DOM helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/**
 * Responsive <img>.
 *
 * The srcset lists only the widths that exist on disk, from IMG_VARIANTS in
 * img-manifest.js. Most of the brochure photographs top out at 480px — they
 * are phone pictures embedded in a PDF — and offering the browser a 1280 that
 * is not there means a 404 on exactly the wide viewports where it picks the
 * largest candidate. A name absent from the manifest falls back to all four
 * widths, so a newly dropped-in image still renders before `npm run manifest`
 * has been run.
 */
function picture(name, alt, { sizes = "100vw", cls = "", eager = false, ratio = "" } = {}) {
  const widths = (typeof IMG_VARIANTS !== "undefined" && IMG_VARIANTS[name]) || IMG_WIDTHS;
  const srcset = widths.map((w) => `${BASE}assets/img/${name}-${w}.webp ${w}w`).join(", ");
  const fallback = widths.includes(1280) ? 1280 : widths[widths.length - 1];
  return `<img src="${BASE}assets/img/${name}-${fallback}.webp" srcset="${srcset}" sizes="${sizes}"
    alt="${esc(alt)}" class="${cls}" ${ratio ? `style="aspect-ratio:${ratio}"` : ""}
    loading="${eager ? "eager" : "lazy"}" decoding="async" ${eager ? 'fetchpriority="high"' : ""} width="1280" height="720">`;
}

/**
 * Remove the section a renderer feeds, given its container's selector.
 * Renderers re-run on every language change, by which time the section they
 * dropped is already gone — so a missing element is success, not an error.
 */
function dropSection(sel) {
  document.querySelector(sel)?.closest("section")?.remove();
}

const t = (k) => window.I18N.t(k);
const tx = (obj) => window.I18N.t(obj);

/* ------------------------------------------------------------------ links */

function waLink(message) {
  const { COMPANY } = window.DATA;
  return `https://wa.me/${COMPANY.whatsapp}?text=${encodeURIComponent(message)}`;
}

function wireContactLinks() {
  const { COMPANY } = window.DATA;
  $$("[data-wa]").forEach((a) => {
    const custom = a.dataset.wa;
    const msg = custom || (I18N.lang === "ar"
      ? `مرحباً ${COMPANY.short.ar}، أود الاستفسار عن الوحدات المتاحة.`
      : `Hello ${COMPANY.short.en}, I would like to ask about the available units.`);
    a.href = waLink(msg);
  });
  $$("[data-tel]").forEach((a) => { a.href = `tel:${COMPANY.phoneHref}`; });
  $$("[data-mail]").forEach((a) => { a.href = `mailto:${a.dataset.mail === "sales" ? COMPANY.salesEmail : COMPANY.email}`; });
}

/* ----------------------------------------------------------------- header */

function initHeader() {
  const header = $(".header");
  if (!header) return;
  const floating = header.dataset.float === "true";

  const onScroll = () => {
    const solid = window.scrollY > 24 || !floating || document.body.classList.contains("nav-open");
    header.classList.toggle("header--solid", solid);
    header.classList.toggle("header--float", !solid);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  const burger = $(".burger");
  burger?.addEventListener("click", () => {
    const open = document.body.classList.toggle("nav-open");
    burger.setAttribute("aria-expanded", String(open));
    onScroll();
  });
  $$(".nav a").forEach((a) => a.addEventListener("click", () => {
    document.body.classList.remove("nav-open");
    burger?.setAttribute("aria-expanded", "false");
    onScroll();
  }));
  window.addEventListener("resize", () => {
    if (window.innerWidth > 960) {
      document.body.classList.remove("nav-open");
      burger?.setAttribute("aria-expanded", "false");
    }
  });
}

/* ---------------------------------------------------------------- reveals */

function initReveals() {
  const items = $$(".reveal");
  if (!items.length || !("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("is-in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (!entry.isIntersecting) return;
      const delay = Math.min(i * 70, 280);
      setTimeout(() => entry.target.classList.add("is-in"), delay);
      io.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  items.forEach((el) => io.observe(el));
}

/* ----------------------------------------------------------------- modals */

let lastFocused = null;

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  lastFocused = document.activeElement;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  const focusable = modal.querySelector("input, select, textarea, button:not(.modal__backdrop)");
  focusable?.focus({ preventScroll: true });
}

function closeModal(modal) {
  modal = typeof modal === "string" ? document.getElementById(modal) : modal;
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  document.body.style.overflow = "";
  lastFocused?.focus?.({ preventScroll: true });
}

function initModals() {
  document.addEventListener("click", (e) => {
    const opener = e.target.closest("[data-modal-open]");
    if (opener) { e.preventDefault(); openModal(opener.dataset.modalOpen); return; }
    if (e.target.closest("[data-modal-close]") || e.target.classList.contains("modal__backdrop")) {
      closeModal(e.target.closest(".modal"));
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$(".modal:not([hidden])").forEach(closeModal);
    if (e.key !== "Tab") return;
    const modal = $(".modal:not([hidden])");
    if (!modal) return;
    // Keep focus inside the open dialog.
    const items = $$('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])', modal)
      .filter((el) => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
}

/* --------------------------------------------------------------- lightbox */

const lightbox = { items: [], index: 0 };

function openLightbox(items, index) {
  lightbox.items = items;
  lightbox.index = index;
  renderLightbox();
  openModal("lightbox");
}

function renderLightbox() {
  const box = $("#lightbox .lightbox__body");
  if (!box) return;
  const item = lightbox.items[lightbox.index];
  if (!item) return;
  box.innerHTML = `
    ${picture(item.name, item.caption, { sizes: "(max-width: 1200px) 100vw, 1180px" })}
    <p class="lightbox__caption">${esc(item.caption)} <span style="opacity:.6">— ${lightbox.index + 1} ${t("misc.of")} ${lightbox.items.length}</span></p>`;
}

function stepLightbox(delta) {
  if (!lightbox.items.length) return;
  lightbox.index = (lightbox.index + delta + lightbox.items.length) % lightbox.items.length;
  renderLightbox();
}

function initLightbox() {
  document.addEventListener("click", (e) => {
    const prev = e.target.closest(".lightbox__nav--prev");
    const next = e.target.closest(".lightbox__nav--next");
    if (prev) stepLightbox(-1);
    if (next) stepLightbox(1);
  });
  document.addEventListener("keydown", (e) => {
    if ($("#lightbox")?.hidden !== false) return;
    if (e.key === "ArrowRight") stepLightbox(document.dir === "rtl" ? -1 : 1);
    if (e.key === "ArrowLeft") stepLightbox(document.dir === "rtl" ? 1 : -1);
  });
}

/* ------------------------------------------------------------------ forms */

const PHONE_RE = /^[+()\d\s-]{8,20}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function fieldError(input, key) {
  // The consent checkbox lives in a .consent label rather than a .field, and
  // its message has to land on the label itself to be seen.
  const wrap = input.closest(".field, .consent");
  if (!wrap) return;
  wrap.classList.add("field--invalid");
  let err = wrap.querySelector(".field__error");
  if (!err) {
    err = document.createElement("p");
    err.className = "field__error";
    wrap.appendChild(err);
  }
  err.textContent = t(key);
  input.setAttribute("aria-invalid", "true");
}

function clearError(input) {
  const wrap = input.closest(".field, .consent");
  wrap?.classList.remove("field--invalid");
  input.removeAttribute("aria-invalid");
}

function validateForm(form) {
  let firstBad = null;
  $$("input, select, textarea", form).forEach((input) => {
    clearError(input);
    const val = input.type === "checkbox" ? input.checked : input.value.trim();
    let bad = null;
    if (input.required && !val) {
      bad = input.type === "checkbox" ? "form.errConsent"
        : input.name === "name" ? "form.errName" : "form.errRequired";
    } else if (val && input.name === "phone" && !PHONE_RE.test(input.value.trim())) {
      bad = "form.errPhone";
    } else if (val && input.type === "email" && !EMAIL_RE.test(input.value.trim())) {
      bad = "form.errEmail";
    } else if (val && input.name === "name" && String(val).length < 3) {
      bad = "form.errName";
    }
    if (bad) { fieldError(input, bad); firstBad = firstBad || input; }
  });
  firstBad?.focus();
  return !firstBad;
}

/** Turn the form into the WhatsApp message a salesperson can act on. */
function formToMessage(form) {
  const { COMPANY } = window.DATA;
  const ar = I18N.lang === "ar";
  const lines = [ar ? `مرحباً ${COMPANY.short.ar}،` : `Hello ${COMPANY.short.en},`, ""];
  const subject = form.dataset.subject;
  if (subject) lines.push(subject, "");
  $$("input, select, textarea", form).forEach((input) => {
    if (input.type === "checkbox" || !input.value.trim() || input.name === "_gotcha") return;
    const label = input.closest(".field")?.querySelector("label")?.textContent?.replace(/\s*\(.*\)\s*$/, "") || input.name;
    const value = input.tagName === "SELECT" ? input.options[input.selectedIndex].text : input.value.trim();
    lines.push(`${label}: ${value}`);
  });
  return lines.join("\n");
}

function showStatus(form, kind, key, extra = "") {
  let box = form.querySelector(".form-status");
  if (!box) {
    box = document.createElement("div");
    box.className = "form-status";
    box.setAttribute("role", "status");
    form.prepend(box);
  }
  box.className = `form-status form-status--${kind}`;
  box.innerHTML = `<strong>${kind === "ok" ? t("form.okTitle") : ""}</strong> ${t(key)} ${extra}`;
  box.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function submitForm(form) {
  const { COMPANY } = window.DATA;
  const btn = form.querySelector('[type="submit"]');
  const original = btn?.textContent;
  const message = formToMessage(form);

  if (COMPANY.formEndpoint) {
    try {
      if (btn) { btn.disabled = true; btn.textContent = t("form.sending"); }
      const res = await fetch(COMPANY.formEndpoint, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: new FormData(form),
      });
      if (!res.ok) throw new Error(String(res.status));
      form.reset();
      showStatus(form, "ok", "form.okPosted");
    } catch {
      const mail = `mailto:${COMPANY.salesEmail}?subject=${encodeURIComponent(form.dataset.subject || "Enquiry")}&body=${encodeURIComponent(message)}`;
      showStatus(form, "err", "form.errSend", `<a class="link-arrow" href="${mail}">${t("form.emailFallback")}</a>`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = original; }
    }
    return;
  }

  // No endpoint configured: hand the enquiry to WhatsApp, keep email as backup.
  window.open(waLink(message), "_blank", "noopener");
  const mail = `mailto:${COMPANY.salesEmail}?subject=${encodeURIComponent(form.dataset.subject || "Enquiry")}&body=${encodeURIComponent(message)}`;
  showStatus(form, "ok", "form.okWhatsapp", `<a class="link-arrow" href="${mail}">${t("form.emailFallback")}</a>`);
  form.reset();
}

function initForms() {
  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-form]");
    if (!form) return;
    e.preventDefault();
    if (form.querySelector('[name="_gotcha"]')?.value) return; // honeypot
    if (validateForm(form)) submitForm(form);
  });
  document.addEventListener("input", (e) => {
    if (e.target.matches("input, select, textarea") && e.target.getAttribute("aria-invalid")) clearError(e.target);
  });
}

/* ------------------------------------------------------------ shared bits */

function initLangSwitch() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang-toggle]");
    if (!btn) return;
    e.preventDefault();
    window.I18N.toggle();
    wireContactLinks();
  });
}

function initFooter() {
  const { COMPANY } = window.DATA;
  $$("[data-year]").forEach((el) => { el.textContent = new Date().getFullYear(); });
  $$("[data-company-phone]").forEach((el) => { el.textContent = COMPANY.phone; });
  $$("[data-company-email]").forEach((el) => { el.textContent = COMPANY.email; });
}

/** Mark the current page in the navigation. */
function initCurrentNav() {
  const here = location.pathname.split("/").pop() || "index.html";
  $$(".nav a").forEach((a) => {
    const target = a.getAttribute("href").split("/").pop().split("?")[0];
    if (target === here) a.setAttribute("aria-current", "page");
  });
}

/* --------------------------------------------------------------- renderers
   Used by several pages, so they live here rather than in a page module.
   -------------------------------------------------------------------------- */

function projectCard(project) {
  const { UNITS, DISTRICTS, PROJECT_STATUS } = window.DATA;
  const units = UNITS.filter((u) => u.projectId === project.id);
  const available = units.filter((u) => u.status === "available" && u.price);
  // Sold out is inferred only for a project that says it is selling.
  const status = units.length && !available.length && project.status === "selling" ? "soldout" : project.status;
  const badge = status && PROJECT_STATUS[status] ? `<span class="badge badge--${status} badge--on-media">${tx(PROJECT_STATUS[status])}</span>` : "";
  const priced = available.length ? Math.min(...available.map((u) => u.price)) : null;

  const facts = [];
  if (units.length) facts.push(`${iconSvg("building")} ${units.length} ${t("project.units")}`);
  if (available.length) facts.push(`${iconSvg("key")} ${available.length} ${t("project.available")}`);
  if (project.delivery) facts.push(`${iconSvg("calendar")} ${tx(project.delivery)}`);

  return `
  <article class="card reveal">
    <a class="card__media" href="${BASE}project.html?id=${project.id}" aria-label="${esc(tx(project.name))}">
      ${picture(project.image, tx(project.name), { sizes: "(max-width: 700px) 92vw, (max-width: 1100px) 45vw, 400px" })}
      ${badge}
    </a>
    <div class="card__body">
      ${project.district ? `<p class="card__meta">${iconSvg("pin")} ${tx(DISTRICTS[project.district])}</p>` : ""}
      <h3 class="card__title"><a href="${BASE}project.html?id=${project.id}">${tx(project.name)}</a></h3>
      <p class="card__text">${tx(project.tagline)}</p>
      ${facts.length ? `<ul class="specs">${facts.map((f) => `<li>${f}</li>`).join("")}</ul>` : ""}
      <div class="card__foot">
        ${priced
          ? `<p class="card__price num">${window.I18N.price(priced)} <small>${t("unit.priceFrom")}</small></p>`
          : `<p class="card__price" style="font-size:var(--fs-sm);font-weight:600">${status && PROJECT_STATUS[status] ? tx(PROJECT_STATUS[status]) : ""}</p>`}
        <a class="link-arrow" href="${BASE}project.html?id=${project.id}">${t("cta.viewProject")} ${iconSvg("arrow", "icon icon--dir")}</a>
      </div>
    </div>
  </article>`;
}

/** Each unit card shows a photograph from its own project, varied by unit. */
function unitImage(unit) {
  const { PROJECTS } = window.DATA;
  const project = PROJECTS.find((p) => p.id === unit.projectId);
  const pool = project.gallery && project.gallery.length ? project.gallery : [project.image];
  return pool[(Number(unit.code) || 0) % pool.length];
}

function unitCard(unit) {
  const { PROJECTS, UNIT_TYPES, ORIENTATIONS } = window.DATA;
  const project = PROJECTS.find((p) => p.id === unit.projectId);
  const sold = unit.status !== "available" || !unit.price;
  return `
  <article class="card reveal">
    <a class="card__media" href="${BASE}project.html?id=${project.id}#unit-${unit.id}" aria-label="${esc(tx(project.name))} ${unit.code}">
      ${picture(unitImage(unit), `${tx(project.name)} — ${tx(UNIT_TYPES[unit.type])}`, { sizes: "(max-width: 700px) 92vw, (max-width: 1100px) 45vw, 380px" })}
      <span class="badge badge--${unit.status} badge--on-media">${t(`status.${unit.status}`)}</span>
    </a>
    <div class="card__body">
      <p class="card__meta">${tx(project.name)} · ${tx(window.DATA.DISTRICTS[unit.district])}</p>
      <h3 class="card__title">${t("unit.unit")} ${unit.code} — ${tx(UNIT_TYPES[unit.type])}</h3>
      <div class="unit-card__grid">
        <div><span>${t("unit.beds")}</span><strong>${unit.beds}</strong></div>
        <div><span>${t("unit.baths")}</span><strong>${unit.baths}</strong></div>
        <div><span>${t("unit.area")}</span><strong class="num">${window.I18N.area(unit.area)}</strong></div>
        <div><span>${t("unit.floor")}</span><strong>${tx(unit.floorLabel)}</strong></div>
      </div>
      <p class="card__meta">${iconSvg("area")} ${unit.outdoor
        ? `${t("unit.outdoor")}: <span class="num">${window.I18N.area(unit.outdoor)}</span> · `
        : ""}${tx(ORIENTATIONS[unit.orientation])}</p>
      <div class="card__foot">
        ${unit.price
          ? `<p class="card__price num">${window.I18N.price(unit.price)}<small>${window.I18N.num(Math.round(unit.price / unit.area))} ${t("unit.jod")} / ${t("unit.sqm")}</small></p>`
          : `<p class="card__price" style="font-size:var(--fs-sm)">${t(`status.${unit.status}`)}</p>`}
        <button class="btn btn--sm ${sold ? "btn--ghost" : "btn--brass"}" data-enquire="${unit.id}" ${sold ? "disabled" : ""}>
          ${sold ? t(`status.${unit.status}`) : t("cta.enquire")}
        </button>
      </div>
    </div>
  </article>`;
}

/** Fill and open the shared enquiry dialog for one unit. */
function initEnquiry() {
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-enquire]");
    if (!btn || btn.disabled) return;
    const { UNITS, PROJECTS, UNIT_TYPES } = window.DATA;
    const unit = UNITS.find((u) => u.id === btn.dataset.enquire);
    if (!unit) return;
    const project = PROJECTS.find((p) => p.id === unit.projectId);
    const title = `${tx(project.name)} — ${t("unit.unit")} ${unit.code}`;
    const summary = [tx(UNIT_TYPES[unit.type]), `${unit.beds} ${t("unit.beds")}`, window.I18N.area(unit.area),
      unit.price ? window.I18N.price(unit.price) : t(`status.${unit.status}`)].join(" · ");
    $("#enquiry-unit-title").textContent = title;
    $("#enquiry-unit-summary").textContent = summary;
    const form = $("#enquiry-form");
    form.dataset.subject = `${title} (${summary})`;
    form.querySelector('[name="unit"]').value = `${title} — ${summary}`;
    openModal("enquiry-modal");
  });
}

/* ------------------------------------------------------------------- boot */

function boot() {
  window.I18N.apply(window.I18N.detect(), { persist: false });
  hydrateIcons();
  initHeader();
  initCurrentNav();
  initLangSwitch();
  initModals();
  initLightbox();
  initForms();
  initEnquiry();
  initFooter();
  wireContactLinks();
  initReveals();
  document.addEventListener("langchange", () => { initFooter(); wireContactLinks(); });
}

// The scripts sit at the end of <body>, so this normally runs straight away —
// which matters, because the page modules render as soon as they are parsed.
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();

window.APP = {
  $, $$, esc, picture, iconSvg, hydrateIcons, projectCard, unitCard,
  openModal, closeModal, openLightbox, initReveals, waLink, BASE, t, tx, dropSection,
};
