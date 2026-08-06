/* =============================================================================
   Project detail page. Everything is driven by ?id=<project id>, including the
   availability matrix, the unit list, the floor plans and the map.
   ========================================================================== */

(function () {
  const { $, $$, picture, iconSvg, unitCard, initReveals, openLightbox, esc, t, tx, BASE } = window.APP;
  const root = $("#project-page");
  if (!root) return;

  const { PROJECTS, UNITS, DISTRICTS, AMENITIES, PAYMENT_PLANS, PROJECT_STATUS, UNIT_TYPES, PLAN_LEGEND } = window.DATA;

  const id = new URLSearchParams(location.search).get("id");
  const project = id ? PROJECTS.find((p) => p.id === id) : PROJECTS[0];
  // An id that no longer exists (a retired project, a stale link) must not
  // quietly render a different building under the requested name.
  if (!project) {
    location.replace(`${BASE}projects.html${window.I18N.lang === "en" ? "?lang=en" : ""}`);
    return;
  }
  const units = UNITS.filter((u) => u.projectId === project.id);
  const available = units.filter((u) => u.status === "available");

  /* --------------------------------------------------------------- header */

  function renderHero() {
    const status = available.length ? project.status : "soldout";
    document.title = `${tx(project.name)} — ${tx(window.DATA.COMPANY.short)}`;
    $("#p-hero-media").innerHTML = picture(`project-${project.image}`, tx(project.name), { sizes: "100vw", eager: true });
    $("#p-crumb").textContent = tx(project.name);
    $("#p-badge").className = `badge badge--${status}`;
    $("#p-badge").textContent = tx(PROJECT_STATUS[status]);
    $("#p-title").textContent = tx(project.name);
    $("#p-tagline").textContent = tx(project.tagline);
    $("#p-meta").innerHTML = [
      `${iconSvg("pin")} ${tx(project.address)}, ${tx(DISTRICTS[project.district])}`,
      `${iconSvg("calendar")} ${tx(project.delivery)}`,
      `${iconSvg("building")} ${units.length} ${t("project.units")} · ${project.floors} ${t("project.floors")}`,
    ].map((s) => `<li>${s}</li>`).join("");
  }

  /* ---------------------------------------------------------------- about */

  function renderAbout() {
    $("#p-description").textContent = tx(project.description);
    $("#p-highlights").innerHTML = project.highlights
      .map((h) => `<li>${iconSvg("check")}<span>${tx(h)}</span></li>`).join("");
    $("#p-amenities").innerHTML = project.amenities
      .map((a) => `<li class="pill">${iconSvg(a in AMENITIES ? a : "check")} ${tx(AMENITIES[a])}</li>`).join("");

    const prices = units.map((u) => u.price);
    const areas = units.map((u) => u.area);
    $("#p-facts").innerHTML = [
      [t("unit.priceFrom"), window.I18N.price(Math.min(...prices))],
      [t("unit.area"), `${window.I18N.num(Math.min(...areas))} – ${window.I18N.area(Math.max(...areas))}`],
      [t("project.available"), `${available.length} ${t("project.units")}`],
      [t("project.delivery"), tx(project.delivery)],
    ].map(([k, v]) => `<div><span>${k}</span><strong class="num">${v}</strong></div>`).join("");
  }

  /* --------------------------------------------------- availability matrix */

  function renderMatrix() {
    const lines = project.lines.map((l) => l.code);
    const floors = [...new Set(units.map((u) => u.floor))].sort((a, b) => b - a);
    const head = `<tr><th scope="col">${t("unit.floor")}</th>${lines.map((c) => `<th scope="col">${t("grid.line")} ${c}</th>`).join("")}</tr>`;
    const rows = floors.map((f) => {
      const cells = lines.map((code) => {
        const unit = units.find((u) => u.floor === f && u.line === code);
        if (!unit) return "<td></td>";
        const sold = unit.status === "sold";
        return `<td><button class="cell cell--${unit.status}" ${sold ? "disabled" : ""}
          data-enquire="${unit.id}" title="${esc(`${tx(UNIT_TYPES[unit.type])} · ${window.I18N.area(unit.area)}`)}">
          <strong>${unit.code}</strong>
          <span class="num">${sold ? t("status.sold") : window.I18N.price(unit.price)}</span>
        </button></td>`;
      }).join("");
      const label = window.DATA.floorMeta(project, f);
      return `<tr><th scope="row">${tx(label)}</th>${cells}</tr>`;
    }).join("");
    $("#p-matrix").innerHTML = `<thead>${head}</thead><tbody>${rows}</tbody>`;
    $("#p-legend").innerHTML = ["available", "reserved", "sold"].map((s) =>
      `<li><i class="cell--${s}"></i> ${t(`status.${s}`)}</li>`).join("");
  }

  /* ---------------------------------------------------------------- units */

  function renderUnits() {
    const list = [...units].sort((a, b) => (a.status === "sold") - (b.status === "sold") || a.price - b.price);
    $("#p-units").innerHTML = list.slice(0, 9).map(unitCard).join("");
    const more = $("#p-units-more");
    if (list.length > 9) {
      more.hidden = false;
      more.href = `${BASE}units.html?project=${project.id}&status=`;
    } else { more.hidden = true; }
  }

  /* ----------------------------------------------------------- floorplans */

  function renderPlans() {
    const plans = [...new Set(project.lines.map((l) => l.plan))];
    $("#p-plan-tabs").innerHTML = plans.map((plan, i) => {
      const line = project.lines.find((l) => l.plan === plan);
      return `<button class="tab" role="tab" aria-selected="${i === 0}" data-plan="${plan}">
        ${line.beds} ${t("unit.beds")} · ${window.I18N.area(line.area)}</button>`;
    }).join("");
    showPlan(plans[0]);
  }

  function showPlan(plan) {
    const line = project.lines.find((l) => l.plan === plan);
    $("#p-plan-img").innerHTML = `<img src="${BASE}assets/img/${plan}.svg" alt="${esc(`${tx(project.name)} — ${line.beds} ${t("unit.beds")}`)}" loading="lazy" width="1200" height="900">`;
    $("#p-plan-legend").innerHTML = Object.entries(PLAN_LEGEND)
      .filter(([num]) => document.querySelector("#p-plan-img") && planUses(plan, Number(num)))
      .map(([num, label]) => `<li><i>${num}</i> ${tx(label)}</li>`).join("");
    $("#p-plan-meta").innerHTML = `
      <li>${iconSvg("bed")} ${line.beds} ${t("unit.beds")}</li>
      <li>${iconSvg("bath")} ${line.baths} ${t("unit.baths")}</li>
      <li>${iconSvg("area")} <span class="num">${window.I18N.area(line.area)}</span></li>
      <li>${iconSvg("floor")} ${t("grid.line")} ${line.code}</li>`;
    $("#p-plan-dl").href = `${BASE}assets/img/${plan}.svg`;
    $("#p-plan-dl").setAttribute("download", `${project.id}-${plan}.svg`);
  }

  /** Which legend numbers actually appear on a given plan drawing. */
  const PLAN_ROOMS = {
    "plan-2br": [1, 2, 3, 4, 5, 6, 7],
    "plan-3br": [1, 2, 3, 4, 5, 6, 8, 9],
    "plan-4br": [1, 2, 3, 4, 5, 6, 7, 9, 10],
    "plan-duplex": [1, 2, 4, 5, 6, 11, 12],
  };
  const planUses = (plan, num) => (PLAN_ROOMS[plan] || []).includes(num);

  /* --------------------------------------------------------- plans + map */

  function renderPayment() {
    $("#p-payment").innerHTML = project.plans.map((pid) => {
      const plan = PAYMENT_PLANS.find((p) => p.id === pid);
      return `<article class="card" style="padding:clamp(1.25rem,2.4vw,1.75rem);gap:.85rem">
        <span class="badge badge--plain">${tx(plan.badge)}</span>
        <h3 class="card__title" style="font-size:1.15rem">${tx(plan.name)}</h3>
        <p class="card__text">${tx(plan.summary)}</p>
        <ul class="tick-list" style="margin-block-start:.5rem">
          ${plan.steps.map((s) => `<li>${iconSvg("check")}<span><strong class="num">${s.pct}%</strong> — ${tx(s.label)}</span></li>`).join("")}
        </ul>
      </article>`;
    }).join("");
  }

  function renderMap() {
    const q = encodeURIComponent(project.mapQuery);
    $("#p-map").innerHTML = `<iframe title="${esc(tx(project.name))} — ${t("project.location")}"
      src="https://www.google.com/maps?q=${q}&output=embed" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>`;
    $("#p-map-link").href = `https://www.google.com/maps/search/?api=1&query=${q}`;
  }

  function renderGallery() {
    const items = project.gallery.map((name, i) => ({
      name,
      caption: `${tx(project.name)} — ${window.I18N.lang === "ar" ? "معالجة معمارية" : "architectural study"} ${i + 1}`,
    }));
    $("#p-gallery").innerHTML = items.map((item, i) => `
      <button class="gallery-item" data-lb="${i}">
        ${picture(item.name, item.caption, { sizes: "(max-width: 700px) 92vw, 30vw" })}
        <figcaption>${esc(item.caption)}</figcaption>
      </button>`).join("");
    $("#p-gallery").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-lb]");
      if (btn) openLightbox(items, Number(btn.dataset.lb));
    });
  }

  function renderRelated() {
    const others = PROJECTS.filter((p) => p.id !== project.id).slice(0, 3);
    $("#p-related").innerHTML = others.map(window.APP.projectCard).join("");
  }

  /* ---------------------------------------------------------------- boot */

  function renderAll() {
    renderHero(); renderAbout(); renderMatrix(); renderUnits(); renderPlans();
    renderPayment(); renderMap(); renderGallery(); renderRelated();
    // Deep links from the units page: ?id=…#unit-<id>
    const hash = location.hash.slice(1);
    if (hash.startsWith("unit-")) {
      const btn = document.querySelector(`[data-enquire="${hash.replace("unit-", "")}"]`);
      btn?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    initReveals();
  }

  document.addEventListener("click", (e) => {
    const tab = e.target.closest("[data-plan]");
    if (!tab) return;
    $$("#p-plan-tabs .tab").forEach((b) => b.setAttribute("aria-selected", String(b === tab)));
    showPlan(tab.dataset.plan);
  });

  $$("[data-wa-project]").forEach((a) => {
    a.dataset.wa = window.I18N.lang === "ar"
      ? `مرحباً، أرغب بالاستفسار عن مشروع ${project.name.ar} في ${DISTRICTS[project.district].ar}.`
      : `Hello, I would like to ask about ${project.name.en} in ${DISTRICTS[project.district].en}.`;
  });

  document.addEventListener("langchange", renderAll);
  renderAll();
})();
