/**
 * Write assets/js/data.js from content.json.
 *
 *   cd website && npm run data
 *
 * The rendering itself lives in render-data.mjs, which imports nothing — it
 * has to run inside a Cloudflare Pages Function too, where `node:fs` does not
 * exist. This file is the part that touches the disk, and nothing else.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "./render-data.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const IN = resolve(ROOT, "content.json");
export const OUT = resolve(ROOT, "assets/js/data.js");

const content = JSON.parse(readFileSync(IN, "utf8"));
writeFileSync(OUT, render(content));

const units = content.projects.reduce((n, p) => n + p.units.length, 0);
console.log(`  ✓ ${content.projects.length} projects, ${units} units → assets/js/data.js`);
