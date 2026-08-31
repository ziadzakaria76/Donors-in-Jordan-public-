/* =============================================================================
   Available units — filtering, sorting, and URL state so a filtered view can
   be sent to a client as a link.
   ========================================================================== */

(function () {
  const { $, $$, unitCard, initReveals, tx, t } = window.APP;
  const grid = $("#unit-grid");
  if (!grid) return;

  const { UNITS, PROJECTS, DISTRICTS, UNIT_TYPES, ORIENTATIONS } = window.DATA;

  const FILTERS = ["project", "district", "beds", "type", "floor", "orientation", "minArea", "maxPrice", "status", "sort"];
  const state = Object.fromEntries(FILTERS.map((k) => [k, ""]));
  state.status = "available";
  state.sort = "priceAsc";

  /* ------------------------------------------------------------- controls */

  function option(value, label, selected) {
    return `<option value="${value}" ${selected ? "selected" : ""}>${label}</option>`;
  }

  function buildControls() {
    // render() removes the panel when there is no inventory, and langchange
    // calls this again afterwards — so there may be nothing left to populate.
    if (!$("#filters")) return;
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
    /* Aspect is a real buying criterion in Amman, not a detail: a north-facing
       flat is cooler through the summer and a south-facing one is bright in
       winter, and buyers ask for one or the other by name. The schedule has
       carried it from the start; it just was not filterable. */
    $("#f-orientation").innerHTML = option("", anyLabel, !state.orientation)
      + [...new Set(UNITS.map((u) => u.orientation))]
        .map((o) => option(o, tx(ORIENTATIONS[o]), state.orientation === o)).join("");
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

  /**
   * What each filter will accept from the query string.
   *
   * These values arrive from outside — a link a salesperson sent months ago, a
   * project id that has since been renamed, a hand-edited URL — and they used
   * to be trusted verbatim. `?project=nope` then threw on the chip label, which
   * left the page showing no units and no chips at all: nothing matched, and
   * nothing on screen said why or offered a way back.
   *
   * Two kinds of value are refused. One is a name that is not in a closed
   * vocabulary — a project, district, type, orientation, status or sort order
   * that does not exist. The other is a number that is not a number, which is
   * where `?maxPrice=abc` came from: it filtered nothing, correctly, while
   * announcing "≤ NaN دينار" in the chips.
   *
   * A well-formed value that simply matches nothing is not refused. `beds=99`
   * and `floor=99` are real questions with the honest answer "none", and the
   * empty state says so.
   */
  const known = (obj) => (v) => Object.prototype.hasOwnProperty.call(obj, v);
  const numeric = (v) => v.trim() !== "" && Number.isFinite(Number(v));
  const ACCEPTS = {
    project: (v) => PROJECTS.some((p) => p.id === v),
    district: known(DISTRICTS),
    type: known(UNIT_TYPES),
    orientation: known(ORIENTATIONS),
    status: (v) => ["available", "reserved", "sold"].includes(v),
    sort: (v) => ["priceAsc", "priceDesc", "areaDesc", "floorAsc"].includes(v),
    beds: numeric,
    floor: numeric,
    minArea: numeric,
    maxPrice: numeric,
  };

  function readUrl() {
    const params = new URLSearchParams(location.search);
    FILTERS.forEach((k) => {
      if (!params.has(k)) return;
      const value = params.get(k);
      /* "" is every filter's neutral setting — ?status= deliberately means
         "any status", not a status called "". */
      if (value === "" || ACCEPTS[k](value)) state[k] = value;
    });
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
      if (state.orientation && u.orientation !== state.orientation) return false;
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
      orientation: () => tx(ORIENTATIONS[state.orientation]),
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
    // Filtering an empty inventory is a control panel with nothing to control.
    if (!UNITS.length) {
      $("#filters")?.remove();
      grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
          <h3>${t("empty.unitsTitle")}</h3>
          <p>${t("empty.unitsBody")}</p>
          <p style="margin-block-start:1.5rem"><a class="btn btn--brass" href="contact.html">${t("cta.contactUs")}</a></p>
        </div>`;
      return;
    }
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
    /* compare.js hangs its toggles off the cards, and the grid is rebuilt from
       scratch on every filter change. It listens for this rather than being
       called directly, so units.html works with the script and without it. */
    document.dispatchEvent(new CustomEvent("unitsrendered"));
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
