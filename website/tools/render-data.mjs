/**
 * Render content.json as assets/js/data.js. Pure: no filesystem, no network.
 *
 * WHY THERE ARE TWO FILES. data.js is what the browser loads, and it is also
 * documentation: its comments record why the founding year is null, why the
 * testimonials array is empty, why a sold unit carries no price, and why the
 * commercial registration is absent rather than invented. Those comments are
 * the reason nobody has quietly re-added the content that was removed. They
 * must survive, and a web form rewriting a commented source file is how
 * comments die. So the two jobs are split:
 *
 *   content.json   what a person or the admin panel edits — projects, units,
 *                  prices, FAQs, testimonials, captions, the company's details
 *   this file      the prose, the enumerations, and the code around them
 *   data.js        rendered from both, and never edited by hand
 *
 * The enumerations stay here on purpose. DISTRICTS, AMENITIES, ORIENTATIONS,
 * UNIT_TYPES and PROJECT_STATUS are not content — they are the vocabulary the
 * content is checked against, and a panel able to invent a new orientation
 * would defeat the check that catches a mistyped one.
 *
 * WHY IT IMPORTS NOTHING. This module runs in three places: the `npm run data`
 * CLI, the `npm run check` staleness gate, and a Cloudflare Pages Function
 * where the admin panel saves. That last one is a Workers runtime with no
 * `node:fs`, so a single top-level `import ... from "node:fs"` here would
 * break the deploy at bundle time. build-data.mjs holds the file I/O instead.
 */

/* --------------------------------------------------------------- vocabulary
   The five enumerations, defined here rather than in content.json, and this is
   the whole point of the split.

   Districts, amenities, unit types, orientations and project statuses are not
   content — they are the vocabulary the content is checked *against*. A panel
   that could add an orientation would be a panel that could make a typo pass
   validation: check-content.mjs catches "sotuh" only because "sotuh" is not on
   this list, and a writable list is not a list. Adding a real one is a code
   change, reviewed as a diff, which is the correct weight for changing what
   the site is able to say.

   Exported because the validator and the admin panel both need to know what is
   allowed, and two copies of an allow-list is one copy too many.
   -------------------------------------------------------------------------- */

export const DISTRICTS = {
  "marj-al-hamam": { ar: "مرج الحمام", en: "Marj Al-Hamam" },
};

export const AMENITIES = {
  gym: { ar: "نادٍ رياضي", en: "Gym" },
  pool: { ar: "مسبح", en: "Swimming pool" },
  reception: { ar: "استقبال ٢٤ ساعة", en: "24-hour reception" },
  generator: { ar: "مولّد كهربائي", en: "Standby generator" },
  parking: { ar: "مواقف مغطّاة", en: "Covered parking" },
  security: { ar: "حراسة ومراقبة", en: "Security and CCTV" },
  elevator: { ar: "مصاعد", en: "Lifts" },
  storage: { ar: "مستودع خاص", en: "Private storage" },
  garden: { ar: "حديقة", en: "Landscaped garden" },
  playground: { ar: "منطقة ألعاب", en: "Children's play area" },
};

export const UNIT_TYPES = {
  apartment: { ar: "شقة", en: "Apartment" },
  roof: { ar: "شقة مع روف", en: "Apartment with roof terrace" },
};

export const ORIENTATIONS = {
  north: { ar: "شمالية", en: "North facing" },
  south: { ar: "جنوبية", en: "South facing" },
  east: { ar: "شرقية", en: "East facing" },
  west: { ar: "غربية", en: "West facing" },
  northeast: { ar: "شمالية شرقية", en: "North-east facing" },
  southeast: { ar: "جنوبية شرقية", en: "South-east facing" },
  southwest: { ar: "جنوبية غربية", en: "South-west facing" },
};

export const PROJECT_STATUS = {
  selling: { ar: "متاح للبيع", en: "Now selling" },
  delivered: { ar: "مُسلَّم", en: "Delivered" },
  upcoming: { ar: "مشروع قادم", en: "Coming soon" },
  soldout: { ar: "بيعت بالكامل", en: "Fully sold" },
};

export const UNIT_STATUS = ["available", "reserved", "sold"];

/**
 * JSON, but formatted the way a person would write it in a source file.
 *
 * Not cosmetic. Every price change in this repository is reviewed as a diff,
 * and `{ ar: "…", en: "…" }` on one line makes a changed word a one-line
 * change. Expanded over four lines, the same edit becomes six lines of noise
 * around the thing you are trying to check.
 */
const IDENT = /^[A-Za-z_$][\w$]*$/;
const WIDTH = 96;

/**
 * A bilingual string is one value, not two, so it never splits below the pair.
 *
 * It is also the thing most often changed. Wrapping `{ ar: "…", en: "…" }`
 * because the Arabic pushed it past 96 columns turns a one-word correction
 * into a six-line diff — the diff nobody reads carefully. So a pair keeps its
 * own generous budget, and when it does overflow it gives each language a
 * whole line and stops there. Never a line per word, never a line per brace.
 *
 * 240 characters puts every label, highlight and process step on one line and
 * splits only the eight paragraph-length pairs: the project descriptions, the
 * FAQ answers, and the company intro. Those read as prose either way.
 */
const PAIR_WIDTH = 240;

const isBilingual = (v) =>
  v !== null && typeof v === "object" && !Array.isArray(v) &&
  Object.keys(v).length === 2 && typeof v.ar === "string" && typeof v.en === "string";

function j(value, indent = 0) {
  const pad = " ".repeat(indent);
  if (value === null || typeof value !== "object") return JSON.stringify(value);

  if (isBilingual(value)) {
    const flat = `{ ar: ${JSON.stringify(value.ar)}, en: ${JSON.stringify(value.en)} }`;
    if (flat.length + indent <= PAIR_WIDTH) return flat;
    return `{\n${pad}  ar: ${JSON.stringify(value.ar)},\n${pad}  en: ${JSON.stringify(value.en)},\n${pad}}`;
  }

  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    const parts = value.map((v) => j(v, indent + 2));
    const flat = `[${parts.join(", ")}]`;
    if (flat.length + indent <= WIDTH && !flat.includes("\n")) return flat;
    return `[\n${parts.map((p) => `${pad}  ${p}`).join(",\n")},\n${pad}]`;
  }

  const entries = Object.entries(value);
  if (!entries.length) return "{}";
  const parts = entries.map(([k, v]) => `${IDENT.test(k) ? k : JSON.stringify(k)}: ${j(v, indent + 2)}`);
  const flat = `{ ${parts.join(", ")} }`;
  if (flat.length + indent <= WIDTH && !flat.includes("\n")) return flat;
  return `{\n${parts.map((p) => `${pad}  ${p}`).join(",\n")},\n${pad}}`;
}

/* --------------------------------------------------------------------------
   The notes that travel with COMPANY's fields.

   These are the most load-bearing comments in the generated file: they are the
   reason nobody has quietly re-added a founding year, invented a commercial
   registration, or "fixed" an empty formFields by deleting the feature. A
   generator that emitted the values and dropped the notes would lose exactly
   the part worth keeping, so the notes live here and are re-emitted every run.

   `before` is block comment text above the field; `after` is a trailing note.
   -------------------------------------------------------------------------- */
const COMPANY_NOTES = {
  founded: { after: "«REPLACE» — unverified, so no page states one" },
  whatsapp: { after: "same mobile as `phone` — change if WhatsApp is on another line" },
  salesEmail: { after: "one address for both for now" },
  domain: {
    before: [
      `Registered with Cloudflare. Apex, no \`www\` — the www host should 301 here
so Google sees one address, not two. This string must stay in step with
SITE in tools/build-pages.mjs, which stamps the canonical, og:url and
hreflang tags into every page, and with sitemap.xml and robots.txt.`,
    ],
  },
  address: {
    before: [
      `Deliberately blank. The footer's address line, the contact page's office
row and the office map are all removed while these are empty; fill either
one in and restore the markup (README → "Removed sections") to bring the
office back.`,
    ],
  },
  formEndpoint: {
    before: [
      `Where a copy of each enquiry is recorded. WhatsApp is the delivery and
always runs; this is the record, and runs as well once it is configured.
Web3Forms is the chosen service: one fixed URL for everybody, with the
destination inbox named by the access_key below.
See README → "Where the form submissions go".`,
    ],
  },
  formFields: {
    before: [
      `Extra fields the service needs in the body. The key is public by design —
Web3Forms says so on the page that issues it: it names an inbox, it does
not open one. So it belongs here rather than in a secret a static host has
no way to read, and anything the browser must send is visible anyway.

This key decides where enquiries land, and nothing in this repository
records which inbox that is. It was issued against the account that set
the form up, which is not the address the site publishes — so treat the
destination as unverified until a real test enquiry has arrived somewhere.

To move it: have Web3Forms issue a key to the address you want, and put
that key here. An earlier note claimed the recipient could be changed in a
dashboard while the key stayed the same; that was never verified, and
Web3Forms issues a key against an email address, so reissuing is the route
that is known to work.

Emptying this switches capture off rather than breaking it: captureReady()
skips the POST entirely, and every form still hands the enquiry to
WhatsApp exactly as before.`,
    ],
  },
  social: {
    before: [
      `No commercial registration. The number that sat here was invented, and an
invented registration number is a claim about a real company's legal
standing, so it is gone rather than left for someone to render by
accident. Add the real one here when it is to hand, and write it into the
footer deliberately — nothing reads this field today.`,
      `No social accounts yet. When there are, add them here and restore the
.socials list in the footer (README → "Removed sections").`,
    ],
  },
  stats: {
    before: [
      `Track record. Empty because the figures that were here were invented for
the build, and the site now carries the real name and logo. To bring the
band back: add entries here and restore the stats <section> in index.html
and about.html (see README → "Restoring the stats and testimonials").`,
    ],
  },
};

/** COMPANY, field by field, so each field keeps the note that explains it. */
function companyBlock(company) {
  const lines = [];
  for (const [key, value] of Object.entries(company)) {
    const note = COMPANY_NOTES[key] || {};
    for (const block of note.before || []) {
      const [head, ...rest] = block.split("\n");
      lines.push(`  /* ${head}`);
      for (const line of rest) lines.push(line ? `     ${line}` : "");
      lines[lines.length - 1] += " */";
    }
    const code = `  ${key}: ${j(value, 2)},`;
    lines.push(note.after ? `${code.padEnd(38)} // ${note.after}` : code);
  }
  return `{\n${lines.join("\n")}\n}`;
}

/** One unit per line: the schedule reads as a table, which is how it is checked. */
function unitLines(units) {
  const w = (s, n) => String(s).padEnd(n);
  return units.map((u) => {
    const parts = [
      `code: ${w(JSON.stringify(u.code) + ",", 6)}`,
      `floor: ${w(u.floor + ",", 3)}`,
      `floorLabel: { ar: ${JSON.stringify(u.floorLabel.ar)}, en: ${JSON.stringify(u.floorLabel.en)} },`,
      `orientation: ${w(JSON.stringify(u.orientation) + ",", 13)}`,
      `area: ${w(u.area + ",", 5)}`,
      `outdoor: ${w((u.outdoor ?? 0) + ",", 5)}`,
      `beds: ${u.beds},`,
      `baths: ${u.baths},`,
      `type: ${w(JSON.stringify(u.type) + ",", 12)}`,
      u.plan ? `plan: ${w(JSON.stringify(u.plan) + ",", 11)}` : null,
      u.price ? `price: ${w(u.price + ",", 8)}` : null,
      `status: ${JSON.stringify(u.status)}`,
    ].filter(Boolean);
    return `      { ${parts.join(" ")} },`;
  }).join("\n");
}

/**
 * One project.
 *
 * `notes` is a map of field name → provenance note, and it is content, not
 * decoration: "the brochure marks none as sold" and "no status, because the
 * brochure does not say" are the record of why the data looks the way it does.
 * Losing them is how a gap in a brochure turns into a guess on a page, so they
 * are edited alongside the project in content.json and re-emitted every run.
 */
function project(p) {
  const notes = p.notes || {};
  const note = (name) => {
    if (!notes[name]) return "";
    const lines = notes[name].split("\n").map((l, i) => (i ? `       ${l}` : `    /* ${l}`));
    return `${lines.join("\n")} */\n`;
  };
  const field = (name, value) =>
    value === undefined ? "" : `${note(name)}    ${name}: ${j(value, 4)},\n`;
  return `  {
    id: ${JSON.stringify(p.id)},
    name: ${j(p.name, 4)},
    district: ${JSON.stringify(p.district)},
${p.status ? `${note("status")}    status: ${JSON.stringify(p.status)},\n` : note("status")}${field("image", p.image)}${field("address", p.address)}${field("mapQuery", p.mapQuery)}${field("tagline", p.tagline)}${field("description", p.description)}${field("highlights", p.highlights)}${field("amenities", p.amenities)}${field("nearby", p.nearby)}${field("progress", p.progress)}${field("gallery", p.gallery)}${note("units")}    units: [
${p.units.length ? unitLines(p.units) : ""}
    ],
  },`;
}

/**
 * The whole of data.js, as a string.
 *
 * Exported rather than written straight to disk so check-content.mjs can
 * render content.json and compare the result to the file that is actually
 * committed. A hand-edited data.js then fails CI, instead of shipping once and
 * vanishing the next time the deploy regenerates the file over the top.
 */
export function render(content) {
  return `/* =============================================================================
   SITE CONTENT — GENERATED. Do not edit by hand.

   Every project, price, unit and caption in this file comes from content.json,
   which is what the admin panel writes. Edit content.json, run \`npm run data\`,
   and commit both. An edit made here instead is caught by \`npm run check\` and
   lost at the next regeneration — the deploy does not rebuild this file,
   precisely so that the mismatch is a failed check rather than a silent
   overwrite of somebody's correction.

   The enumerations below — districts, amenities, orientations, unit types,
   project statuses — are deliberately NOT in content.json. They are the
   vocabulary that content is checked against, and a panel able to invent a new
   orientation would defeat the check that catches a mistyped one.

   WHAT IS REAL HERE: the company name and logo, the phone, WhatsApp and email,
   and the projects and their unit schedules, which come from the sales
   brochures. The invented content this file once carried — the payment plans,
   the track-record figures, the testimonials, the founding year and the
   commercial registration — was removed rather than left to be published by
   accident. Anything still empty is unfinished, not false.
   ========================================================================== */

const COMPANY = ${companyBlock(content.company)};

/* --------------------------------------------------------------- districts */

const DISTRICTS = ${j(DISTRICTS)};

/* ---------------------------------------------------------------- projects
   Each project carries its own schedule of units, stated one at a time as the
   sales brochure publishes them. Prices are stated, never calculated — real
   schedules do not follow a formula — and a sold unit carries no price,
   because the brochure publishes none.
   -------------------------------------------------------------------------- */

const PROJECTS = [
${content.projects.map(project).join("\n")}
];

/* ------------------------------------------------------- image captions
   What each photograph is, in both languages. The gallery page builds itself
   from these keys; a project page uses them to caption its images instead of
   numbering them. An image with no entry still renders — the project page
   falls back to numbering it — so this is a caption list, not a permission
   list. */

const IMAGE_CAPTIONS = ${j(content.imageCaptions)};

/* ---------------------------------------------------------------- amenities */

const AMENITIES = ${j(AMENITIES)};

/* ------------------------------------------------------------ testimonials
   Only entries marked published render. The quotes that once sat here were
   invented for the build; the section stays empty until real, permissioned
   ones exist, and the draft flag is what lets the panel hold one before it is
   ready rather than publishing it by accident. */

const TESTIMONIALS = ${j(content.testimonials.filter((t) => t.published !== false).map(({ published, ...rest }) => rest))};

/* ---------------------------------------------------------------- process */

const PROCESS = ${j(content.process)};

/* -------------------------------------------------------------------- FAQ */

const FAQS = ${j(content.faqs)};

/* ------------------------------------------------------- derived inventory */

const UNIT_STATUS = { available: "available", reserved: "reserved", sold: "sold" };

/**
 * Expand each project's units into the flat list the site works with.
 *
 * Real schedules do not follow a formula — in General Sherman 2 the same
 * 152 m² layout is 88,000 on the first floor and 88,000 again on the third,
 * while a 190 m² lower-ground unit is 117,000 — so prices are stated per unit
 * rather than derived from a rate and a floor premium. A sold unit carries no
 * price at all, because the brochure does not publish one.
 */
function buildUnits() {
  const units = [];
  for (const p of PROJECTS) {
    for (const u of p.units || []) {
      units.push({
        ...u,
        id: \`\${p.id}-\${u.code}\`,
        projectId: p.id,
        district: p.district,
        outdoor: u.outdoor ?? 0,
        price: u.price ?? null,
      });
    }
  }
  return units;
}

const UNITS = buildUnits();

const UNIT_TYPES = ${j(UNIT_TYPES)};

const ORIENTATIONS = ${j(ORIENTATIONS)};

const PROJECT_STATUS = ${j(PROJECT_STATUS)};


const DATA = {
  COMPANY, DISTRICTS, PROJECTS, UNITS, AMENITIES, TESTIMONIALS,
  PROCESS, FAQS, UNIT_TYPES, ORIENTATIONS, PROJECT_STATUS, IMAGE_CAPTIONS,
};

if (typeof window !== "undefined") window.DATA = DATA;
if (typeof module !== "undefined") module.exports = DATA;
`;
}
