/* =============================================================================
   Side-by-side comparison of up to three units.

   Buyers here are choosing between apartments in the same two buildings that
   differ by a floor, an aspect and ten square metres. The schedule holds all of
   that, but reading it means scrolling between cards and holding four numbers
   in your head — and the number that actually decides it, price per square
   metre, is on the card in small print and nowhere aggregated.

   So this exists to put three units in one table with the differences marked.

   It is a separate file, wired to the grid through the `unitsrendered` event
   rather than into unitCard, because comparison belongs to the units page and
   the card is rendered on four. A card on a page without this script keeps
   working exactly as it did.
   ========================================================================== */

(function () {
  const { $, $$, esc, t, tx } = window.APP;
  const grid = $("#unit-grid");
  if (!grid) return;

  const { UNITS, PROJECTS, UNIT_TYPES, ORIENTATIONS } = window.DATA;
  const LIMIT = 3;

  /* Kept in the URL so a comparison can be sent to somebody, which is the whole
     point of building one — units.html already puts its filters there. */
  const PARAM = "compare";
  const picked = new Set(
    (new URLSearchParams(location.search).get(PARAM) || "")
      .split(",").filter((id) => UNITS.some((u) => u.id === id)).slice(0, LIMIT),
  );

  const unitOf = (id) => UNITS.find((u) => u.id === id);
  const projectOf = (u) => PROJECTS.find((p) => p.id === u.projectId);

  function writeUrl() {
    const params = new URLSearchParams(location.search);
    if (picked.size) params.set(PARAM, [...picked].join(","));
    else params.delete(PARAM);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }

  /* ------------------------------------------------------ the card control */

  /**
   * Add a compare toggle to every card that does not have one.
   *
   * Runs after each grid render. A sold unit gets no toggle: comparing what you
   * cannot buy against what you can is a table with a dead column in it.
   */
  function decorate() {
    for (const card of $$("#unit-grid [data-unit]")) {
      const unit = unitOf(card.dataset.unit);
      if (!unit || unit.status !== "available" || !unit.price) continue;
      if (card.querySelector("[data-compare]")) { sync(card); continue; }

      /* On the card, NOT inside .card__media — on a unit card that element is
         the <a> wrapping the photograph, and a <button> inside an <a> is both
         invalid and unusable: the click navigates to the project page instead
         of toggling. */
      const button = document.createElement("button");
      button.type = "button";
      button.className = "compare-toggle";
      button.dataset.compare = unit.id;
      card.append(button);
      sync(card);
    }
  }

  function sync(card) {
    const button = card.querySelector("[data-compare]");
    if (!button) return;
    const on = picked.has(button.dataset.compare);
    button.classList.toggle("is-on", on);
    button.setAttribute("aria-pressed", String(on));
    button.setAttribute("aria-label", t(on ? "compare.remove" : "compare.add"));
    button.innerHTML = on
      ? `<span class="compare-toggle__tick" aria-hidden="true">✓</span><span>${esc(t("compare.added"))}</span>`
      : `<span class="compare-toggle__tick" aria-hidden="true">+</span><span>${esc(t("compare.add"))}</span>`;
    card.classList.toggle("is-comparing", on);
  }

  /* ------------------------------------------------------------- the tray */

  let tray = null;

  function renderTray() {
    if (!picked.size) {
      tray?.remove();
      tray = null;
      document.body.classList.remove("has-compare-tray");
      document.documentElement.style.removeProperty("--compare-tray-h");
      return;
    }

    if (!tray) {
      tray = document.createElement("div");
      tray.className = "compare-tray";
      tray.setAttribute("role", "region");
      document.body.append(tray);
    }
    tray.setAttribute("aria-label", t("compare.tray"));

    const chips = [...picked].map((id) => {
      const u = unitOf(id);
      return `<button class="chip" data-compare="${esc(id)}">${esc(tx(projectOf(u).name))} ${esc(u.code)}
        <span class="chip__x" aria-hidden="true">✕</span>
        <span class="sr-only">${esc(t("compare.remove"))}</span></button>`;
    }).join("");

    tray.innerHTML = `
      <div class="wrap compare-tray__inner">
        <div class="chip-row">${chips}</div>
        <div class="compare-tray__actions">
          <button class="btn btn--ghost btn--sm" type="button" data-compare-clear>${esc(t("compare.clear"))}</button>
          <button class="btn btn--brass btn--sm" type="button" data-compare-open ${picked.size < 2 ? "disabled" : ""}>
            ${esc(window.I18N.fill("compare.open", { n: picked.size }))}
          </button>
        </div>
      </div>`;

    /* Tell the page how much room the tray needs. It wraps to two rows on a
       phone, so this is measured rather than assumed — and without it the tray
       covers the WhatsApp button and the last band of the footer. */
    requestAnimationFrame(() => {
      if (!tray) return;
      document.documentElement.style.setProperty("--compare-tray-h", `${Math.ceil(tray.offsetHeight)}px`);
      document.body.classList.add("has-compare-tray");
    });
  }

  /* -------------------------------------------------------------- the table

     The comparison is a table, not three cards side by side, because the
     question is "how do these differ" and a table is the shape that answers it.
     On a phone it scrolls sideways rather than stacking: stacked, the rows stop
     lining up and it becomes three cards again. */

  function openTable() {
    const units = [...picked].map(unitOf);
    if (units.length < 2) return;

    const perSqm = (u) => Math.round(u.price / u.area);
    const best = {
      price: Math.min(...units.map((u) => u.price)),
      area: Math.max(...units.map((u) => u.area + (u.outdoor || 0))),
      perSqm: Math.min(...units.map(perSqm)),
    };

    /* Mark the winner of each row only when there is one — three units at the
       same price have no cheapest, and badging all three would say nothing. */
    const sole = (values, target) => values.filter((v) => v === target).length === 1;
    const win = (label) => `<span class="compare-win">${esc(t(label))}</span>`;

    const rows = [
      [t("compare.project"), units.map((u) => esc(`${tx(projectOf(u).name)} · ${t("unit.unit")} ${u.code}`))],
      [t("unit.price"), units.map((u) =>
        `<strong class="num">${window.I18N.price(u.price)}</strong>${
          u.price === best.price && sole(units.map((x) => x.price), best.price) ? win("compare.cheapest") : ""}`)],
      [t("compare.perSqm"), units.map((u) =>
        `<span class="num">${window.I18N.num(perSqm(u))} ${t("unit.jod")}</span>${
          perSqm(u) === best.perSqm && sole(units.map(perSqm), best.perSqm) ? win("compare.bestValue") : ""}`)],
      [t("unit.area"), units.map((u) => `<span class="num">${window.I18N.area(u.area)}</span>`)],
      [t("unit.outdoor"), units.map((u) => u.outdoor ? `<span class="num">${window.I18N.area(u.outdoor)}</span>` : "—")],
      [t("compare.total"), units.map((u) => {
        const total = u.area + (u.outdoor || 0);
        return `<span class="num">${window.I18N.area(total)}</span>${
          total === best.area && sole(units.map((x) => x.area + (x.outdoor || 0)), best.area) ? win("compare.largest") : ""}`;
      })],
      [t("unit.beds"), units.map((u) => u.beds)],
      [t("unit.baths"), units.map((u) => u.baths)],
      [t("unit.floor"), units.map((u) => esc(tx(u.floorLabel)))],
      [t("compare.aspect"), units.map((u) => esc(tx(ORIENTATIONS[u.orientation])))],
      [t("filter.type"), units.map((u) => esc(tx(UNIT_TYPES[u.type])))],
    ];

    /* A row where every unit says the same thing is a row that is not helping
       you choose. Identity, price and area always stay — they are the anchors
       you read the rest against. */
    const KEEP = new Set([t("compare.project"), t("unit.price"), t("unit.area")]);
    const useful = rows.filter(([label, cells]) =>
      KEEP.has(label) || new Set(cells.map(String)).size > 1);

    $("#compare-table").innerHTML = `
      <thead><tr><th></th>${units.map((u) =>
        `<th scope="col">${esc(tx(projectOf(u).name))}<br>${esc(t("unit.unit"))} ${esc(u.code)}</th>`).join("")}</tr></thead>
      <tbody>${useful.map(([label, cells]) =>
        `<tr><th scope="row">${esc(label)}</th>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody>
      <tfoot><tr><td></td>${units.map((u) =>
        `<td><button class="btn btn--sm btn--brass" data-enquire="${esc(u.id)}">${esc(t("cta.enquire"))}</button></td>`).join("")}</tr></tfoot>`;
    window.APP.openModal("compare-modal");
  }

  /* ------------------------------------------------------------- plumbing */

  function refresh() {
    for (const card of $$("#unit-grid [data-unit]")) sync(card);
    renderTray();
    writeUrl();
  }

  document.addEventListener("click", (e) => {
    const toggle = e.target.closest("[data-compare]");
    if (toggle) {
      e.preventDefault();
      const id = toggle.dataset.compare;
      if (picked.has(id)) picked.delete(id);
      else if (picked.size >= LIMIT) { alert(t("compare.full")); return; }
      else picked.add(id);
      refresh();
      return;
    }
    if (e.target.closest("[data-compare-clear]")) { picked.clear(); refresh(); return; }
    if (e.target.closest("[data-compare-open]")) openTable();
  });

  /* The grid is rebuilt on every filter change, so the toggles go with it. */
  document.addEventListener("unitsrendered", () => { decorate(); renderTray(); });
  document.addEventListener("langchange", () => { decorate(); renderTray(); });

  decorate();
  renderTray();
})();
