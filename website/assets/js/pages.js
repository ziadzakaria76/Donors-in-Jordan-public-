/* =============================================================================
   Small per-page renderers: the home page modules, the gallery grid, and the
   project index. Each block exits quietly if its container is not on the page.
   ========================================================================== */

(function () {
  const { $, $$, picture, iconSvg, projectCard, unitCard, initReveals, openLightbox, esc, t, tx, BASE } = window.APP;
  const { COMPANY, PROJECTS, UNITS, DISTRICTS, TESTIMONIALS, PROCESS, UNIT_TYPES } = window.DATA;
  const I18N = window.I18N;

  /* ------------------------------------------------------------ home page */

  function homeStats() {
    const box = $("#home-stats");
    if (!box) return;
    // No figures, no band — a section heading over nothing reads as broken.
    if (!COMPANY.stats.length) { box.closest("section")?.remove(); return; }
    box.innerHTML = COMPANY.stats.map((s) => `
      <div class="stat reveal">
        <p class="stat__value num">${s.value}</p>
        <p class="stat__label">${tx(s.label)}</p>
      </div>`).join("");
  }

  function featuredProjects() {
    const box = $("#home-projects");
    if (!box) return;
    // Lead with what is actually sellable: most available units first.
    const ranked = [...PROJECTS].sort((a, b) =>
      UNITS.filter((u) => u.projectId === b.id && u.status === "available").length -
      UNITS.filter((u) => u.projectId === a.id && u.status === "available").length);
    box.innerHTML = ranked.slice(0, 3).map(projectCard).join("");
  }

  function featuredUnits() {
    const box = $("#home-units");
    if (!box) return;
    const picks = UNITS.filter((u) => u.status === "available")
      .sort((a, b) => b.area / b.price - a.area / a.price)  // best area per dinar
      .slice(0, 3);
    box.innerHTML = picks.map(unitCard).join("");
  }

  function testimonials() {
    const box = $("#home-quotes");
    if (!box) return;
    if (!TESTIMONIALS.length) { box.closest("section")?.remove(); return; }
    box.innerHTML = TESTIMONIALS.map((q) => {
      const name = tx(q.name);
      const initials = name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("");
      return `<figure class="quote reveal">
        <blockquote class="quote__text">${tx(q.quote)}</blockquote>
        <figcaption class="quote__who">
          <span class="avatar" aria-hidden="true">${esc(initials)}</span>
          <span><span class="quote__name">${esc(name)}</span><br><span class="quote__role">${tx(q.role)}</span></span>
        </figcaption>
      </figure>`;
    }).join("");
  }

  function process() {
    const box = $("#home-process");
    if (!box) return;
    box.innerHTML = PROCESS.map((s) => `
      <div class="step reveal">
        <p class="step__num">${s.step}</p>
        <h3 class="step__title">${tx(s.title)}</h3>
        <p class="step__body">${tx(s.body)}</p>
      </div>`).join("");
  }

  /** Hero quick-search: composes a link into the units page. */
  function quickSearch() {
    const form = $("#quick-search");
    if (!form) return;
    const anyLabel = () => t("filter.any");
    const fill = () => {
      $("#q-district").innerHTML = `<option value="">${anyLabel()}</option>` +
        Object.entries(DISTRICTS).map(([id, d]) => `<option value="${id}">${tx(d)}</option>`).join("");
      $("#q-beds").innerHTML = `<option value="">${anyLabel()}</option>` +
        [2, 3, 4].map((b) => `<option value="${b}">${b} ${t("filter.plus")}</option>`).join("");
      $("#q-budget").innerHTML = `<option value="">${anyLabel()}</option>` +
        [150000, 200000, 250000, 350000, 500000].map((v) => `<option value="${v}">≤ ${I18N.price(v)}</option>`).join("");
    };
    fill();
    document.addEventListener("langchange", fill);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const params = new URLSearchParams({ status: "available" });
      if ($("#q-district").value) params.set("district", $("#q-district").value);
      if ($("#q-beds").value) params.set("beds", $("#q-beds").value);
      if ($("#q-budget").value) params.set("maxPrice", $("#q-budget").value);
      if (I18N.lang !== "ar") params.set("lang", I18N.lang);
      location.href = `${BASE}units.html?${params}`;
    });
  }

  /* -------------------------------------------------------- project index */

  function projectIndex() {
    const box = $("#projects-grid");
    if (!box) return;
    const render = (filter = "") => {
      const list = filter ? PROJECTS.filter((p) => p.status === filter) : PROJECTS;
      box.innerHTML = list.map(projectCard).join("");
      initReveals();
    };
    render();
    $$("#project-filters .tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$("#project-filters .tab").forEach((b) => b.setAttribute("aria-selected", String(b === tab)));
        render(tab.dataset.status || "");
      });
    });
    document.addEventListener("langchange", () => {
      const active = $("#project-filters .tab[aria-selected='true']");
      render(active?.dataset.status || "");
    });
  }

  /* ---------------------------------------------------------------- gallery */

  function gallery() {
    const box = $("#gallery-grid");
    if (!box) return;

    const CAPTIONS = {
      "project-residence76": { ar: "ريزيدنس ٧٦ — الواجهة الغربية عند الغروب", en: "Residence 76 — west elevation at dusk" },
      "project-crescent": { ar: "ذا كريسنت — الكتلة الرئيسية من جهة الوادي", en: "The Crescent — main massing from the valley side" },
      "project-rabieh": { ar: "حدائق الرابية — المسبح والتراس المشترك", en: "Rabieh Gardens — pool and shared terrace" },
      "gallery-facade-1": { ar: "دراسة الواجهة — إيقاع الشرفات والحجر", en: "Facade study — balcony rhythm and stone" },
      "gallery-facade-2": { ar: "دراسة الواجهة — الزجاج والظل في ضوء العصر", en: "Facade study — glass and shadow in afternoon light" },
      "gallery-facade-3": { ar: "دراسة الواجهة — الوحدات المتكررة", en: "Facade study — the repeating module" },
      "gallery-interior-1": { ar: "المعيشة — الإطلالة من الطابق السابع", en: "Living room — the view from the seventh floor" },
      "gallery-interior-2": { ar: "المعيشة — تشطيبات البلوط الطبيعي", en: "Living room — natural oak finishes" },
      "gallery-interior-3": { ar: "المعيشة — الضوء الجنوبي بعد الظهر", en: "Living room — southern light in the afternoon" },
      "gallery-courtyard-1": { ar: "المرافق المشتركة — المسبح عند المغيب", en: "Shared amenities — the pool at sunset" },
      "gallery-courtyard-2": { ar: "المرافق المشتركة — الفناء صباحاً", en: "Shared amenities — the courtyard in the morning" },
      "gallery-skyline-1": { ar: "السياق العمراني — غرب عمّان", en: "Urban context — West Amman" },
      "gallery-skyline-2": { ar: "السياق العمراني — المدينة ليلاً", en: "Urban context — the city at night" },
    };

    const build = (filter = "") => {
      const names = Object.keys(CAPTIONS).filter((n) => !filter || n.includes(filter));
      const items = names.map((name) => ({ name, caption: tx(CAPTIONS[name]) }));
      box.innerHTML = items.map((item, i) => `
        <button class="gallery-item ${i % 5 === 0 ? "gallery-item--tall" : ""}" data-lb="${i}">
          ${picture(item.name, item.caption, { sizes: "(max-width: 700px) 92vw, (max-width: 1100px) 46vw, 30vw" })}
          <figcaption>${esc(item.caption)}</figcaption>
        </button>`).join("");
      box.onclick = (e) => {
        const btn = e.target.closest("[data-lb]");
        if (btn) openLightbox(items, Number(btn.dataset.lb));
      };
      initReveals();
    };

    build();
    $$("#gallery-filters .tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$("#gallery-filters .tab").forEach((b) => b.setAttribute("aria-selected", String(b === tab)));
        build(tab.dataset.filter || "");
      });
    });
    document.addEventListener("langchange", () => {
      const active = $("#gallery-filters .tab[aria-selected='true']");
      build(active?.dataset.filter || "");
    });
  }

  /* ------------------------------------------------------- contact page bits */

  function contactBits() {
    const box = $("#contact-map");
    // No address means no office map — never a map of somewhere else.
    if (box && !COMPANY.mapQuery) box.remove();
    else if (box) {
      const q = encodeURIComponent(COMPANY.mapQuery);
      box.innerHTML = `<iframe title="${esc(tx(COMPANY.name))}" src="https://www.google.com/maps?q=${q}&output=embed"
        loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>`;
    }
    const select = $("#contact-project");
    if (select) {
      const fill = () => {
        select.innerHTML = `<option value="">${t("filter.any")}</option>` +
          PROJECTS.map((p) => `<option value="${esc(tx(p.name))}">${esc(tx(p.name))}</option>`).join("");
        const pre = new URLSearchParams(location.search).get("project");
        if (pre) {
          const project = PROJECTS.find((p) => p.id === pre);
          if (project) select.value = tx(project.name);
        }
      };
      fill();
      document.addEventListener("langchange", fill);
    }
  }

  /* --------------------------------------------------------------- run all */

  function run() {
    homeStats(); featuredProjects(); featuredUnits(); testimonials(); process();
    projectIndex(); contactBits();
    initReveals();
  }

  quickSearch();
  gallery();
  run();
  document.addEventListener("langchange", run);
})();
