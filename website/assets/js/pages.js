/* =============================================================================
   Small per-page renderers: the home page modules, the gallery grid, and the
   project index. Each block exits quietly if its container is not on the page.
   ========================================================================== */

(function () {
  const { $, $$, picture, iconSvg, projectCard, unitCard, initReveals, openLightbox, esc, t, tx, BASE, dropSection } = window.APP;
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
    if (!PROJECTS.length) { box.closest("section")?.remove(); return; }
    // Lead with what is actually sellable: most available units first.
    const ranked = [...PROJECTS].sort((a, b) =>
      UNITS.filter((u) => u.projectId === b.id && u.status === "available").length -
      UNITS.filter((u) => u.projectId === a.id && u.status === "available").length);
    box.innerHTML = ranked.slice(0, 3).map(projectCard).join("");
  }

  function featuredUnits() {
    const box = $("#home-units");
    if (!box) return;
    if (!UNITS.length) { box.closest("section")?.remove(); return; }
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
    if (!UNITS.length) { form.remove(); return; }
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
      if (!PROJECTS.length) {
        $("#project-filters")?.remove();
        box.innerHTML = `<div class="empty" style="grid-column:1/-1">
            <h3>${t("empty.projectsTitle")}</h3>
            <p>${t("empty.projectsBody")}</p>
            <p style="margin-block-start:1.5rem"><a class="btn btn--brass" href="${BASE}contact.html">${t("cta.contactUs")}</a></p>
          </div>`;
        return;
      }
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

    const CAPTIONS = window.DATA.IMAGE_CAPTIONS;

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
    if (select && !PROJECTS.length) select.closest(".field")?.remove();
    else if (select) {
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
