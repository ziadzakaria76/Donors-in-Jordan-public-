/* =============================================================================
   Available units — filtering, sorting, and URL state so a filtered view can
   be sent to a client as a link.
   ========================================================================== */

(function () {
  const { $, $$, unitCard, initReveals, tx, t } = window.APP;
  const grid = $("#unit-grid");
  if (!grid) return;

  const { UNITS, PROJECTS, DISTRICTS, UNIT_TYPES } = window.DATA;

  const FILTERS = ["project", "district", "beds", "type", "floor", "minArea", "maxPrice", "status", "sort"];
  const state = Object.fromEntries(FILTERS.map((k) => [k, ""]));
  state.status = "available";
  state.sort = "priceAsc";

  /* ------------------------------------------------------------- controls */

  function option(value, label, selected) {
    return `<option value="${value}" ${selected ? "selected" : ""}>${label}</option>`;
  }

  function buildControls() {
    const anyLabel = t("filter.any");
    const floors = [...new Set(UNITS.map((u) => u.floor))].sort((a, b) => a - b);

    $("#f-project").innerHTML = option("", anyLabel, !state.project)
      + PROJECTS.map((p) => option(p.id, tx(p.name), state.project === p.id)).join("");
    $("#f-district").innerHTML = option("", anyLabel, !state.district)
      + Object.entries(DISTRICTS).map(([id, d]) => option(id, tx(d), state.district === id)).join("");
    $("#f-beds").innerHTML = option("", anyLabel, !state.beds)
      + [2, 3, 4].map((b) => option(b, `${b} ${t("filter.plus")}`, String(state.beds) === String(b))).join("");
    $("#f-type").innerHTML = option("", anyLabel, !state.type)
      + Object.entries(UNIT_TYPES).map(([id, d]) => option(id, tx(d), state.type === id)).join("");
    $("#f-floor").innerHTML = option("", anyLabel, !state.floor)
      + floors.map((f) => option(f, f === 0 ? t("filter.ground") : `${t("unit.floor")} ${f}`, String(state.floor) === String(f))).join("");
    $("#f-status").innerHTML = ["available", "reserved", "sold"]
      .map((s) => option(s, t(`status.${s}`), state.status === s)).join("")
      + option("", anyLabel, !state.status);
    $("#f-sort").innerHTML = [
      ["priceAsc", "sort.priceAsc"], ["priceDesc", "sort.priceDesc"],
      ["areaDesc", "sort.areaDesc"], ["floorAsc", "sort.floorAsc"],
    ].map(([v, k]) => option(v, t(k), state.sort === v)).join("");
    $("#f-minArea").value = state.minArea;
    $("#f-maxPrice").value = state.maxPrice;
  }

  /* ---------------------------------------------------------- URL syncing */

  function readUrl() {
    const params = new URLSearchParams(location.search);
    FILTERS.forEach((k) => { if (params.has(k)) state[k] = params.get(k); });
  }

  function writeUrl() {
    const params = new URLSearchParams(location.search);
    FILTERS.forEach((k) => (state[k] ? params.set(k, state[k]) : params.delete(k)));
    if (window.I18N.lang !== "ar") params.set("lang", window.I18N.lang);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }

  /* ------------------------------------------------------------ filtering */

  function apply() {
    let list = UNITS.filter((u) => {
      if (state.project && u.projectId !== state.project) return false;
      if (state.district && u.district !== state.district) return false;
      if (state.beds && u.beds < Number(state.beds)) return false;
      if (state.type && u.type !== state.type) return false;
      if (state.floor !== "" && String(u.floor) !== String(state.floor)) return false;
      if (state.minArea && u.area < Number(state.minArea)) return false;
      if (state.maxPrice && u.price > Number(state.maxPrice)) return false;
      if (state.status && u.status !== state.status) return false;
      return true;
    });

    const sorters = {
      priceAsc: (a, b) => a.price - b.price,
      priceDesc: (a, b) => b.price - a.price,
      areaDesc: (a, b) => b.area - a.area,
      floorAsc: (a, b) => a.floor - b.floor || a.price - b.price,
    };
    list.sort(sorters[state.sort] || sorters.priceAsc);
    return list;
  }

  /* -------------------------------------------------------------- chips */

  function chips() {
    const active = [];
    const label = {
      project: () => tx(PROJECTS.find((p) => p.id === state.project).name),
      district: () => tx(DISTRICTS[state.district]),
      beds: () => `${state.beds}+ ${t("unit.beds")}`,
      type: () => tx(UNIT_TYPES[state.type]),
      floor: () => (Number(state.floor) === 0 ? t("filter.ground") : `${t("unit.floor")} ${state.floor}`),
      minArea: () => `${state.minArea}+ ${t("unit.sqm")}`,
      maxPrice: () => `≤ ${window.I18N.price(Number(state.maxPrice))}`,
      status: () => t(`status.${state.status}`),
    };
    Object.keys(label).forEach((k) => {
      if (state[k] !== "" && state[k] != null) active.push({ k, text: label[k]() });
    });
    $("#chips").innerHTML = active.map((c) =>
      `<button class="chip" data-clear="${c.k}">${c.text}<span class="chip__x" aria-hidden="true">✕</span>
        <span class="sr-only">${t("cta.reset")}</span></button>`).join("");
  }

  /* ------------------------------------------------------------- render */

  function render() {
    const list = apply();
    $("#result-count").innerHTML = `<strong class="num">${list.length}</strong> ${t("results.count")}`;
    grid.innerHTML = list.length
      ? list.map(unitCard).join("")
      : `<div class="empty" style="grid-column:1/-1">
           <h3>${t("results.emptyTitle")}</h3>
           <p>${t("results.emptyBody")}</p>
           <p style="margin-block-start:1.25rem"><button class="btn btn--ghost" data-clear="all">${t("cta.reset")}</button></p>
         </div>`;
    chips();
    writeUrl();
    initReveals();
  }

  /* -------------------------------------------------------------- events */

  document.addEventListener("change", (e) => {
    const el = e.target.closest("#filters select, #filters input");
    if (!el) return;
    state[el.dataset.filter] = el.value;
    render();
  });

  document.addEventListener("click", (e) => {
    const clear = e.target.closest("[data-clear]");
    if (!clear) return;
    if (clear.dataset.clear === "all") FILTERS.forEach((k) => { state[k] = k === "sort" ? "priceAsc" : ""; });
    else state[clear.dataset.clear] = "";
    buildControls();
    render();
  });

  document.addEventListener("langchange", () => { buildControls(); render(); });

  readUrl();
  buildControls();
  render();
})();
