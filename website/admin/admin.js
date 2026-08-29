/**
 * The admin panel.
 *
 * No framework and no build step, for the same reason the site has none: this
 * is a small amount of behaviour over a small amount of data, and a toolchain
 * would be the only thing here that could rot. It loads in a browser the way
 * every other file in this repository does.
 *
 * It imports the validator and the vocabulary directly from ../tools/, which
 * is the point of that split. The rules that decide whether a unit is
 * publishable now run in four places — as you type here, in the Function
 * before it commits, in `npm run check` locally, and in CI — from one source.
 * A rule that exists in only three of them is the bug this arrangement exists
 * to make impossible.
 */

import { validate } from "../tools/validate-content.mjs";
import { DISTRICTS, AMENITIES, ORIENTATIONS, UNIT_TYPES, PROJECT_STATUS, UNIT_STATUS } from "../tools/render-data.mjs";

/* ================================================================= state === */

const state = {
  content: null,   // what you are editing
  saved: null,     // what is on the branch, for the dirty check
  commit: null,    // the commit it came from, for conflict detection
  tab: "dashboard",
  project: null,
  deploys: [],
};

const $ = (sel) => document.querySelector(sel);
const main = $("#main");
const clone = (v) => JSON.parse(JSON.stringify(v));
const dirty = () => JSON.stringify(state.content) !== JSON.stringify(state.saved);

/* ================================================================== dom === */

/** Build an element. Text is set with textContent, never innerHTML — the
    content being edited is text from a brochure, and a project name with an
    ampersand in it should render as an ampersand, not vanish. */
function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "value") node.value = v;
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

/** A text input bound to obj[key]. Every edit re-checks and re-renders the bar. */
function input(obj, key, opts = {}) {
  const node = el(opts.multiline ? "textarea" : "input", {
    type: opts.type || "text",
    dir: opts.dir,
    lang: opts.dir === "rtl" ? "ar" : null,
    class: opts.class,
    placeholder: opts.placeholder,
    value: obj[key] ?? "",
  });
  node.addEventListener("input", () => {
    const raw = node.value;
    if (opts.type === "number") {
      obj[key] = raw === "" ? (opts.blankIsNull ? null : 0) : Number(raw);
    } else {
      obj[key] = raw;
    }
    opts.onchange?.();
    touched();
  });
  return node;
}

/** A bilingual pair. Both languages always visible, because the rule that they
    are filled in together is only easy to follow if you can see both. */
function pair(obj, key, label, opts = {}) {
  obj[key] ??= { ar: "", en: "" };
  return el("div", { class: "field" },
    label ? el("span", { text: label }) : null,
    el("div", { class: "pair" },
      el("label", {}, el("span", { text: "العربية" }), input(obj[key], "ar", { ...opts, dir: "rtl" })),
      el("label", {}, el("span", { text: "English" }), input(obj[key], "en", { ...opts, dir: "ltr" })),
    ),
  );
}

function select(obj, key, options, opts = {}) {
  const node = el("select", { class: opts.class });
  if (opts.blank) node.append(el("option", { value: "", text: opts.blank }));
  for (const [value, label] of options) {
    node.append(el("option", { value, text: label, selected: obj[key] === value }));
  }
  node.value = obj[key] ?? "";
  node.addEventListener("change", () => {
    obj[key] = node.value || (opts.blank ? undefined : node.value);
    opts.onchange?.();
    touched();
  });
  return node;
}

const labelPairs = (map) => Object.entries(map).map(([k, v]) => [k, `${v.en} — ${v.ar}`]);

/* ================================================================== bar === */

function touched() {
  const on = dirty();
  $("#save").disabled = !on;
  $("#discard").hidden = !on;
  const badge = $("#dirty");
  badge.hidden = !on;
  if (on) badge.textContent = "unsaved changes";
  showProblems();
}

/** Live validation. The same list the Function will refuse the save with, so
    nobody discovers a missing price at the end of a long edit. */
function showProblems() {
  const errors = state.content ? validate(state.content) : [];
  const banner = $("#banner");
  if (!errors.length) {
    if (banner.dataset.kind === "errors") { banner.hidden = true; banner.dataset.kind = ""; }
    return;
  }
  banner.dataset.kind = "errors";
  banner.className = "banner banner--bad";
  banner.hidden = false;
  banner.replaceChildren(
    el("strong", { text: `${errors.length} thing${errors.length === 1 ? "" : "s"} would stop this going live:` }),
    el("ul", {}, errors.slice(0, 8).map((e) => el("li", { text: e }))),
    errors.length > 8 ? el("small", { text: `…and ${errors.length - 8} more.` }) : null,
  );
}

function say(text, kind = "") {
  const banner = $("#banner");
  banner.dataset.kind = "message";
  banner.className = `banner${kind ? ` banner--${kind}` : ""}`;
  banner.hidden = false;
  banner.replaceChildren(typeof text === "string" ? document.createTextNode(text) : text);
}

/* ================================================================== api === */

async function api(path, init) {
  const res = await fetch(path, { ...init, headers: { "content-type": "application/json", ...init?.headers } });
  let body = null;
  try { body = await res.json(); } catch { /* a proxy or Access page, not our JSON */ }
  if (!res.ok) {
    const err = new Error(body?.error || `${path} → ${res.status}`);
    err.status = res.status;
    err.errors = body?.errors;
    throw err;
  }
  return body;
}

/* =============================================================== render === */

const TABS = {};

function render() {
  for (const b of document.querySelectorAll("#tabs button")) b.classList.toggle("is-on", b.dataset.tab === state.tab);
  main.replaceChildren();
  TABS[state.tab]?.(main);
}

/* ---------------------------------------------------------- dashboard --- */

TABS.dashboard = (root) => {
  const projects = state.content.projects;
  const units = projects.flatMap((p) => p.units || []);
  const by = (s) => units.filter((u) => u.status === s).length;
  const prices = units.filter((u) => u.price > 0).map((u) => u.price);

  root.append(
    el("h2", { text: "Dashboard" }),
    el("p", { class: "sub", text: "What is on the site right now, and whether the last save reached it." }),
    el("div", { class: "stats" },
      stat(projects.length, "projects"),
      stat(units.length, "units"),
      stat(by("available"), "available"),
      stat(by("reserved"), "reserved"),
      stat(by("sold"), "sold"),
      stat(prices.length ? `${Math.min(...prices).toLocaleString()}` : "—", "lowest price, JOD"),
    ),
  );

  const deploys = el("div", { class: "card" },
    el("h3", { text: "Deploys" }),
    el("p", { class: "sub", text: "Saving commits; the commit triggers CI; CI deploys. This is the third step — the one that was silently not running while the live site sat twelve hours stale." }),
    el("ul", { class: "deploys" }, el("li", { text: "Loading…" })),
  );
  root.append(deploys);

  api("/api/deploys").then(({ runs }) => {
    const list = deploys.querySelector(".deploys");
    list.replaceChildren(...(runs.length ? runs.map((r) => el("li", {},
      el("span", { class: `badge badge--${r.conclusion === "success" ? "good" : r.conclusion ? "bad" : "warn"}`,
        text: r.conclusion || r.status }),
      el("code", { text: r.sha.slice(0, 7) }),
      el("span", { class: "msg", text: r.message }),
      el("a", { href: r.url, target: "_blank", rel: "noopener", text: "log" }),
    )) : [el("li", { text: "No deploy runs yet." })]));
  }).catch((e) => {
    deploys.querySelector(".deploys").replaceChildren(el("li", { text: `Could not read the deploy history: ${e.message}` }));
  });

  /* Unfinished, not false — the same list `npm run check` prints. */
  const gaps = [];
  if (!state.content.company.founded) gaps.push("The founding year is not set, so no page states one.");
  if (!state.content.company.address?.ar) gaps.push("There is no office address, so the footer address line and the office map stay hidden.");
  if (!state.content.company.formFields?.access_key) gaps.push("Enquiry capture is off — forms still hand over to WhatsApp, but nothing is recorded.");
  if (!(state.content.testimonials || []).some((t) => t.published !== false)) gaps.push("No testimonial is published, so that section stays hidden.");
  if (!(state.content.company.stats || []).length) gaps.push("No track-record figures, so the stats band stays hidden.");

  if (gaps.length) {
    root.append(el("div", { class: "card" },
      el("h3", { text: "Still to supply" }),
      el("p", { class: "sub", text: "None of these are errors. Each is something true that nobody has supplied yet, and the site hides the section rather than inventing it." }),
      el("ul", {}, gaps.map((g) => el("li", { text: g }))),
    ));
  }
};

const stat = (value, label) => el("div", { class: "stat" }, el("b", { text: String(value) }), el("span", { text: label }));

/* ----------------------------------------------------------- projects --- */

function projectPicker(onpick) {
  return el("div", { class: "picker" }, state.content.projects.map((p) =>
    el("button", {
      type: "button",
      class: state.project === p.id ? "is-on" : "",
      text: p.name.en,
      onclick: () => { state.project = p.id; onpick(); },
    })));
}

const currentProject = () =>
  state.content.projects.find((p) => p.id === state.project) || state.content.projects[0];

TABS.projects = (root) => {
  state.project ??= state.content.projects[0]?.id;
  root.append(
    el("h2", { text: "Projects" }),
    el("p", { class: "sub", text: "Everything a project page says about itself, apart from its schedule of units." }),
    projectPicker(render),
  );

  const p = currentProject();
  if (!p) return root.append(el("p", { class: "empty", text: "No projects." }));

  root.append(
    el("div", { class: "card" },
      el("h3", { text: "Identity" }),
      pair(p, "name", "Name"),
      pair(p, "tagline", "Tagline"),
      el("div", { class: "row" },
        el("label", { class: "field" }, el("span", { text: "District" }),
          select(p, "district", labelPairs(DISTRICTS))),
        el("label", { class: "field" }, el("span", { text: "Status" }),
          select(p, "status", labelPairs(PROJECT_STATUS), { blank: "— none, so no badge —", onchange: render })),
        el("label", { class: "field" }, el("span", { text: "Cover image" }), input(p, "image")),
      ),
      p.status === "selling" && !(p.units || []).some((u) => u.status === "available")
        ? el("p", { class: "badge badge--bad", text: "Marked selling, but no unit is available." }) : null,
    ),
    el("div", { class: "card" },
      el("h3", { text: "Description" }),
      pair(p, "description", null, { multiline: true }),
    ),
    el("div", { class: "card" },
      el("h3", { text: "Where it is" }),
      pair(p, "address", "Address"),
      el("label", { class: "field" }, el("span", { text: "Map search" }), input(p, "mapQuery"),
        el("small", { text: "What the map link searches for. A wrong one sends a buyer to the wrong street." })),
    ),
    listCard(p, "highlights", "Specification", "Each line is one specification claim from the brochure. Say only what the brochure says.",
      () => ({ ar: "", en: "" }), (item) => pair(item, null, null)),
    amenitiesCard(p),
    galleryCard(p),
  );
};

/** A card holding a reorderable list of bilingual items. */
function listCard(owner, key, title, sub, blank, renderItem) {
  owner[key] ??= [];
  const items = owner[key];
  const card = el("div", { class: "card" }, el("h3", { text: title }), sub ? el("p", { class: "sub", text: sub }) : null);
  const list = el("ul", { class: "list" });

  const draw = () => {
    list.replaceChildren(...(items.length ? items.map((item, i) => el("li", { class: "item" },
      el("div", { class: "item__head" },
        el("strong", { text: `${i + 1}` }),
        el("div", { class: "item__tools" },
          el("button", { type: "button", class: "btn btn--ghost btn--small", text: "↑", disabled: i === 0,
            onclick: () => { items.splice(i - 1, 0, items.splice(i, 1)[0]); draw(); touched(); } }),
          el("button", { type: "button", class: "btn btn--ghost btn--small", text: "↓", disabled: i === items.length - 1,
            onclick: () => { items.splice(i + 1, 0, items.splice(i, 1)[0]); draw(); touched(); } }),
          el("button", { type: "button", class: "btn btn--danger btn--small", text: "Remove",
            onclick: () => { items.splice(i, 1); draw(); touched(); } }),
        ),
      ),
      renderItem(item, i),
    )) : [el("li", { class: "empty", text: "Nothing here yet." })]));
  };
  draw();

  card.append(list, el("button", { type: "button", class: "btn btn--ghost btn--small", text: "Add",
    onclick: () => { items.push(blank()); draw(); touched(); } }));
  return card;
}

/** Bilingual pairs in a list are the item itself, not a field of it. */
const pairDirect = (item) => el("div", { class: "pair" },
  el("label", {}, el("span", { text: "العربية" }), input(item, "ar", { dir: "rtl", multiline: true })),
  el("label", {}, el("span", { text: "English" }), input(item, "en", { dir: "ltr", multiline: true })),
);

function amenitiesCard(p) {
  p.amenities ??= [];
  return el("div", { class: "card" },
    el("h3", { text: "Amenities" }),
    el("p", { class: "sub", text: "Only these ten exist. Adding an eleventh is a code change, so that a typo cannot quietly become a new amenity nobody has a label for." }),
    el("div", { class: "checks" }, Object.entries(AMENITIES).map(([key, label]) => {
      const box = el("input", { type: "checkbox", checked: p.amenities.includes(key) });
      box.addEventListener("change", () => {
        if (box.checked) p.amenities.push(key);
        else p.amenities.splice(p.amenities.indexOf(key), 1);
        touched();
      });
      return el("label", {}, box, `${label.en} — ${label.ar}`);
    })),
  );
}

function galleryCard(p) {
  p.gallery ??= [];
  const captions = state.content.imageCaptions;
  const card = el("div", { class: "card" },
    el("h3", { text: "Gallery" }),
    el("p", { class: "sub", text: "Image names, without the width or the .webp. A name with no file behind it fails the build rather than 404ing in front of a buyer — but only CI can see the files, so a typo here will not show up until then." }),
  );
  const list = el("ul", { class: "list" });
  const draw = () => {
    list.replaceChildren(...(p.gallery.length ? p.gallery.map((name, i) => {
      const box = { name };
      const cap = captions[name];
      return el("li", { class: "item" },
        el("div", { class: "item__head" },
          input(box, "name", { onchange: () => { p.gallery[i] = box.name; } }),
          el("div", { class: "item__tools" },
            el("button", { type: "button", class: "btn btn--ghost btn--small", text: "↑", disabled: i === 0,
              onclick: () => { p.gallery.splice(i - 1, 0, p.gallery.splice(i, 1)[0]); draw(); touched(); } }),
            el("button", { type: "button", class: "btn btn--ghost btn--small", text: "↓", disabled: i === p.gallery.length - 1,
              onclick: () => { p.gallery.splice(i + 1, 0, p.gallery.splice(i, 1)[0]); draw(); touched(); } }),
            el("button", { type: "button", class: "btn btn--danger btn--small", text: "Remove",
              onclick: () => { p.gallery.splice(i, 1); draw(); touched(); } }),
          ),
        ),
        cap ? pair(captions, name, "Caption") : el("p", { class: "sub", text: "No caption — the project page will number this image instead." }),
      );
    }) : [el("li", { class: "empty", text: "No images." })]));
  };
  draw();
  card.append(list, el("button", { type: "button", class: "btn btn--ghost btn--small", text: "Add",
    onclick: () => { p.gallery.push(""); draw(); touched(); } }));
  return card;
}

/* -------------------------------------------------------------- units --- */

TABS.units = (root) => {
  state.project ??= state.content.projects[0]?.id;
  root.append(
    el("h2", { text: "Units" }),
    el("p", { class: "sub", text: "The schedule, as the brochure publishes it. Prices are stated per unit and never calculated — real schedules do not follow a formula. Marking a unit sold removes its price; an available unit without one renders as unsellable." }),
    projectPicker(render),
  );

  const p = currentProject();
  if (!p) return;
  p.units ??= [];

  const body = el("tbody");
  const draw = () => {
    body.replaceChildren(...p.units.map((u, i) => el("tr", { class: u.status === "sold" ? "is-sold" : "" },
      el("td", {}, input(u, "code", { class: "code" })),
      el("td", {}, input(u, "floor", { type: "number", class: "code" })),
      el("td", {}, el("div", { class: "pair" },
        input(u.floorLabel ??= { ar: "", en: "" }, "ar", { dir: "rtl", class: "label" }),
        input(u.floorLabel, "en", { dir: "ltr", class: "label" }))),
      el("td", {}, select(u, "orientation", Object.entries(ORIENTATIONS).map(([k, v]) => [k, v.en]))),
      el("td", {}, input(u, "area", { type: "number" })),
      el("td", {}, input(u, "outdoor", { type: "number" })),
      el("td", {}, input(u, "beds", { type: "number" })),
      el("td", {}, input(u, "baths", { type: "number" })),
      el("td", {}, select(u, "type", Object.entries(UNIT_TYPES).map(([k, v]) => [k, v.en]))),
      el("td", {}, input(u, "plan", { class: "plan" })),
      el("td", {}, input(u, "price", { type: "number", blankIsNull: true })),
      el("td", {}, select(u, "status", UNIT_STATUS.map((s) => [s, s]), { onchange: draw })),
      el("td", {}, el("button", { type: "button", class: "btn btn--danger btn--small", text: "Remove",
        onclick: () => {
          if (!confirm(`Remove unit ${u.code} from ${p.name.en}? Anyone holding a link to it will land on the project page instead.`)) return;
          p.units.splice(i, 1); draw(); touched();
        } })),
    )));
  };
  draw();

  root.append(
    el("div", { class: "scroll" },
      el("table", {},
        el("thead", {}, el("tr", {}, ["Code", "Floor", "Floor label (ar / en)", "Aspect", "Area", "Outdoor", "Beds", "Baths", "Type", "Plan", "Price", "Status", ""]
          .map((h) => el("th", { text: h })))),
        body,
      ),
    ),
    el("p", {}, el("button", { type: "button", class: "btn btn--ghost btn--small", text: "Add a unit",
      onclick: () => {
        const last = p.units[p.units.length - 1];
        p.units.push({
          code: String(p.units.length + 1), floor: last?.floor ?? 0,
          floorLabel: clone(last?.floorLabel ?? { ar: "", en: "" }),
          orientation: "north", area: 0, outdoor: 0, beds: 3, baths: 3,
          type: "apartment", plan: "", price: 0, status: "available",
        });
        draw(); touched();
      } })),
  );
};

/* ----------------------------------------------------------- progress --- */

TABS.progress = (root) => {
  state.project ??= state.content.projects[0]?.id;
  root.append(
    el("h2", { text: "Construction progress" }),
    el("p", { class: "sub", text: "A dated log of what has actually been built. It renders as a timeline on the project page, newest first, and the page hides the section entirely while the log is empty — a buyer being shown no progress is better than being shown a stale one." }),
    projectPicker(render),
  );

  const p = currentProject();
  if (!p) return;

  root.append(listCard(p, "progress", `Log for ${p.name.en}`, null,
    () => ({ date: new Date().toISOString().slice(0, 10), percent: null, title: { ar: "", en: "" }, body: { ar: "", en: "" } }),
    (entry) => el("div", {},
      el("div", { class: "row" },
        el("label", { class: "field" }, el("span", { text: "Date" }), input(entry, "date", { type: "date" })),
        el("label", { class: "field" }, el("span", { text: "Percent complete" }),
          input(entry, "percent", { type: "number", blankIsNull: true, placeholder: "optional" })),
      ),
      pair(entry, "title", "Headline"),
      pair(entry, "body", "What was done", { multiline: true }),
    )));
};

/* --------------------------------------------------------------- faqs --- */

TABS.faqs = (root) => {
  root.append(
    el("h2", { text: "FAQs" }),
    el("p", { class: "sub", text: "Shown on the contact page. An answer that states a payment term, a delivery date or a legal fact is a commitment — write what is true, not what sells." }),
    listCard(state.content, "faqs", "Questions", null,
      () => ({ q: { ar: "", en: "" }, a: { ar: "", en: "" } }),
      (item) => el("div", {}, pair(item, "q", "Question"), pair(item, "a", "Answer", { multiline: true }))),
  );
};

/* ------------------------------------------------------- testimonials --- */

TABS.testimonials = (root) => {
  state.content.testimonials ??= [];
  root.append(
    el("h2", { text: "Testimonials" }),
    el("p", { class: "sub" },
      "The quotes that once sat here were invented for the build and were removed. A published testimonial is a real person's words attributed to them by name on a public page, so leave one unpublished until you have their permission — the site hides the section while none are published.",
    ),
    listCard(state.content, "testimonials", "Quotes", null,
      () => ({ published: false, name: { ar: "", en: "" }, role: { ar: "", en: "" }, quote: { ar: "", en: "" } }),
      (item) => {
        const box = el("input", { type: "checkbox", checked: item.published !== false });
        box.addEventListener("change", () => { item.published = box.checked; touched(); showProblems(); });
        return el("div", {},
          el("label", { class: "checks" }, box, "Published — appears on the site"),
          pair(item, "quote", "Quote", { multiline: true }),
          pair(item, "name", "Name"),
          pair(item, "role", "Role or project"),
        );
      }),
  );
};

/* -------------------------------------------------------------- leads --- */

TABS.leads = (root) => {
  root.append(
    el("h2", { text: "Leads" }),
    el("p", { class: "sub", text: "There is no lead list here, and that is the arrangement rather than a gap." }),

    el("div", { class: "card" },
      el("h3", { text: "Where an enquiry goes" }),
      el("p", {}, "Every form does two things. It hands the enquiry to WhatsApp, which is the delivery and has "
        + "always worked — that happens first, synchronously, so it survives even if the second step fails. Then "
        + "it posts a copy to Web3Forms, which emails it to the sales inbox."),
      el("p", {}, "WhatsApp is the channel a buyer in Amman actually replies on. The email is the record."),
    ),

    el("div", { class: "card" },
      el("h3", { text: "Why there is no table on this page" }),
      el("p", {}, "Reading submissions back out of Web3Forms needs their Submissions API, which is a paid "
        + "feature. The alternative was to store enquiries ourselves in a Cloudflare database — which would mean "
        + "this site keeps buyers' names and phone numbers, something it does not do today."),
      el("p", {}, "That was decided rather than deferred: the site keeps no personal data of its own. A panel that "
        + "listed leads here would be a panel that had a copy of every enquiry, and holding one is a different "
        + "commitment from passing one along."),
    ),

    /* The operational catch, stated where somebody will read it before it
       costs them an enquiry rather than after. */
    el("div", { class: "card" },
      el("h3", { text: "The one thing to know" }),
      el("p", {}, el("strong", { text: "Web3Forms keeps submissions for 30 days on the free plan." }),
        " After that the copy in their dashboard is gone. The email in the inbox is the durable record, so treat "
        + "the inbox as the archive and the dashboard as a recent view — do not delete an enquiry email expecting "
        + "to find it again later."),
      el("p", {}, "If enquiries ever need to be searched, exported or reported on, that is the point to revisit "
        + "this, not before."),
    ),

    el("div", { class: "card" },
      el("h3", { text: "Where to look" }),
      el("ul", {},
        el("li", {}, "The sales inbox — every enquiry, kept as long as you keep the email."),
        el("li", {}, el("a", { href: "https://web3forms.com/", target: "_blank", rel: "noopener", text: "web3forms.com" }),
          " — the last 30 days, with the IP and timestamp of each."),
        el("li", {}, "WhatsApp — the conversations themselves."),
      ),
    ),
  );
};

/* ================================================================= save === */

async function save() {
  const errors = validate(state.content);
  if (errors.length) { showProblems(); return; }

  const dialog = $("#saveDialog");
  const changed = summarise();
  $("#saveSummary").textContent = changed;
  $("#saveMessage").value = "";
  dialog.showModal();

  const choice = await new Promise((done) => dialog.addEventListener("close", () => done(dialog.returnValue), { once: true }));
  if (choice !== "save") return;

  const button = $("#save");
  button.disabled = true;
  say("Committing…");

  try {
    const res = await api("/api/content", {
      method: "PUT",
      body: JSON.stringify({ content: state.content, commit: state.commit, message: $("#saveMessage").value }),
    });
    if (res.unchanged) { say("Nothing had changed, so nothing was committed."); button.disabled = true; return; }
    state.saved = clone(state.content);
    state.commit = res.commit;
    touched();
    say(el("span", {}, `Committed ${res.commit.slice(0, 7)}. The deploy takes a minute or two — the Dashboard shows whether it lands.`), "good");
  } catch (e) {
    button.disabled = false;
    if (e.status === 409) {
      say(el("span", {}, e.message, " ", el("a", { href: "", text: "Reload" })), "bad");
      return;
    }
    if (e.errors?.length) {
      say(el("span", {}, el("strong", { text: "The save was refused: " }), el("ul", {}, e.errors.map((x) => el("li", { text: x })))), "bad");
      return;
    }
    say(`Could not save: ${e.message}`, "bad");
  }
}

/** A one-line description of what changed, so the save dialog is not a blank
    confirmation. Counts, not a diff — a diff belongs in the commit. */
function summarise() {
  const before = state.saved, after = state.content;
  const bits = [];
  const units = (c) => c.projects.flatMap((p) => (p.units || []).map((u) => `${p.id}-${u.code}`));
  const a = units(before), b = units(after);
  const added = b.filter((x) => !a.includes(x)).length;
  const removed = a.filter((x) => !b.includes(x)).length;
  if (added) bits.push(`${added} unit${added === 1 ? "" : "s"} added`);
  if (removed) bits.push(`${removed} unit${removed === 1 ? "" : "s"} removed`);

  const priced = (c) => Object.fromEntries(c.projects.flatMap((p) => (p.units || []).map((u) => [`${p.id}-${u.code}`, `${u.price}/${u.status}`])));
  const pa = priced(before), pb = priced(after);
  const moved = Object.keys(pb).filter((k) => pa[k] && pa[k] !== pb[k]).length;
  if (moved) bits.push(`${moved} price or status change${moved === 1 ? "" : "s"}`);

  if (JSON.stringify(before.faqs) !== JSON.stringify(after.faqs)) bits.push("FAQs edited");
  if (JSON.stringify(before.testimonials) !== JSON.stringify(after.testimonials)) bits.push("testimonials edited");

  return bits.length ? `${bits.join(", ")}.` : "Text changes only.";
}

/* ================================================================= boot === */

$("#tabs").addEventListener("click", (e) => {
  const tab = e.target.closest("button")?.dataset.tab;
  if (tab) { state.tab = tab; render(); }
});
$("#save").addEventListener("click", save);
$("#discard").addEventListener("click", () => {
  if (!confirm("Throw away every change since the page loaded?")) return;
  state.content = clone(state.saved);
  touched(); render();
});

/* A half-finished price edit lost to a stray tab close is a bad afternoon. */
addEventListener("beforeunload", (e) => { if (dirty()) e.preventDefault(); });

(async function boot() {
  try {
    const session = await api("/api/session");
    $("#repo").textContent = session.ready ? `${session.repo} · ${session.branch} · ${session.email}` : session.email;
    if (!session.ready) { main.replaceChildren(el("p", { class: "empty", text: session.error })); return; }

    const { content, commit } = await api("/api/content");
    state.content = content;
    state.saved = clone(content);
    state.commit = commit;
    render();
    touched();
  } catch (e) {
    main.replaceChildren(el("div", { class: "card" },
      el("h3", { text: "The panel could not start" }),
      el("p", { text: e.message }),
    ));
  }
})();
