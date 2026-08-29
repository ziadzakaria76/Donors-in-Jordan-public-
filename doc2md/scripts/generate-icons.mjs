#!/usr/bin/env node
/**
 * Generates the PWA icon set from code, so the repo carries no binary assets
 * that nobody can regenerate. Rasterises a simple mark (a page with a corner
 * fold and a download arrow) and writes it out as PNG using only zlib.
 *
 *   node scripts/generate-icons.mjs
 */
import { deflateSync } from 'node:zlib';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'icons');

const BRAND = [0x4f, 0x46, 0xe5]; // indigo-600
const BRAND_DEEP = [0x31, 0x2b, 0xa8];
const PAPER = [0xff, 0xff, 0xff];

// ---------------------------------------------------------------- PNG writer

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/** @param {Uint8Array} rgba packed RGBA, size*size*4 */
function encodePng(rgba, size) {
  const stride = size * 4;
  const raw = Buffer.alloc((stride + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (stride + 1)] = 0; // filter: none
    Buffer.from(rgba.buffer, rgba.byteOffset + y * stride, stride).copy(
      raw,
      y * (stride + 1) + 1,
    );
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // colour type: RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// ------------------------------------------------------------------ geometry
// All shapes are described in a normalised 0..1 box and sampled with 3x3
// supersampling, which is enough antialiasing at these sizes.

const inRoundRect = (x, y, x0, y0, x1, y1, r) => {
  if (x < x0 || x > x1 || y < y0 || y > y1) return false;
  const cx = Math.min(Math.max(x, x0 + r), x1 - r);
  const cy = Math.min(Math.max(y, y0 + r), y1 - r);
  const dx = x - cx;
  const dy = y - cy;
  return dx * dx + dy * dy <= r * r;
};

const inTriangle = (x, y, [ax, ay], [bx, by], [cx, cy]) => {
  const d = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay);
  const s = ((bx - ax) * (y - ay) - (x - ax) * (by - ay)) / d;
  const t = ((x - ax) * (cy - ay) - (cx - ax) * (y - ay)) / d;
  return s >= 0 && t >= 0 && s + t <= 1;
};

/** Colour of the mark at normalised (x, y), or null for transparent. */
function markAt(x, y) {
  // Page body: rounded rect with the top-right corner sliced off.
  const cut = 0.2;
  const page = inRoundRect(x, y, 0.2, 0.11, 0.8, 0.89, 0.05);
  const corner = inTriangle(x, y, [0.8 - cut, 0.11], [0.8, 0.11], [0.8, 0.11 + cut]);
  // The folded flap, a shade darker so the corner reads as a fold rather than
  // a bite taken out of the page. Drawn before the body so it wins.
  if (page && inTriangle(x, y, [0.8 - cut, 0.11], [0.8, 0.11 + cut], [0.8 - cut, 0.11 + cut])) {
    return [0xc7, 0xd2, 0xfe];
  }
  if (page && !corner) {
    // Download arrow punched out of the page in the deep brand tone.
    const stem = x >= 0.455 && x <= 0.545 && y >= 0.3 && y <= 0.6;
    const head = inTriangle(x, y, [0.35, 0.56], [0.65, 0.56], [0.5, 0.75]);
    if (stem || head) return BRAND_DEEP;
    return PAPER;
  }
  return null;
}

/**
 * @param {number} size
 * @param {'any'|'maskable'} purpose  maskable icons must survive a circular
 *   crop, so the background bleeds to the edges and the mark shrinks into the
 *   80% safe zone.
 */
function render(size, purpose) {
  const rgba = new Uint8Array(size * size * 4);
  const ss = 3;
  const inset = purpose === 'maskable' ? 0.2 : 0;
  const scale = 1 - inset * 2;

  for (let py = 0; py < size; py++) {
    for (let px = 0; px < size; px++) {
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      for (let sy = 0; sy < ss; sy++) {
        for (let sx = 0; sx < ss; sx++) {
          const u = (px + (sx + 0.5) / ss) / size;
          const v = (py + (sy + 0.5) / ss) / size;

          // Background plate.
          const onPlate =
            purpose === 'maskable' ? true : inRoundRect(u, v, 0, 0, 1, 1, 0.22);
          if (!onPlate) continue;

          // Subtle diagonal gradient so the plate is not flat.
          const t = Math.min(1, Math.max(0, (u + v) / 2));
          let col = [
            Math.round(BRAND[0] + (BRAND_DEEP[0] - BRAND[0]) * t),
            Math.round(BRAND[1] + (BRAND_DEEP[1] - BRAND[1]) * t),
            Math.round(BRAND[2] + (BRAND_DEEP[2] - BRAND[2]) * t),
          ];
          const mark = markAt((u - inset) / scale, (v - inset) / scale);
          if (mark) col = mark;

          r += col[0];
          g += col[1];
          b += col[2];
          a += 255;
        }
      }
      const n = ss * ss;
      const i = (py * size + px) * 4;
      // Un-premultiply: the accumulated colour only covered `a/255` samples.
      const cov = a / 255;
      if (cov > 0) {
        rgba[i] = Math.round(r / cov);
        rgba[i + 1] = Math.round(g / cov);
        rgba[i + 2] = Math.round(b / cov);
        rgba[i + 3] = Math.round(a / n);
      }
    }
  }
  return encodePng(rgba, size);
}

const SVG_FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#4f46e5"/><stop offset="1" stop-color="#312ba8"/>
  </linearGradient></defs>
  <rect width="100" height="100" rx="22" fill="url(#g)"/>
  <path d="M20 16h40l20 20v48a5 5 0 0 1-5 5H25a5 5 0 0 1-5-5V21a5 5 0 0 1 5-5z" fill="#fff"/>
  <path d="M60 16l20 20H60z" fill="#c7d2fe"/>
  <path d="M45.5 30h9v26h9L50 75 35.5 56h10z" fill="#312ba8"/>
</svg>
`;

mkdirSync(OUT_DIR, { recursive: true });
const written = [];
for (const [name, size, purpose] of [
  ['icon-192.png', 192, 'any'],
  ['icon-512.png', 512, 'any'],
  ['maskable-512.png', 512, 'maskable'],
  ['apple-touch-icon.png', 180, 'maskable'],
]) {
  const png = render(size, purpose);
  writeFileSync(join(OUT_DIR, name), png);
  written.push(`${name} (${(png.length / 1024).toFixed(1)} KB)`);
}
writeFileSync(join(OUT_DIR, 'favicon.svg'), SVG_FAVICON);
written.push('favicon.svg');
console.log(`icons → public/icons: ${written.join(', ')}`);
