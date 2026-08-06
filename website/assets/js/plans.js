/* =============================================================================
   Payment plans page: the contractual plans, and an instalment calculator that
   can price any available unit in the inventory.
   ========================================================================== */

(function () {
  const { $, $$, iconSvg, initReveals, esc, t, tx } = window.APP;
  const calcRoot = $("#calculator");
  if (!calcRoot) return;

  const { PAYMENT_PLANS, UNITS, PROJECTS, UNIT_TYPES } = window.DATA;
  const I18N = window.I18N;

  const state = { price: 195000, downPct: 25, years: 15, rate: 6.5, mode: "company", unitId: "" };

  /* ------------------------------------------------------- contract plans */

  function renderPlanCards() {
    $("#plan-cards").innerHTML = PAYMENT_PLANS.map((plan) => `
      <article class="card reveal" style="padding:clamp(1.4rem,2.8vw,2.25rem);gap:1rem">
        <span class="badge badge--plain">${tx(plan.badge)}</span>
        <h3 class="card__title">${tx(plan.name)}</h3>
        <p class="card__text">${tx(plan.summary)}</p>
        <ul class="tick-list">
          ${plan.steps.map((s) => `<li>${iconSvg("check")}<span><strong class="num">${s.pct}%</strong> — ${tx(s.label)}</span></li>`).join("")}
        </ul>
        <ul class="tick-list" style="border-block-start:1px solid var(--line-soft);padding-block-start:1rem;color:var(--muted)">
          ${plan.notes.map((no) => `<li>${iconSvg("check")}<span>${tx(no)}</span></li>`).join("")}
        </ul>
        <p class="card__meta" style="margin-block-start:auto">${iconSvg("building")} ${tx(plan.availableFor)}</p>
      </article>`).join("");
  }

  /* ----------------------------------------------------------- calculator */

  function monthly() {
    const financed = state.price * (1 - state.downPct / 100);
    if (state.mode === "company") {
      // Company instalments carry no interest, so it is a straight division.
      const months = Math.round(state.years * 12);
      return { financed, months, payment: financed / months, total: financed, interest: 0 };
    }
    const months = Math.round(state.years * 12);
    const r = state.rate / 100 / 12;
    const payment = r === 0 ? financed / months : (financed * r) / (1 - Math.pow(1 + r, -months));
    return { financed, months, payment, total: payment * months, interest: payment * months - financed };
  }

  function renderUnitPicker() {
    const list = UNITS.filter((u) => u.status === "available").sort((a, b) => a.price - b.price);
    $("#c-unit").innerHTML = `<option value="">${t("calc.custom")}</option>` + list.map((u) => {
      const p = PROJECTS.find((x) => x.id === u.projectId);
      return `<option value="${u.id}" ${state.unitId === u.id ? "selected" : ""}>
        ${esc(`${tx(p.name)} · ${u.code} · ${u.beds} ${t("unit.beds")} · ${I18N.price(u.price)}`)}</option>`;
    }).join("");
  }

  function renderOut() {
    const { financed, months, payment, total, interest } = monthly();
    $("#c-monthly").textContent = I18N.price(payment);
    $("#c-rows").innerHTML = [
      [t("calc.downAmount"), I18N.price(state.price * (state.downPct / 100))],
      [t("calc.financed"), I18N.price(financed)],
      [t("calc.months"), I18N.num(months)],
      [t("calc.interest"), state.mode === "company" ? "—" : I18N.price(interest)],
      [t("calc.total"), I18N.price(total + state.price * (state.downPct / 100))],
    ].map(([k, v]) => `<div><dt>${k}</dt><dd class="num">${v}</dd></div>`).join("");
  }

  function syncInputs() {
    $("#c-price").value = state.price;
    $("#c-down").value = state.downPct;
    $("#c-down-out").textContent = `${state.downPct}%`;
    $("#c-years").value = state.years;
    $("#c-years-out").textContent = I18N.num(state.years);
    $("#c-rate").value = state.rate;
    $("#c-rate-out").textContent = `${state.rate}%`;
    $("#c-rate-field").hidden = state.mode === "company";
    $$('[name="c-mode"]').forEach((r) => { r.checked = r.value === state.mode; });
    // Company plans run to five years; bank financing goes far longer.
    const max = state.mode === "company" ? 5 : 25;
    const min = state.mode === "company" ? 1 : 5;
    $("#c-years").max = max; $("#c-years").min = min;
    if (state.years > max) state.years = max;
    if (state.years < min) state.years = min;
    $("#c-years").value = state.years;
    $("#c-years-out").textContent = I18N.num(state.years);
    renderOut();
  }

  calcRoot.addEventListener("input", (e) => {
    const el = e.target;
    if (el.id === "c-price") state.price = Math.max(20000, Number(el.value) || 0);
    else if (el.id === "c-down") state.downPct = Number(el.value);
    else if (el.id === "c-years") state.years = Number(el.value);
    else if (el.id === "c-rate") state.rate = Number(el.value);
    else if (el.name === "c-mode") state.mode = el.value;
    else if (el.id === "c-unit") {
      state.unitId = el.value;
      const unit = UNITS.find((u) => u.id === el.value);
      if (unit) { state.price = unit.price; $("#c-price").value = unit.price; }
    }
    syncInputs();
  });

  function renderAll() {
    renderPlanCards();
    renderUnitPicker();
    syncInputs();
    initReveals();
  }

  document.addEventListener("langchange", renderAll);
  renderAll();
})();
