/**
 * The content rules that need nothing but the content itself.
 *
 * Split out of check-content.mjs so the admin panel can run them too. The panel
 * saves by committing to the repository, so CI is still the real gate — but a
 * gate that only fires after you have pushed is a bad way to learn you typed
 * "sotuh". These run in the browser as you edit, and again in the Function
 * before it writes anything, and again in CI. Same list, three places, no
 * second copy of the rules to drift.
 *
 * What is NOT here: everything that needs the filesystem — images existing at
 * the widths the manifest promises, the manifest matching disk, the domain
 * agreeing across build-pages.mjs, sitemap.xml and robots.txt. Those stay in
 * check-content.mjs, because a Worker has no disk to check.
 *
 * Every rule below exists because breaking it produces something a visitor
 * would see, and none of them throw on their own. That is the point: the site
 * degrades politely and says nothing, which is the worst way for a price list
 * to be wrong.
 */

import { DISTRICTS, AMENITIES, ORIENTATIONS, UNIT_TYPES, PROJECT_STATUS, UNIT_STATUS } from "./render-data.mjs";

/** @returns {string[]} one message per problem; empty means it is publishable. */
export function validate(content) {
  const errors = [];
  const check = (ok, message) => { if (!ok) errors.push(message); };

  if (!content || typeof content !== "object") return ["content is not an object"];
  if (!Array.isArray(content.projects)) return ["content.projects is missing or not an array"];

  /* ------------------------------------------------------------- projects */

  const seenProject = new Set();
  const seenUnit = new Set();

  for (const p of content.projects) {
    check(p.id && /^[a-z0-9-]+$/.test(p.id),
      `project id "${p.id}" must be lowercase letters, digits and hyphens — it goes in a URL and an element id`);
    check(!seenProject.has(p.id), `two projects share the id "${p.id}"`);
    seenProject.add(p.id);

    check(DISTRICTS[p.district], `${p.id}: district "${p.district}" has no label`);
    if (p.status) check(PROJECT_STATUS[p.status], `${p.id}: status "${p.status}" has no label`);
    for (const a of p.amenities || []) check(AMENITIES[a], `${p.id}: amenity "${a}" has no label`);

    check(p.image, `${p.id}: has no cover image`);

    // `notes` is the one field whose text reaches data.js unquoted — it is
    // rendered as a block comment. A comment terminator inside one would close
    // that comment early and leave the rest of the note parsed as code: a site
    // whose every page is blank, since data.js is the first script every page
    // loads. Nothing legitimate needs one.
    //
    // (Line comments here on purpose. Writing this rule as a block comment is
    // how I broke this file the first time.)
    for (const [field, text] of Object.entries(p.notes || {})) {
      check(typeof text === "string", `${p.id}: note on "${field}" is not text`);
      check(!String(text).includes("*/"),
        `${p.id}: the note on "${field}" contains "*/", which would end its comment early and break every page`);
    }

    for (const u of p.units || []) {
      const at = `${p.id} unit ${u.code}`;
      const id = `${p.id}-${u.code}`;
      check(u.code !== undefined && u.code !== "", `${p.id}: a unit has no code`);
      check(!seenUnit.has(id),
        `duplicate unit id ${id} — unit ids are element ids on the project page, so two of them break the deep link to both`);
      seenUnit.add(id);

      check(ORIENTATIONS[u.orientation],
        `${at}: orientation "${u.orientation}" has no label — the card would render a blank where the aspect goes`);
      check(UNIT_TYPES[u.type], `${at}: type "${u.type}" has no label`);
      check(u.floorLabel?.ar && u.floorLabel?.en, `${at}: floorLabel is missing a language`);
      check(Number.isInteger(u.floor), `${at}: floor is ${u.floor}, which is not a whole number`);
      check(Number.isFinite(u.area) && u.area > 0, `${at}: area is ${u.area}`);
      check(Number.isFinite(u.outdoor ?? 0) && (u.outdoor ?? 0) >= 0, `${at}: outdoor is ${u.outdoor}`);
      check(u.beds > 0 && u.baths > 0, `${at}: beds/baths are ${u.beds}/${u.baths}`);
      check(UNIT_STATUS.includes(u.status), `${at}: status "${u.status}" is not ${UNIT_STATUS.join(", ")}`);

      /* An available unit with no price renders as sold: unitCard treats a
         missing price as unsellable, so the schedule would hide it. */
      if (u.status === "available") {
        check(u.price > 0, `${at}: is available but carries no price, so the site will show it as unsellable`);
      }
      if (u.type === "roof") check((u.outdoor ?? 0) > 0, `${at}: is typed "roof" but has no outdoor area`);

      /* Plan tabs are labelled by area, so one drawing shared by units of
         different sizes would label itself with only the first unit's. */
      const sharing = (p.units || []).filter((x) => x.plan && x.plan === u.plan);
      check(sharing.every((x) => x.area === u.area),
        `${p.id}: plan ${u.plan} is shared by units of different areas (${[...new Set(sharing.map((x) => x.area))].join(", ")})`);
    }

    if (p.status === "selling") {
      check((p.units || []).some((u) => u.status === "available"),
        `${p.id}: is marked "selling" but no unit is available`);
    }
  }

  /* -------------------------------------------------------- both languages
     Arabic is the site's first language and English is applied over it, so a
     pair with one side filled in renders the other language's page with a gap
     nobody notices until a buyer does. */

  const walk = (node, at) => {
    if (!node || typeof node !== "object") return;
    const keys = Object.keys(node);
    if (keys.includes("ar") || keys.includes("en")) {
      check(node.ar !== undefined && node.en !== undefined,
        `${at}: bilingual text is missing "${node.ar === undefined ? "ar" : "en"}"`);
      if (typeof node.ar === "string" && typeof node.en === "string") {
        check(!!node.ar.trim() === !!node.en.trim(), `${at}: one language is filled in and the other is empty`);
      }
      return;
    }
    for (const [key, value] of Object.entries(node)) walk(value, `${at}.${key}`);
  };
  walk(content.projects, "projects");
  walk(content.process, "process");
  walk(content.faqs, "faqs");
  walk(content.imageCaptions, "imageCaptions");

  /* ---------------------------------------------------------- testimonials
     A published testimonial is a real person's words attributed to them by
     name on a public page. Everything the panel can hold in draft is fine; a
     published one missing its quote or its attribution is not. */

  for (const [i, t] of (content.testimonials || []).entries()) {
    if (t.published === false) continue;
    check(t.quote?.ar?.trim() && t.quote?.en?.trim(), `testimonial ${i + 1}: published with an empty quote in one language`);
    check(t.name?.ar?.trim() && t.name?.en?.trim(), `testimonial ${i + 1}: published with no attribution`);
  }

  return errors;
}
