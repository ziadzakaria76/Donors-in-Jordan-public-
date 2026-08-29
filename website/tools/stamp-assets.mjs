/**
 * Put a content hash in every CSS and JS URL, so a cached copy cannot be stale.
 *
 *   cd website && npm run stamp
 *
 * WHY THIS EXISTS. Every price, every unit and the phone number live in
 * assets/js/data.js. The filename never changes, so any cache anywhere -- the
 * visitor's browser, a CDN edge, a corporate proxy -- can hold an old copy of
 * the price list and there is no way to reach it. That is not hypothetical:
 * the General Sherman 3 schedule went live and the site kept showing "coming
 * soon" with no units, because the browser was still using a data.js it had
 * kept from before.
 *
 * `Cache-Control: must-revalidate` in _headers asks politely. This does not
 * ask: assets/js/data.js?v=6f2a9c41 is a different URL from
 * assets/js/data.js?v=1b7e0d33, so nothing can serve one when the page asks
 * for the other. The HTML that names them is itself never cached hard, so a
 * new hash reaches visitors on their next page load.
 *
 * WHY IT RUNS IN CI RATHER THAN BEING COMMITTED. Committed stamps would go
 * stale the moment someone edits data.js and forgets to re-run this -- which
 * is exactly the failure it exists to prevent, reintroduced with an extra
 * step. The deploy workflow runs it on its own disposable checkout, so the
 * repository keeps plain, openable files and the deployed copy is stamped
 * without anyone having to remember.
 *
 * Idempotent: running it twice replaces the stamp rather than doubling it.
 */

import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Eight hex characters is ~4 billion values; collisions are not the risk here. */
const hashes = new Map();
function stampFor(rel) {
  if (!hashes.has(rel)) {
    const bytes = readFileSync(resolve(ROOT, rel));
    hashes.set(rel, createHash("sha256").update(bytes).digest("hex").slice(0, 8));
  }
  return hashes.get(rel);
}

/* src="assets/js/data.js" and href="assets/css/main.css", with or without an
   existing ?v= to replace. Nothing else is touched -- images are named per
   width and already cached on their own terms, and the fonts are immutable. */
const REF = /(\ssrc="|\shref=")(assets\/(?:js|css)\/[\w.-]+\.(?:js|css))(?:\?v=[0-9a-f]+)?(")/g;

let files = 0;
let refs = 0;
for (const file of readdirSync(ROOT)) {
  if (!file.endsWith(".html")) continue;
  const path = resolve(ROOT, file);
  const before = readFileSync(path, "utf8");
  const after = before.replace(REF, (_, lead, rel, tail) => {
    refs++;
    return `${lead}${rel}?v=${stampFor(rel)}${tail}`;
  });
  if (after !== before) { writeFileSync(path, after); files++; }
}

console.log(`  ✓ stamped ${refs} references across ${files} page${files === 1 ? "" : "s"}`);
for (const [rel, hash] of [...hashes].sort()) console.log(`      ${hash}  ${rel}`);
