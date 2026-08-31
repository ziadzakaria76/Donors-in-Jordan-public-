/**
 * Check the content file against the files and pages around it.
 *
 *   cd website && npm run check
 *
 * assets/js/data.js is meant to be edited by whoever is selling the units, not
 * only by whoever wrote the site. That is the point of keeping every price and
 * every unit in one plain file — and it is also the risk: a typo there is not a
 * syntax error, it is a page that renders a blank orientation, a plan tab that
 * fetches a drawing nobody made, or a "coming soon" project quietly holding
 * fourteen units for sale.
 *
 * None of that throws. The site degrades politely and says nothing, which is
 * the worst way for a price list to be wrong. So the invariants the code relies
 * on are asserted here instead, and CI runs it on every pull request.
 *
 * Every check below exists because breaking it produces something a visitor
 * would see. Nothing here is style.
 *
 * No dependencies, no network, no browser — this is the cheap gate. The
 * expensive one is a person opening the pages.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "./render-data.mjs";
import { validate } from "./validate-content.mjs";
import { rendered } from "./build-pages.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const img = (name) => existsSync(resolve(ROOT, "assets/img", name));
const read = (rel) => readFileSync(resolve(ROOT, rel), "utf8");

const DATA = (await import(resolve(ROOT, "assets/js/data.js"))).default;
const { COMPANY, PROJECTS } = DATA;

const errors = [];
const notes = [];
const check = (ok, message) => { if (!ok) errors.push(message); };

/* ----------------------------------------------------- data.js is generated
   content.json is the edited file and data.js is rendered from it, so a change
   made directly in data.js works locally, ships once, and then disappears the
   next time anyone regenerates — the worst kind of failure, because the price
   was right when you checked it.

   Rendering content.json here and comparing catches that while it is still a
   diff. If this fails after an intentional edit to the generator, run
   `npm run data` and commit the result. */

check(read("assets/js/data.js") === render(JSON.parse(read("content.json"))),
  "assets/js/data.js does not match content.json — it is generated, so edit content.json and run `npm run data`");

/* ------------------------------------------------ three runtimes, one module
   render-data.mjs and validate-content.mjs are imported by a Cloudflare Pages
   Function and by the admin panel in the browser, as well as by this script.
   Neither has `node:fs` — the Function would fail to bundle and the deploy
   would break, and the panel would fail to load with a bare import error.

   That is easy to undo by accident: adding one convenience import at the top
   of the validator is a natural thing to do and breaks two runtimes silently,
   because the third one — this one — would keep passing. */

for (const file of ["tools/render-data.mjs", "tools/validate-content.mjs"]) {
  const bad = [...read(file).matchAll(/^import[^;]*?from\s+"(node:[^"]+)"/gm)].map((m) => m[1]);
  check(!bad.length,
    `${file} imports ${bad.join(", ")}, but it also runs in a Worker and in the browser, where that does not exist — keep filesystem work in build-data.mjs`);
}

/* --------------------------------------------- statuses we cannot tell apart
   502 and 504 are the statuses Cloudflare answers with when a Pages Function
   dies or the platform is unwell. Its "Bad gateway / Host Error" page carries
   the same 502 this code would, so a 502 from the admin API is, from a browser,
   indistinguishable from the platform falling over: seeing one tells you
   nothing about whether our code ran at all.

   That ambiguity cost real hours here. The panel's GitHub failures and a
   genuine platform error looked identical, and the days spent deciding which
   we were looking at were days not spent on the actual broken permission.

   502 is an honest status to reach for when an upstream call fails — which is
   exactly why this has to be a rule and not a memory. */

for (const file of readdirSync(resolve(ROOT, "functions/api")).filter((f) => f.endsWith(".js"))) {
  const src = read(`functions/api/${file}`);
  const bad = [...src.matchAll(/\bstatus:\s*(502|504)\b|,\s*(502|504)\s*\)/g)];
  check(!bad.length,
    `functions/api/${file} returns ${bad.map((m) => m[1] || m[2]).join(", ")}, which a browser cannot tell apart from Cloudflare's own error page for a dead Function — use 500, so the status means our code answered`);
}

/* The admin panel imports those two directly. A moved or renamed file is a
   panel that fails to boot, and nothing else in the repository would notice. */
for (const spec of [...read("admin/admin.js").matchAll(/from\s+"(\.\.\/[^"]+)"/g)].map((m) => m[1])) {
  check(existsSync(resolve(ROOT, "admin", spec)), `admin/admin.js imports ${spec}, which is not there`);
}

/* --------------------------------------------------------------- images
   picture() offers the browser only the widths the manifest lists, and
   project.js asks for plan drawings at a hard-coded 800 and 1280. Either one
   naming a file that is not there is a 404 in front of a buyer. */

const referenced = new Set();
for (const p of PROJECTS) {
  referenced.add(p.image);
  for (const g of p.gallery || []) referenced.add(g);
  for (const u of p.units || []) if (u.plan) referenced.add(u.plan);
}

const manifest = read("assets/js/img-manifest.js");
const widthsOf = (name) => {
  const m = new RegExp(`"${name}": \\[([\\d, ]+)\\]`).exec(manifest);
  return m ? m[1].split(",").map((n) => Number(n.trim())) : null;
};

for (const name of referenced) {
  const widths = widthsOf(name);
  check(widths, `data.js references the image "${name}", which img-manifest.js does not list — run \`npm run manifest\``);
  for (const w of widths || []) {
    check(img(`${name}-${w}.webp`), `img-manifest.js promises assets/img/${name}-${w}.webp, which is not on disk`);
  }
}

for (const p of PROJECTS) {
  for (const u of p.units || []) {
    if (!u.plan) continue;
    for (const w of [800, 1280]) {
      check(img(`${u.plan}-${w}.webp`),
        `${p.id} unit ${u.code}: project.js will request ${u.plan}-${w}.webp, which is not on disk`);
    }
  }
}

/* The manifest is generated, so it can be regenerated and compared. A stale one
   is the failure that put 404s in the gallery in the first place. */
{
  const onDisk = {};
  for (const file of readdirSync(resolve(ROOT, "assets/img"))) {
    const m = /^(.+)-(\d+)\.webp$/.exec(file);
    if (m) (onDisk[m[1]] ??= []).push(Number(m[2]));
  }
  for (const [name, widths] of Object.entries(onDisk)) {
    widths.sort((a, b) => a - b);
    const listed = widthsOf(name);
    check(listed && listed.join() === widths.join(),
      `img-manifest.js is out of date for "${name}" (disk has ${widths.join(", ")}, manifest has ${listed ? listed.join(", ") : "nothing"}) — run \`npm run manifest\``);
  }
}

/* -------------------------------------------------- every <img> resolves
   The page-hero image is the largest, most visible request a page makes, and
   the scaffolder used to name a 1920 for every one of them. Most of these
   photographs come out of a sales brochure and stop at 1600, so a hero picked
   from those 404s on its `src` and again in its srcset — a blank band across
   the top of the page, in front of a buyer.

   Rather than trust the fix, check the output: every image URL the generated
   pages name has to exist on disk. */

for (const [file, html] of rendered) {
  for (const m of html.matchAll(/assets\/img\/([\w-]+\.webp)/g)) {
    check(img(m[1]), `${file} requests assets/img/${m[1]}, which is not on disk`);
  }
}

/* ------------------------------------------- the rules that need no disk
   Unit ids, the vocabulary every label resolves against, prices on available
   units, both languages filled in together. They live in validate-content.mjs
   because the admin panel runs them too — in the browser as you type, and in
   the Function before it commits. One list, three places. */

for (const e of validate(JSON.parse(read("content.json")))) errors.push(e);

/* ------------------------------------------------------- one domain, everywhere
   The canonical tags, the sitemap and robots.txt are written in three different
   places from three different sources. They only point search engines at one
   site if all three agree, and disagreeing is silent. */

const domain = COMPANY.domain.replace(/\/$/, "");
const site = /const SITE = "([^"]+)"/.exec(read("tools/build-pages.mjs"))?.[1];
check(site === domain, `tools/build-pages.mjs stamps canonical tags for ${site}, but COMPANY.domain is ${domain}`);

const robots = read("robots.txt");
check(robots.includes(`${domain}/sitemap.xml`), `robots.txt does not point at ${domain}/sitemap.xml`);

const sitemap = read("sitemap.xml");
const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
for (const loc of locs) check(loc.startsWith(domain), `sitemap.xml lists ${loc}, which is not on ${domain}`);

for (const file of readdirSync(ROOT)) {
  if (!file.endsWith(".html") || file === "404.html") continue;
  const path = file === "index.html" ? "/" : `/${file}`;
  check(locs.some((l) => new URL(l).pathname === path), `sitemap.xml does not list ${file}`);
}
/* One HTML file serves every project, so each needs its own sitemap entry or
   search engines are offered a page that renders nothing without an id. */
for (const p of PROJECTS) {
  check(locs.some((l) => l.includes(`id=${p.id}`)), `sitemap.xml does not list project ${p.id}`);
}

/* ------------------------------------------- three hosts, one cache policy
   _headers, netlify.toml and vercel.json say the same thing in three
   syntaxes, and a rule added to one and forgotten in the others is invisible
   until someone deploys to that host. The path that matters most is
   assets/js: the prices are in data.js, so caching it hard caches the price
   list. That was the actual mistake here once. */

for (const [file, needles] of [
  ["_headers", ["/assets/js/*", "/assets/css/*", "/*.html"]],
  ["netlify.toml", ["/assets/js/*", "/assets/css/*", "/*.html"]],
  ["vercel.json", ["/assets/js/(.*)", "/assets/css/(.*)", "/(.*).html"]],
]) {
  const text = read(file);
  for (const needle of needles) {
    check(text.includes(needle), `${file} has no cache rule for ${needle} — the three host configs must stay in step`);
  }
  check((text.match(/max-age=0, must-revalidate/g) || []).length >= needles.length,
    `${file} names ${needles.length} paths that must revalidate but sets the policy on fewer`);
}

/* ------------------------------------------------------------ unfinished
   Not failures. «REPLACE» marks something true that nobody has supplied yet,
   and printing them turns the go-live list into something you run. */

for (const line of read("assets/js/data.js").match(/^.*«REPLACE».*$/gm) || []) {
  const text = line.trim().replace(/^\/?\*+\s*/, "");
  if (text.startsWith("by accident.")) continue;   // the file header explaining the marker
  notes.push(text);
}

/* ------------------------------------------- the pages match the scaffolder
   Every page except index.html is generated by build-pages.mjs, and every page
   is also a finished file you can open and edit. That combination is a trap: an
   edit made in the page rather than the generator works, ships, and then
   disappears the first time anyone runs `npm run pages`.

   It had already happened twice — a construction-progress section added
   straight to project.html, and an aspect filter added straight to units.html —
   and in both cases the scaffolder would have deleted them silently.

   So the generated pages are compared to the generator, the same way data.js is
   compared to content.json. If this fails, decide which of the two is right:
   put the change in build-pages.mjs and run `npm run pages`. */

for (const [file, html] of rendered) {
  check(read(file) === html,
    `${file} does not match what tools/build-pages.mjs generates — put the change in the generator and run \`npm run pages\`, or it will be deleted the next time somebody does`);
}

/* ------------------------------------------ every renderer has somewhere to go
   pages.js renders into elements it looks up by id. If the markup for one is on
   no page, the renderer is dead code and — worse — whatever writes that content
   is writing into a void.

   That has happened twice. The FAQ renderer had no page until this month, so
   content.json held five questions nobody could read and the admin panel's FAQ
   editor changed nothing. Then the testimonials section was removed from
   index.html while its renderer stayed, so the panel invited an editor to
   publish a real person's words and would have shown them nowhere.

   Both failures are silent: the renderer returns early, the page looks fine,
   and only the person who supplied the content finds out, later.

   A deliberately removed section is fine — name it in REMOVED below, so the
   decision is written down rather than indistinguishable from an accident. */

{
  const REMOVED = {
    "home-stats": "the stats band went with the invented figures; about.html now shows the three real buildings instead (README -> Restoring the stats and testimonials)",
    "contact-map": "no office address is published, so there is no office to map (README -> Restoring the office address)",
    "project-filters": "three projects do not need filtering; the grid shows all of them",
  };
  const allPages = readdirSync(ROOT).filter((f) => f.endsWith(".html")).map((f) => read(f)).join("\n");
  const targets = [...read("assets/js/pages.js").matchAll(/\$\("#([\w-]+)"\)/g)].map((m) => m[1]);

  for (const id of new Set(targets)) {
    if (REMOVED[id]) { notes.push(`section "${id}" is deliberately absent: ${REMOVED[id]}`); continue; }
    check(allPages.includes(`id="${id}"`),
      `assets/js/pages.js renders into #${id}, which no page contains — the renderer is dead, and anything writing that content is writing into a void. Restore the markup, or list it in REMOVED in this file with the reason.`);
  }
}

/* ------------------------------------------------ the deploy finds the API
   Wrangler resolves Pages Functions from `path.join(process.cwd(), "functions")`
   — its working directory, never the directory being uploaded — and wrangler 4
   removed the --functions-directory flag that used to make this explicit.

   So the deploy step must run from website/. Run from the repository root, the
   upload succeeds, the workflow goes green, and every /api/* route answers with
   the static 404 page. That is exactly how the admin panel first shipped: a
   successful deploy of a site with no API in it.

   Asserted here because it is a one-line change in a file nobody edits often,
   it produces no error anywhere, and the panel is the only thing that notices. */

for (const [file, stepName] of [
  ["deploy-website.yml", "Deploy to Cloudflare Pages"],
  ["preview-website.yml", "Deploy the preview"],
]) {
  const workflow = resolve(ROOT, "../.github/workflows", file);
  if (!existsSync(workflow)) continue;
  const text = readFileSync(workflow, "utf8");
  const step = new RegExp(`- name: ${stepName}\\n([\\s\\S]*?)\\n        run:`).exec(text);
  check(step && /working-directory:\s*website/.test(step[1]),
    `the "${stepName}" step in .github/workflows/${file} must set \`working-directory: website\`, or wrangler will not find website/functions and every /api/* route will 404`);
}

/* A preview that lands on the production branch is not a preview — it is an
   unreviewed pull request published to the live domain. */
{
  const preview = resolve(ROOT, "../.github/workflows/preview-website.yml");
  if (existsSync(preview)) {
    const text = readFileSync(preview, "utf8");
    check(/BRANCH="pr-/.test(text) && /Refusing to deploy/.test(text),
      "preview-website.yml must deploy under a `pr-` branch and refuse to run if that equals the production branch — otherwise a pull request publishes to the live site");
    check(/Disallow: \/\\n/.test(text) && /X-Robots-Tag: noindex, nofollow/.test(text),
      "preview-website.yml must make the preview refuse indexing — it is a full copy of a site with live prices on a public URL");
    check(/head\.repo\.full_name == github\.repository/.test(text),
      "preview-website.yml must not run for pull requests from forks — it holds the Cloudflare deploy token");
  }
}

/* ------------------------------------------------------------------ out */

if (errors.length) {
  console.error(`\n  ✗ ${errors.length} problem${errors.length === 1 ? "" : "s"} in the content:\n`);
  for (const e of errors) console.error(`    - ${e}`);
  console.error("");
  process.exit(1);
}

const units = PROJECTS.reduce((n, p) => n + (p.units || []).length, 0);
console.log(`  ✓ ${PROJECTS.length} projects, ${units} units, ${referenced.size} images — content checks pass`);
if (notes.length) {
  console.log(`\n  Still to supply (${notes.length}):`);
  for (const n of notes) console.log(`    · ${n}`);
}
