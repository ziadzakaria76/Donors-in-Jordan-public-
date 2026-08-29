/* =============================================================================
   Project detail page. Everything is driven by ?id=<project id>, including the
   availability matrix, the unit list, the floor plans and the map.
   ========================================================================== */

(function () {
  const { $, $$, picture, iconSvg, unitCard, initReveals, openLightbox, esc, t, tx, BASE, dropSection } = window.APP;
  const root = $("#project-page");
  if (!root) return;

  const { PROJECTS, UNITS, DISTRICTS, AMENITIES, PROJECT_STATUS, UNIT_TYPES } = window.DATA;

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

  /* ----------------------------------------------------------- <head> tags */

  /* One HTML file serves all three projects, so the canonical, og:url and
     hreflang tags stamped into project.html name the file without an id. Left
     alone, all three projects would declare the same canonical — telling search
     engines they are duplicates of a page that renders nothing. Rewrite them to
     the URL actually being viewed, which is what sitemap.xml lists. */
  function setCanonical() {
    const domain = (window.DATA.COMPANY.domain || "").replace(/\/$/, "");
    const base = `${domain}/project.html?id=${project.id}`;
    const set = (sel, attr, value) => {
      const el = document.head.querySelector(sel);
      if (el) el.setAttribute(attr, value);
    };
    set('link[rel="canonical"]', "href", base);
    set('meta[property="og:url"]', "content", base);
    set('link[rel="alternate"][hreflang="ar"]', "href", base);
    set('link[rel="alternate"][hreflang="en"]', "href", `${base}&lang=en`);
  }

  /* --------------------------------------------------------------- header */

  function renderHero() {
    const status = units.length && !available.length && project.status === "selling" ? "soldout" : project.status;
    if (!status || !PROJECT_STATUS[status]) $("#p-badge")?.parentElement?.remove();
    document.title = `${tx(project.name)} — ${tx(window.DATA.COMPANY.short)}`;
    $("#p-hero-media").innerHTML = picture(project.image, tx(project.name), { sizes: "100vw", eager: true });
    $("#p-crumb").textContent = tx(project.name);
    if ($("#p-badge")) {
      $("#p-badge").className = `badge badge--${status}`;
      $("#p-badge").textContent = tx(PROJECT_STATUS[status]);
    }
    $("#p-title").textContent = tx(project.name);
    $("#p-tagline").textContent = tx(project.tagline);
    const meta = [];
    if (project.address) meta.push(`${iconSvg("pin")} ${tx(project.address)}`);
    else if (project.district) meta.push(`${iconSvg("pin")} ${tx(DISTRICTS[project.district])}`);
    if (project.delivery) meta.push(`${iconSvg("calendar")} ${tx(project.delivery)}`);
    if (units.length) meta.push(`${iconSvg("building")} ${units.length} ${t("project.units")}`);
    $("#p-meta").innerHTML = meta.map((s) => `<li>${s}</li>`).join("");
    // A project with no schedule has nothing to jump to.
    $$("[href='#availability']").forEach((a) => { if (!units.length) a.remove(); });
  }

  /* ---------------------------------------------------------------- about */

  function renderAbout() {
    if (!$("#p-description")) return;
    $("#p-description").textContent = tx(project.description);

    // Each of these removes itself when the project has nothing to put in it,
    // and this runs again on every language change — so nothing may be there.
    const fill = (sel, items, render) => {
      const box = $(sel);
      if (!box) return;
      if (!items?.length) { box.previousElementSibling?.remove(); box.remove(); return; }
      box.innerHTML = items.map(render).join("");
    };
    fill("#p-highlights", project.highlights, (h) => `<li>${iconSvg("check")}<span>${tx(h)}</span></li>`);
    fill("#p-amenities", project.amenities,
      (a) => `<li class="pill">${iconSvg(a in AMENITIES ? a : "check")} ${tx(AMENITIES[a])}</li>`);

    // The numbers card shares this section with the description, so an
    // inventory-less project loses the card, not the whole section.
    if (!units.length) { $("#p-facts")?.closest(".card")?.remove(); return; }
    const priced = available.filter((u) => u.price).map((u) => u.price);
    const areas = units.map((u) => u.area);
    const facts = [];
    if (priced.length) facts.push([t("unit.priceFrom"), window.I18N.price(Math.min(...priced))]);
    facts.push([t("unit.area"), `${window.I18N.num(Math.min(...areas))} – ${window.I18N.area(Math.max(...areas))}`]);
    facts.push([t("unit.unit"), String(units.length)]);
    facts.push([t("project.available"), `${available.length} ${t("project.units")}`]);
    if (project.delivery) facts.push([t("project.delivery"), tx(project.delivery)]);
    $("#p-facts").innerHTML = facts
      .map(([k, v]) => `<div><span>${k}</span><strong class="num">${v}</strong></div>`).join("");
  }

  /* --------------------------------------------------- availability matrix */

  function renderMatrix() {
    if (!$("#p-matrix")) return;
    if (!units.length) { $("#availability")?.remove(); return; }
    // Grouped by floor, top down, exactly as the schedule is published.
    const floors = [...new Set(units.map((u) => u.floor))].sort((a, b) => b - a);
    const rows = floors.map((f) => {
      const onFloor = units.filter((u) => u.floor === f);
      const cells = onFloor.map((unit) => {
        const sold = unit.status !== "available" || !unit.price;
        return `<td><button class="cell cell--${unit.status}" ${sold ? "disabled" : ""}
          data-enquire="${unit.id}" title="${esc(`${tx(UNIT_TYPES[unit.type])} · ${window.I18N.area(unit.area)}`)}">
          <strong>${t("unit.unit")} ${unit.code}</strong>
          <span class="num">${unit.price ? window.I18N.price(unit.price) : t(`status.${unit.status}`)}</span>
          <span class="num">${window.I18N.area(unit.area)}</span>
        </button></td>`;
      }).join("");
      return `<tr><th scope="row">${tx(onFloor[0].floorLabel)}</th>${cells}</tr>`;
    }).join("");
    $("#p-matrix").innerHTML = `<tbody>${rows}</tbody>`;
    $("#p-legend").innerHTML = ["available", "sold"].map((st) =>
      `<li><i class="cell--${st}"></i> ${t(`status.${st}`)}</li>`).join("");
  }

  /* ---------------------------------------------------------------- units */

  /** The unit named by a `#unit-…` hash, if it belongs to this project. */
  function hashUnitId() {
    const m = /^#unit-(.+)$/.exec(decodeURIComponent(location.hash));
    return m && units.some((u) => u.id === m[1]) ? m[1] : null;
  }

  function renderUnits() {
    if (!$("#p-units")) return;
    if (!units.length) { dropSection("#p-units"); return; }
    const list = [...units].sort((a, b) =>
      (a.status === "sold") - (b.status === "sold") || (a.price || 0) - (b.price || 0));
    /* Cards arrive here from units.html as `project.html?id=…#unit-…`, and the
       page shows only the first nine. A schedule of fourteen can therefore be
       asked for a unit that this list would cut, so the requested one is
       pulled to the front rather than dropped — otherwise the link lands on a
       page that does not contain what was clicked. */
    let shown = list.slice(0, 9);
    const wanted = hashUnitId();
    if (wanted && !shown.some((u) => u.id === wanted)) {
      shown = [list.find((u) => u.id === wanted), ...shown.slice(0, 8)];
    }
    $("#p-units").innerHTML = shown.map(unitCard).join("");
    const more = $("#p-units-more");
    if (list.length > 9) {
      more.hidden = false;
      more.href = `${BASE}units.html?project=${project.id}&status=`;
    } else { more.hidden = true; }
  }

  /**
   * Scroll to the unit the URL asked for.
   *
   * The browser resolves a fragment while parsing, which is long before these
   * cards exist, so a `#unit-…` link would otherwise land at the top of the
   * page with no sign of the unit that was clicked.
   */
  function focusHashUnit() {
    const id = hashUnitId();
    if (!id) return;
    const card = document.getElementById(`unit-${id}`);
    if (!card) return;
    card.classList.add("card--targeted");
    card.scrollIntoView({ block: "center", behavior: "auto" });
  }

  /* ----------------------------------------------------------- floorplans */

  function renderPlans() {
    if (!$("#p-plan-tabs")) return;
    // One tab per distinct plan drawing, labelled by the units that use it.
    const plans = [...new Set(units.map((u) => u.plan).filter(Boolean))];
    if (!plans.length) { dropSection("#p-plan-tabs"); return; }
    $("#p-plan-tabs").innerHTML = plans.map((plan, i) => {
      const on = units.filter((u) => u.plan === plan);
      return `<button class="tab" role="tab" aria-selected="${i === 0}" data-plan="${plan}">
        ${t("unit.unit")} ${on.map((u) => u.code).join("، ")} · ${window.I18N.area(on[0].area)}</button>`;
    }).join("");
    showPlan(plans[0]);
  }

  function showPlan(plan) {
    const on = units.filter((u) => u.plan === plan);
    const u = on[0];
    $("#p-plan-img").innerHTML = `<img src="${BASE}assets/img/${plan}-1280.webp"
      srcset="${BASE}assets/img/${plan}-800.webp 800w, ${BASE}assets/img/${plan}-1280.webp 1280w"
      sizes="(max-width: 860px) 92vw, 46vw"
      alt="${esc(`${tx(project.name)} — ${t("unit.unit")} ${on.map((x) => x.code).join("، ")}`)}"
      loading="lazy" style="border-radius:var(--radius)">`;
    $("#p-plan-legend").innerHTML = on.map((x) =>
      `<li><i>${x.code}</i> ${tx(x.floorLabel)} — ${tx(window.DATA.ORIENTATIONS[x.orientation])}</li>`).join("");
    $("#p-plan-meta").innerHTML = `
      <li>${iconSvg("bed")} ${u.beds} ${t("unit.beds")}</li>
      <li>${iconSvg("bath")} ${u.baths} ${t("unit.baths")}</li>
      <li>${iconSvg("area")} <span class="num">${window.I18N.area(u.area)}</span></li>
      ${u.outdoor ? `<li>${iconSvg("floor")} ${t("unit.outdoor")} <span class="num">${window.I18N.area(u.outdoor)}</span></li>` : ""}`;
    $("#p-plan-dl").href = `${BASE}assets/img/${plan}-1280.webp`;
    $("#p-plan-dl").setAttribute("download", `${project.id}-${plan}.webp`);
  }

  /* --------------------------------------------------------- plans + map */

  function renderNearby() {
    if (!$("#p-nearby")) return;
    if (!project.nearby?.length) { $("#p-nearby-section")?.remove(); return; }
    $("#p-nearby").innerHTML = project.nearby.map((g) => `
      <article class="card reveal" style="padding:clamp(1.25rem,2.4vw,1.75rem);gap:1rem">
        <h3 class="card__title" style="font-size:1.1rem">${tx(g.group)}</h3>
        <ul class="tick-list">
          ${g.items.map((it) => `<li>${iconSvg("clock")}<span>${tx(it.name)}
            <strong class="num" style="color:var(--brass)"> · ${it.mins} ${t("unit.mins")}</strong></span></li>`).join("")}
        </ul>
      </article>`).join("");
  }

  /**
   * The construction log, newest first.
   *
   * Dates are rendered in the reading language's own calendar formatting but
   * always with Western digits, as every other number on this site is — a
   * price in Western digits beside a date in Eastern-Arabic ones reads as two
   * different documents. The percentage is optional: "we poured the third
   * floor slab" is a fact, "41% complete" is an estimate, and a log is more
   * credible when it can state the first without inventing the second.
   */
  function renderProgress() {
    if (!$("#p-progress")) return;
    const log = (project.progress || []).filter((e) => e && e.date);
    if (!log.length) { $("#p-progress-section")?.remove(); return; }

    const entries = [...log].sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const locale = document.documentElement.lang === "ar" ? "ar-JO-u-nu-latn" : "en-GB";
    const fmt = (iso) => {
      const d = new Date(`${iso}T00:00:00`);
      return Number.isNaN(d.getTime()) ? iso
        : d.toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" });
    };

    $("#p-progress").innerHTML = entries.map((e) => `
      <li class="timeline__item reveal">
        <p class="timeline__date"><time class="num" datetime="${esc(e.date)}">${esc(fmt(e.date))}</time>${
          Number.isFinite(e.percent) ? ` <span class="timeline__pct num">${e.percent}%</span>` : ""}</p>
        ${e.title ? `<h3 class="timeline__title">${tx(e.title)}</h3>` : ""}
        ${e.body ? `<p>${tx(e.body)}</p>` : ""}
      </li>`).join("");
  }

  function renderMap() {
    if (!$("#p-map")) return;
    if (!project.mapQuery) { dropSection("#p-map"); return; }
    const q = encodeURIComponent(project.mapQuery);
    $("#p-map").innerHTML = `<iframe title="${esc(tx(project.name))} — ${t("project.location")}"
      src="https://www.google.com/maps?q=${q}&output=embed" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>`;
    $("#p-map-link").href = `https://www.google.com/maps/search/?api=1&query=${q}`;
  }

  function renderGallery() {
    if (!$("#p-gallery")) return;
    if (!project.gallery?.length) { dropSection("#p-gallery"); return; }
    /* Caption each image by what it is, falling back to numbering it. The
       fallback is not decorative: this project's gallery mixes 3D studies of
       the elevations with photographs of the entrance as built, and "image 5
       of 8" tells a buyer nothing about which one they are looking at. */
    const captions = window.DATA.IMAGE_CAPTIONS || {};
    const items = project.gallery.map((name, i) => ({
      name, caption: captions[name] ? tx(captions[name]) : `${tx(project.name)} — ${i + 1}`,
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
    if (!$("#p-related")) return;
    const others = PROJECTS.filter((p) => p.id !== project.id).slice(0, 3);
    $("#p-related").innerHTML = others.map(window.APP.projectCard).join("");
  }

  /* ---------------------------------------------------------------- boot */

  function renderAll() {
    setCanonical(); renderHero(); renderAbout(); renderMatrix(); renderUnits(); renderPlans();
    renderProgress(); renderNearby(); renderMap(); renderGallery(); renderRelated();
    initReveals();
    /* After initReveals, so the card is not mid-animation when we scroll it
       into view. Deep links from the units page: ?id=…#unit-<id> */
    focusHashUnit();
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
