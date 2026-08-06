/**
 * Image generator for the General Sherman site.
 *
 * The site ships with every image already rendered into assets/img, so you do
 * NOT need to run this to use the site. Run it only if you want to change the
 * generated artwork (palettes, massing, framing):
 *
 *   cd website && npm install && npm run assets
 *
 * Each scene is written as an .svg source (editable) and rasterised to .webp at
 * several widths for responsive srcsets.
 */
import sharp from "sharp";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const IMG = resolve(ROOT, "assets/img");
const WIDTHS = [1920, 1280, 800, 480];

/* ---------------------------------------------------------------- helpers */

/** Deterministic PRNG so re-running produces byte-identical artwork. */
function rng(seed) {
  let s = 0;
  for (const ch of String(seed)) s = (s * 31 + ch.charCodeAt(0)) >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];
const between = (r, a, b) => a + r() * (b - a);

/**
 * Every exterior is lit from the front-left, so each mass gets three tones:
 * `front` (sunlit), `side` (in shade), `roof` (sky-lit). Keeping one light
 * direction across all scenes is what makes the set read as one campaign.
 */
const PALETTES = {
  dusk: {
    sky: ["#0C161E", "#1B2C38", "#40525A", "#8A7A6A", "#D9A265"],
    sun: "#FFCF92", glow: "#E9AE6C",
    front: "#3A4750", side: "#222D35", roof: "#4A5760",
    lit: "#FFD79B", litRate: 0.45, glass: ["#1E2C35", "#3E525E"],
    ground: "#1A232A", haze: "#5A6B73", grain: 0.12,
  },
  dawn: {
    sky: ["#7E9AAE", "#A9BEC8", "#D3D9D5", "#EBE0CD", "#F6E4C6"],
    sun: "#FFF3DC", glow: "#F2DEBC",
    front: "#DDD5C6", side: "#A79E90", roof: "#EAE3D6",
    lit: "#FDF5E6", litRate: 0.1, glass: ["#8FA6B2", "#C3CFD2"],
    ground: "#B9B3A5", haze: "#CFD6D4", grain: 0.1,
  },
  golden: {
    sky: ["#2F4759", "#5D7180", "#A38F7D", "#D9A96F", "#F4CE96"],
    sun: "#FFE3B4", glow: "#F0BC7C",
    front: "#C7A379", side: "#6B5844", roof: "#D8BA92",
    lit: "#FFE2B0", litRate: 0.26, glass: ["#3A4A52", "#7C8E92"],
    ground: "#4A3E31", haze: "#B99A76", grain: 0.12,
  },
  night: {
    sky: ["#050A0F", "#0B141C", "#152029", "#1F2E39", "#2C3F4B"],
    sun: "#9FC0D4", glow: "#33505F",
    front: "#222E37", side: "#141D24", roof: "#2A3841",
    lit: "#FFD08F", litRate: 0.58, glass: ["#101A21", "#22333E"],
    ground: "#0B1116", haze: "#1E2C36", grain: 0.14,
  },
  overcast: {
    sky: ["#8E9CA5", "#AFBBC0", "#CBD2D1", "#DFE1DA", "#EDE9E0"],
    sun: "#F8F4EC", glow: "#E6E6DE",
    front: "#CDC7BB", side: "#948E84", roof: "#DAD5C9",
    lit: "#F8F2E6", litRate: 0.08, glass: ["#7C8B92", "#AFBBBE"],
    ground: "#A6A29A", haze: "#C6CCCB", grain: 0.1,
  },
};

/**
 * A ground plane in one-point perspective, shared by the interior and the
 * courtyard. Positions are given as (u across, t into depth); `solid` extrudes
 * a footprint upward using the plane's own vertical scale at that depth, which
 * is what keeps near objects large and far objects small.
 */
function groundPlane(W, H, { farY, farX0, farX1, ceilY = 0 }) {
  const lerp = (a, b, k) => a + (b - a) * k;
  const vScale = (t) => lerp(H - ceilY, farY - ceilY, t);
  const fp = (u, t) => [lerp(lerp(0, W, u), lerp(farX0, farX1, u), t), lerp(H, farY, t)];
  const up = ([x, y], v, t) => [x, y - v * vScale(t)];

  const solid = (u0, u1, t0, t1, hgt, fill, top, opts = {}) => {
    const A = fp(u0, t0), B = fp(u1, t0), C = fp(u1, t1), D = fp(u0, t1);
    const At = up(A, hgt, t0), Bt = up(B, hgt, t0), Ct = up(C, hgt, t1), Dt = up(D, hgt, t1);
    const shadow = opts.shadow === false ? "" :
      `<ellipse cx="${n((A[0] + C[0]) / 2)}" cy="${n((A[1] + D[1]) / 2)}" rx="${n(Math.abs(B[0] - A[0]) * 0.62)}" ry="${n(Math.abs(A[1] - D[1]) * 0.45 + 10)}" fill="#000" opacity="0.2" filter="url(#soft)"/>`;
    return `<g>${shadow}
      <polygon points="${n(Dt[0])},${n(Dt[1])} ${n(Ct[0])},${n(Ct[1])} ${n(Bt[0])},${n(Bt[1])} ${n(At[0])},${n(At[1])}" fill="${top || fill}"/>
      <polygon points="${n(Bt[0])},${n(Bt[1])} ${n(Ct[0])},${n(Ct[1])} ${n(C[0])},${n(C[1])} ${n(B[0])},${n(B[1])}" fill="${fill}" opacity="0.7"/>
      <polygon points="${n(At[0])},${n(At[1])} ${n(Bt[0])},${n(Bt[1])} ${n(B[0])},${n(B[1])} ${n(A[0])},${n(A[1])}" fill="${fill}"/>
    </g>`;
  };
  const quad = (u0, u1, t0, t1, fill, extra = "") => {
    const A = fp(u0, t0), B = fp(u1, t0), C = fp(u1, t1), D = fp(u0, t1);
    return `<polygon points="${n(A[0])},${n(A[1])} ${n(B[0])},${n(B[1])} ${n(C[0])},${n(C[1])} ${n(D[0])},${n(D[1])}" fill="${fill}" ${extra}/>`;
  };
  return { fp, up, solid, quad, vScale };
}

const grainDef = (id, freq = 0.85, oct = 3) => `
    <filter id="${id}" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="${oct}" seed="7"/>
      <feColorMatrix type="saturate" values="0"/>
    </filter>`;

const blurDef = (id, dev) => `<filter id="${id}" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="${dev}"/></filter>`;

const skyDef = (id, p) => `
    <linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      ${p.sky.map((c, i) => `<stop offset="${(i / (p.sky.length - 1)).toFixed(3)}" stop-color="${c}"/>`).join("")}
    </linearGradient>`;

const n = (v) => Number(v).toFixed(1);

/**
 * One building mass drawn in parallel projection: sunlit front, shaded return
 * face, sky-lit roof. Windows run as horizontal ribbons with slab bands
 * between them, which is what actually distinguishes a residential tower from
 * a grid of squares.
 */
function box(r, o) {
  const { x, y, w, h, p, floors, opacity = 1, tint = 0, balcony = true } = o;
  const dx = o.dx ?? w * 0.22;
  const dy = o.dy ?? -w * 0.1;
  const fh = h / floors;
  const g = [];

  // Return face + roof first, so the front face sits on top of their seams.
  g.push(`<polygon points="${n(x + w)},${n(y)} ${n(x + w + dx)},${n(y + dy)} ${n(x + w + dx)},${n(y + h + dy)} ${n(x + w)},${n(y + h)}" fill="${p.side}"/>`);
  g.push(`<polygon points="${n(x)},${n(y)} ${n(x + dx)},${n(y + dy)} ${n(x + w + dx)},${n(y + dy)} ${n(x + w)},${n(y)}" fill="${p.roof}"/>`);
  g.push(`<rect x="${n(x)}" y="${n(y)}" width="${n(w)}" height="${n(h)}" fill="${p.front}"/>`);

  const inset = Math.min(w * 0.05, 10);
  const bandH = fh * 0.52;
  for (let f = 0; f < floors; f++) {
    const yy = y + f * fh + fh * 0.24;
    if (bandH < 1.2) continue;
    // Glazing ribbon on the sunlit face
    g.push(`<rect x="${n(x + inset)}" y="${n(yy)}" width="${n(w - inset * 2)}" height="${n(bandH)}" fill="url(#glass)"/>`);
    const bays = Math.max(2, Math.round(w / 42));
    const bw = (w - inset * 2) / bays;
    for (let b = 0; b < bays; b++) {
      if (r() < p.litRate) {
        g.push(`<rect x="${n(x + inset + b * bw + 1)}" y="${n(yy)}" width="${n(bw - 2)}" height="${n(bandH)}" fill="${p.lit}" opacity="${between(r, 0.4, 0.9).toFixed(2)}"/>`);
      }
      g.push(`<rect x="${n(x + inset + b * bw)}" y="${n(yy)}" width="1.5" height="${n(bandH)}" fill="${p.side}" opacity="0.7"/>`);
    }
    // Ribbon continuing round the corner, sheared along the depth vector
    const sy = yy;
    g.push(`<polygon points="${n(x + w)},${n(sy)} ${n(x + w + dx * 0.92)},${n(sy + dy * 0.92)} ${n(x + w + dx * 0.92)},${n(sy + dy * 0.92 + bandH)} ${n(x + w)},${n(sy + bandH)}" fill="${p.glass[0]}" opacity="0.85"/>`);
    if (balcony) {
      // Slab edge reads as the balcony line and catches the light.
      g.push(`<rect x="${n(x - w * 0.015)}" y="${n(yy + bandH)}" width="${n(w * 1.03)}" height="${n(Math.max(1.5, fh * 0.07))}" fill="${p.roof}"/>`);
      g.push(`<rect x="${n(x - w * 0.015)}" y="${n(yy + bandH + Math.max(1.5, fh * 0.07))}" width="${n(w * 1.03)}" height="${n(Math.max(1, fh * 0.05))}" fill="#000" opacity="0.22"/>`);
    }
  }

  // Vertical circulation core: a solid stone bay breaking the glazing rhythm.
  const coreW = Math.max(8, w * 0.13);
  const coreX = x + w * (o.coreAt ?? 0.68);
  g.push(`<rect x="${n(coreX)}" y="${n(y)}" width="${n(coreW)}" height="${n(h)}" fill="${p.roof}"/>`);
  g.push(`<rect x="${n(coreX)}" y="${n(y)}" width="2" height="${n(h)}" fill="#000" opacity="0.15"/>`);

  // Rim light on the sunlit corner + parapet
  g.push(`<rect x="${n(x)}" y="${n(y)}" width="1.6" height="${n(h)}" fill="${p.sun}" opacity="0.55"/>`);
  g.push(`<rect x="${n(x)}" y="${n(y - 2)}" width="${n(w)}" height="3" fill="${p.sun}" opacity="0.4"/>`);

  if (tint) g.push(`<rect x="${n(x)}" y="${n(y + dy)}" width="${n(w + dx)}" height="${n(h - dy)}" fill="${p.haze}" opacity="${tint}"/>`);
  return `<g opacity="${opacity}">${g.join("")}</g>`;
}

/* ----------------------------------------------------------------- scenes */

/** A slender cypress — the tree that actually lines Amman's hillside plots. */
function cypress(x, y, h, fill, opacity = 1) {
  return `<g opacity="${opacity}"><rect x="${n(x - h * 0.012)}" y="${n(y - h * 0.12)}" width="${n(h * 0.024)}" height="${n(h * 0.12)}" fill="${fill}"/>
    <path d="M ${n(x)} ${n(y - h)} C ${n(x + h * 0.15)} ${n(y - h * 0.6)}, ${n(x + h * 0.11)} ${n(y - h * 0.15)}, ${n(x)} ${n(y - h * 0.08)}
      C ${n(x - h * 0.11)} ${n(y - h * 0.15)}, ${n(x - h * 0.15)} ${n(y - h * 0.6)}, ${n(x)} ${n(y - h)} Z" fill="${fill}"/></g>`;
}

/** Wide exterior: layered massing, atmospheric depth, landscaped foreground. */
function skyline(seed, paletteName, opts = {}) {
  const r = rng(seed);
  const p = PALETTES[paletteName];
  const W = 1920, H = 1080;
  const horizon = H * (opts.horizon ?? 0.8);
  const sunX = W * (opts.sunX ?? 0.68);
  const sunY = horizon - H * 0.1;
  const g = [];

  // Sky is confined to the area above the horizon so the warm band lands on it.
  g.push(`<rect width="${W}" height="${n(horizon)}" fill="url(#sky)"/>`);
  g.push(`<ellipse cx="${n(sunX)}" cy="${n(sunY)}" rx="${n(W * 0.34)}" ry="${n(H * 0.28)}" fill="${p.glow}" opacity="0.55" filter="url(#soft)"/>`);
  g.push(`<circle cx="${n(sunX)}" cy="${n(sunY)}" r="${n(H * 0.045)}" fill="${p.sun}" opacity="0.9" filter="url(#soft2)"/>`);
  // Thin cloud banding keeps the sky from looking like a flat gradient.
  for (let i = 0; i < 5; i++) {
    const cy = between(r, H * 0.1, horizon - H * 0.12);
    g.push(`<ellipse cx="${n(between(r, 0, W))}" cy="${n(cy)}" rx="${n(between(r, 220, 520))}" ry="${n(between(r, 6, 16))}" fill="${p.sun}" opacity="${between(r, 0.06, 0.16).toFixed(2)}" filter="url(#soft)"/>`);
  }

  // Hills — Amman is built across them, so they set the place before the buildings do.
  for (let layer = 0; layer < 3; layer++) {
    const base = horizon - H * 0.14 + layer * H * 0.05;
    const pts = [`0,${n(horizon)}`];
    for (let x = 0; x <= W; x += 80) {
      const k = x / W;
      pts.push(`${x},${n(base - Math.sin(k * (2.4 + layer * 1.7) + layer) * H * (0.045 - layer * 0.01) - r() * 8)}`);
    }
    pts.push(`${W},${n(horizon)}`);
    g.push(`<polygon points="${pts.join(" ")}" fill="${p.haze}" opacity="${(0.5 - layer * 0.12).toFixed(2)}"/>`);
    // Hillside houses, tiny and stacked
    for (let i = 0; i < 26 - layer * 6; i++) {
      const hx = between(r, 0, W), hw = between(r, 14, 30), hh = between(r, 8, 18);
      const hy = base - Math.sin((hx / W) * (2.4 + layer * 1.7) + layer) * H * (0.045 - layer * 0.01);
      g.push(`<rect x="${n(hx)}" y="${n(hy - hh)}" width="${n(hw)}" height="${n(hh)}" fill="${p.side}" opacity="${(0.35 - layer * 0.08).toFixed(2)}"/>`);
    }
  }

  // Depth layer 1 — background blocks, heavily hazed
  for (let i = 0; i < 12; i++) {
    const w = between(r, 90, 170), h = between(r, 140, 300);
    g.push(box(r, {
      x: i * (W / 12) - 30, y: horizon - h, w, h, p,
      floors: Math.max(4, Math.round(h / 34)), opacity: 0.75, tint: 0.45, balcony: false,
      dx: w * 0.16, dy: -w * 0.07, coreAt: between(r, 0.3, 0.8),
    }));
  }
  g.push(`<rect x="0" y="${n(horizon - H * 0.3)}" width="${W}" height="${n(H * 0.32)}" fill="${p.haze}" opacity="0.3" filter="url(#soft)"/>`);

  // Depth layer 2 — neighbouring buildings
  const midCount = opts.midCount ?? 5;
  for (let i = 0; i < midCount; i++) {
    const w = between(r, 170, 250), h = between(r, 200, 330);
    g.push(box(r, {
      x: 30 + i * (W / midCount) + between(r, -40, 40), y: horizon - h, w, h, p,
      floors: Math.max(5, Math.round(h / 42)), opacity: 0.95, tint: 0.16,
      coreAt: between(r, 0.25, 0.8),
    }));
  }

  // Hero mass — stepped terraces, the signature of the flagship building.
  const hx = W * (opts.heroX ?? 0.28);
  const hw = W * (opts.heroW ?? 0.3);
  const hh = H * (opts.heroH ?? 0.5);
  // Drawn tallest-first so the lower, wider terraces overlap in front of it.
  const tiers = opts.tiers ?? 3;
  for (let t = tiers - 1; t >= 0; t--) {
    const tw = hw * (1 - t * 0.26);
    const th = hh * (1 + t * 0.2);
    const tx = opts.stepBack === "start" ? hx + t * hw * 0.26 : hx + (t * hw * 0.26) / 2;
    g.push(box(r, {
      x: tx, y: horizon - th, w: tw, h: th, p,
      floors: Math.max(6, Math.round(th / 44)),
      dx: tw * 0.2, dy: -tw * 0.09, coreAt: t === 0 ? 0.72 : 0.3,
    }));
  }
  // Double-height lobby glow anchoring the tower to the street
  g.push(`<rect x="${n(hx)}" y="${n(horizon - H * 0.05)}" width="${n(hw)}" height="${n(H * 0.05)}" fill="${p.lit}" opacity="0.65"/>`);
  g.push(`<ellipse cx="${n(hx + hw / 2)}" cy="${n(horizon)}" rx="${n(hw * 0.7)}" ry="${n(H * 0.07)}" fill="${p.lit}" opacity="0.22" filter="url(#soft)"/>`);

  // Ground plane, cast shadows raking away from the sun, wet-stone sheen
  g.push(`<rect x="0" y="${n(horizon)}" width="${W}" height="${n(H - horizon)}" fill="${p.ground}"/>`);
  g.push(`<rect x="0" y="${n(horizon)}" width="${W}" height="${n(H - horizon)}" fill="url(#floorSheen)"/>`);
  const shadowDir = sunX > W / 2 ? -1 : 1;
  g.push(`<polygon points="${n(hx)},${n(horizon)} ${n(hx + hw)},${n(horizon)} ${n(hx + hw + shadowDir * hw * 0.5)},${H} ${n(hx + shadowDir * hw * 0.7)},${H}" fill="#000" opacity="0.22" filter="url(#soft)"/>`);

  const treeFill = paletteName === "dawn" || paletteName === "overcast" ? "#5E6A5A" : "#1A231F";
  for (let i = 0; i < 9; i++) {
    const tx = between(r, -20, W), ty = horizon + between(r, 6, (H - horizon) * 0.8);
    g.push(cypress(tx, ty, between(r, 90, 210) * (0.7 + (ty - horizon) / (H - horizon)), treeFill, 0.92));
  }
  // Low planter wall in the immediate foreground for depth
  g.push(`<rect x="0" y="${n(H - 70)}" width="${W}" height="70" fill="${p.ground}"/>`);
  g.push(`<rect x="0" y="${n(H - 74)}" width="${W}" height="5" fill="${p.roof}" opacity="0.5"/>`);
  g.push(`<rect width="${W}" height="${H}" fill="url(#vig)"/>`);

  return wrap(W, H, `${skyDef("sky", p)}${blurDef("soft", 44)}${blurDef("soft2", 16)}
    <linearGradient id="glass" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0" stop-color="${p.glass[1]}"/><stop offset="1" stop-color="${p.glass[0]}"/></linearGradient>
    <linearGradient id="floorSheen" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${p.glow}" stop-opacity="0.28"/><stop offset="1" stop-color="#000" stop-opacity="0.25"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.45" r="0.8">
      <stop offset="0.55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.35"/></radialGradient>
    ${grainDef("grain", 0.9)}`, g.join(""), p);
}

/** Tight crop of a facade module — stone, glass, balcony, hard shadow. */
function facade(seed, paletteName, opts = {}) {
  const r = rng(seed);
  const p = PALETTES[paletteName];
  const W = 1920, H = 1080;
  const g = [];
  const stone = opts.stone ?? "#D9D1C2";
  const shade = opts.shade ?? "#A79E8D";
  const glass = opts.glass ?? ["#2E3F49", "#6E8894"];

  g.push(`<rect width="${W}" height="${H}" fill="${stone}"/>`);
  const cols = opts.cols ?? 4;
  const rows = opts.rows ?? 3;
  const cw = W / cols, ch = H / rows;

  for (let c = 0; c < cols; c++) {
    for (let row = 0; row < rows; row++) {
      const x = c * cw, y = row * ch;
      g.push(`<rect x="${x}" y="${y}" width="${cw}" height="${ch}" fill="${row % 2 ? shade : stone}" opacity="${0.5 + r() * 0.2}"/>`);
      // Recessed opening
      const ox = x + cw * 0.14, oy = y + ch * 0.16, ow = cw * 0.72, oh = ch * 0.62;
      g.push(`<rect x="${ox}" y="${oy}" width="${ow}" height="${oh}" fill="#0F171C" opacity="0.9"/>`);
      g.push(`<rect x="${ox + ow * 0.06}" y="${oy + oh * 0.08}" width="${ow * 0.88}" height="${oh * 0.84}" fill="url(#gl)"/>`);
      // Mullions
      for (let m = 1; m < 3; m++) {
        g.push(`<rect x="${ox + (ow / 3) * m}" y="${oy}" width="4" height="${oh}" fill="${shade}" opacity="0.85"/>`);
      }
      // Balcony slab + railing
      g.push(`<rect x="${x + cw * 0.06}" y="${oy + oh}" width="${cw * 0.88}" height="${ch * 0.06}" fill="${stone}"/>`);
      g.push(`<rect x="${x + cw * 0.06}" y="${oy + oh + ch * 0.06}" width="${cw * 0.88}" height="${ch * 0.03}" fill="#000" opacity="0.25"/>`);
      for (let b = 0; b < 14; b++) {
        g.push(`<rect x="${(x + cw * 0.08 + b * (cw * 0.84) / 14).toFixed(1)}" y="${(oy + oh - ch * 0.16).toFixed(1)}" width="2" height="${(ch * 0.16).toFixed(1)}" fill="${shade}" opacity="0.9"/>`);
      }
    }
  }
  // Raking light across the elevation
  g.push(`<rect width="${W}" height="${H}" fill="url(#rake)"/>`);
  return wrap(W, H, `
    <linearGradient id="gl" x1="0" y1="0" x2="0.4" y2="1">
      <stop offset="0" stop-color="${glass[0]}"/><stop offset="1" stop-color="${glass[1]}"/></linearGradient>
    <linearGradient id="rake" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${p.sun}" stop-opacity="0.34"/>
      <stop offset="0.55" stop-color="${p.sun}" stop-opacity="0.04"/>
      <stop offset="1" stop-color="#0D1418" stop-opacity="0.30"/></linearGradient>
    ${grainDef("grain", 0.8)}`, g.join(""), p);
}

/**
 * Interior in one-point perspective. Everything is placed in room coordinates
 * — u across, t into the depth, v up — and projected, so furniture, the rug and
 * the light spill all sit on the same floor plane instead of floating.
 */
function interior(seed, opts = {}) {
  const r = rng(seed);
  const W = 1920, H = 1080;
  const wall = opts.wall ?? "#EAE4D8";
  const wallShade = opts.wallShade ?? "#CFC7B8";
  const floorCol = opts.floor ?? "#8A6E51";
  const accent = opts.accent ?? "#B08D4F";
  const g = [];

  // Back wall opening (the room's far end), and the picture-plane frame.
  const bx0 = W * (opts.backX ?? 0.2), bx1 = W * (opts.backX ?? 0.2) + W * (opts.backW ?? 0.6);
  const by0 = H * 0.24, by1 = H * 0.7;
  const { fp, solid } = groundPlane(W, H, { farY: by1, farX0: bx0, farX1: bx1, ceilY: by0 - H * 0.24 });

  g.push(`<rect width="${W}" height="${H}" fill="${wall}"/>`);
  // Side walls and ceiling as converging planes
  g.push(`<polygon points="0,0 ${n(bx0)},${n(by0)} ${n(bx0)},${n(by1)} 0,${H}" fill="${wallShade}"/>`);
  g.push(`<polygon points="${W},0 ${n(bx1)},${n(by0)} ${n(bx1)},${n(by1)} ${W},${H}" fill="${wallShade}" opacity="0.72"/>`);
  g.push(`<polygon points="0,0 ${W},0 ${n(bx1)},${n(by0)} ${n(bx0)},${n(by0)}" fill="${wall}"/>`);
  g.push(`<polygon points="0,0 ${W},0 ${n(bx1)},${n(by0)} ${n(bx0)},${n(by0)}" fill="#000" opacity="0.1"/>`);
  // Floor
  g.push(`<polygon points="0,${H} ${W},${H} ${n(bx1)},${n(by1)} ${n(bx0)},${n(by1)}" fill="${floorCol}"/>`);
  g.push(`<polygon points="0,${H} ${W},${H} ${n(bx1)},${n(by1)} ${n(bx0)},${n(by1)}" fill="url(#floorG)"/>`);
  for (let i = 1; i < 14; i++) {
    const [ax, ay] = fp(i / 14, 0), [bx, by] = fp(i / 14, 1);
    g.push(`<line x1="${n(ax)}" y1="${n(ay)}" x2="${n(bx)}" y2="${n(by)}" stroke="#000" stroke-opacity="0.09" stroke-width="2"/>`);
  }

  // Back wall: full-height glazing onto the city
  g.push(`<rect x="${n(bx0)}" y="${n(by0)}" width="${n(bx1 - bx0)}" height="${n(by1 - by0)}" fill="${wall}"/>`);
  const gx0 = bx0 + (bx1 - bx0) * 0.06, gx1 = bx1 - (bx1 - bx0) * 0.06;
  const gy0 = by0 + (by1 - by0) * 0.08, gy1 = by1 - (by1 - by0) * 0.04;
  g.push(`<rect x="${n(gx0)}" y="${n(gy0)}" width="${n(gx1 - gx0)}" height="${n(gy1 - gy0)}" fill="url(#viewG)"/>`);
  for (let i = 0; i < 9; i++) {
    const bw = (gx1 - gx0) / 9, bh = between(r, 26, 82);
    g.push(`<rect x="${n(gx0 + i * bw)}" y="${n(gy1 - bh - (gy1 - gy0) * 0.06)}" width="${n(bw * 0.82)}" height="${n(bh)}" fill="#8C9AA2" opacity="0.45"/>`);
  }
  for (let m = 1; m < 4; m++) {
    g.push(`<rect x="${n(gx0 + ((gx1 - gx0) / 4) * m - 3)}" y="${n(gy0)}" width="6" height="${n(gy1 - gy0)}" fill="${wall}"/>`);
  }
  g.push(`<rect x="${n(gx0)}" y="${n(gy0)}" width="${n(gx1 - gx0)}" height="6" fill="${wall}"/>`);

  // Sheer curtain panels at the reveals
  for (const [c0, c1] of [[0.0, 0.1], [0.9, 1.0]]) {
    const cx0 = bx0 + (bx1 - bx0) * c0, cx1 = bx0 + (bx1 - bx0) * c1;
    g.push(`<rect x="${n(cx0)}" y="${n(by0 + (by1 - by0) * 0.04)}" width="${n(cx1 - cx0)}" height="${n((by1 - by0) * 0.96)}" fill="#F4EFE4" opacity="0.85"/>`);
    for (let i = 0; i < 5; i++) {
      g.push(`<rect x="${n(cx0 + ((cx1 - cx0) / 5) * i)}" y="${n(by0 + (by1 - by0) * 0.04)}" width="2" height="${n((by1 - by0) * 0.96)}" fill="#C9C0AE" opacity="0.5"/>`);
    }
  }

  // Framed work on the left wall, projected onto that plane
  const wallQuad = (t0, t1, v0, v1, fill, extra = "") => {
    const lerp2 = (a, b, k) => a + (b - a) * k;
    const px0 = lerp2(0, bx0, t0), px1 = lerp2(0, bx0, t1);
    const yA = (t, v) => lerp2(lerp2(H, by1, t), lerp2(0, by0, t), v);
    return `<polygon points="${n(px0)},${n(yA(t0, v0))} ${n(px1)},${n(yA(t1, v0))} ${n(px1)},${n(yA(t1, v1))} ${n(px0)},${n(yA(t0, v1))}" fill="${fill}" ${extra}/>`;
  };
  g.push(wallQuad(0.3, 0.66, 0.4, 0.72, "#000", 'opacity="0.1"'));
  g.push(wallQuad(0.32, 0.64, 0.42, 0.7, "#D8CFBD"));
  g.push(wallQuad(0.36, 0.6, 0.46, 0.66, accent, 'opacity="0.55"'));

  // Daylight spilling out of the opening onto the floor
  const [s0x, s0y] = fp(0.06, 1), [s1x, s1y] = fp(0.94, 1);
  const [s2x, s2y] = fp(1.25, 0), [s3x, s3y] = fp(-0.25, 0);
  g.push(`<polygon points="${n(s0x)},${n(s0y)} ${n(s1x)},${n(s1y)} ${n(s2x)},${n(s2y)} ${n(s3x)},${n(s3y)}" fill="#FFF1D6" opacity="0.26" filter="url(#soft)"/>`);

  // Furnished back-to-front: console at the window, then table, then the sofa
  // with its back to us, which is how these rooms are actually photographed.
  const [r0x, r0y] = fp(0.06, 0.26), [r1x, r1y] = fp(0.74, 0.26), [r2x, r2y] = fp(0.7, 0.78), [r3x, r3y] = fp(0.12, 0.78);
  g.push(`<polygon points="${n(r0x)},${n(r0y)} ${n(r1x)},${n(r1y)} ${n(r2x)},${n(r2y)} ${n(r3x)},${n(r3y)}" fill="#CFC4AE" opacity="0.6"/>`);
  g.push(solid(0.78, 0.97, 0.62, 0.7, 0.1, "#54402C", "#654E36"));
  g.push(solid(0.3, 0.54, 0.56, 0.7, 0.05, accent, "#CDAA6B"));
  g.push(solid(0.14, 0.62, 0.3, 0.56, 0.06, "#39424A", "#4A555D"));   // seat
  g.push(solid(0.12, 0.2, 0.3, 0.56, 0.11, "#333C43", "#404A52"));    // left arm
  g.push(solid(0.56, 0.64, 0.3, 0.56, 0.11, "#333C43", "#404A52"));   // right arm
  g.push(solid(0.12, 0.64, 0.3, 0.35, 0.13, "#2E373E", "#3B454C"));   // back
  // Cushions break the slab of upholstery
  g.push(solid(0.18, 0.3, 0.34, 0.4, 0.09, "#4B565E", "#5A666E"));
  g.push(solid(0.46, 0.58, 0.34, 0.4, 0.09, "#4B565E", "#5A666E"));

  // Planter, scaled to its depth so it belongs to the room
  const pt = 0.46;
  const [px, py] = fp(0.9, pt);
  const pk = (0.4 + (1 - pt) * 0.6).toFixed(3);
  g.push(`<g transform="translate(${n(px)} ${n(py)}) scale(${pk})">
    <ellipse cx="0" cy="6" rx="48" ry="15" fill="#000" opacity="0.2" filter="url(#soft)"/>
    <path d="M -32 0 L 32 0 L 24 -78 L -24 -78 Z" fill="#B9AE99"/>
    <g fill="#33452F"><ellipse cx="0" cy="-156" rx="18" ry="68"/>
      <ellipse cx="-42" cy="-128" rx="15" ry="54" transform="rotate(-26 -42 -128)"/>
      <ellipse cx="42" cy="-124" rx="15" ry="54" transform="rotate(24 42 -124)"/></g></g>`);

  // Pendant hung over the table
  const lx = fp(0.42, 0.62)[0];
  g.push(`<line x1="${n(lx)}" y1="0" x2="${n(lx)}" y2="${n(H * 0.22)}" stroke="#2B3238" stroke-width="3"/>
    <path d="M ${n(lx - 40)} ${n(H * 0.27)} L ${n(lx + 40)} ${n(H * 0.27)} L ${n(lx + 22)} ${n(H * 0.22)} L ${n(lx - 22)} ${n(H * 0.22)} Z" fill="#2B3238"/>
    <ellipse cx="${n(lx)}" cy="${n(H * 0.29)}" rx="58" ry="26" fill="${accent}" opacity="0.42" filter="url(#soft)"/>`);

  g.push(`<rect width="${W}" height="${H}" fill="url(#vig)"/>`);

  return wrap(W, H, `
    <linearGradient id="floorG" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0" stop-color="#000" stop-opacity="0.34"/><stop offset="1" stop-color="#FFF" stop-opacity="0.06"/></linearGradient>
    <linearGradient id="viewG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#A9C2D0"/><stop offset="0.66" stop-color="#E6E1D3"/><stop offset="1" stop-color="#D6CAB2"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.45" r="0.78">
      <stop offset="0.5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.4"/></radialGradient>
    ${blurDef("soft", 30)}${grainDef("grain", 0.9)}`, g.join(""), { grain: 0.1 });
}

/** Landscaped courtyard with a pool — the amenity shot. */
function courtyard(seed, paletteName) {
  const r = rng(seed);
  const p = PALETTES[paletteName];
  const W = 1920, H = 1080;
  const horizon = H * 0.42;
  const g = [];
  g.push(`<rect width="${W}" height="${n(horizon + 2)}" fill="url(#sky)"/>`);
  g.push(`<ellipse cx="${n(W * 0.2)}" cy="${n(horizon - H * 0.03)}" rx="${n(W * 0.26)}" ry="${n(H * 0.1)}" fill="${p.glow}" opacity="0.4" filter="url(#soft)"/>`);
  g.push(`<circle cx="${n(W * 0.2)}" cy="${n(horizon - H * 0.05)}" r="${n(H * 0.035)}" fill="${p.sun}" opacity="0.85" filter="url(#soft2)"/>`);
  for (let i = 0; i < 4; i++) {
    g.push(`<ellipse cx="${n(between(r, 0, W))}" cy="${n(between(r, H * 0.06, horizon * 0.6))}" rx="${n(between(r, 200, 460))}" ry="${n(between(r, 5, 13))}" fill="${p.sun}" opacity="${between(r, 0.06, 0.14).toFixed(2)}" filter="url(#soft)"/>`);
  }
  // Building wing framing the courtyard on the right
  g.push(box(r, {
    x: W * 0.62, y: -H * 0.08, w: W * 0.4, h: horizon + H * 0.22, p,
    floors: 7, dx: -W * 0.06, dy: -H * 0.03, coreAt: 0.1,
  }));
  // Terrace deck on a real ground plane, so the pool and furniture sit on it
  const gp = groundPlane(W, H, { farY: horizon + H * 0.06, farX0: W * 0.12, farX1: W * 0.78 });
  g.push(gp.quad(-0.4, 1.4, 0, 1, "#C2A47C"));
  g.push(gp.quad(-0.4, 1.4, 0, 1, "url(#deckG)"));
  for (let i = 1; i < 16; i++) {
    const [ax, ay] = gp.fp(-0.4 + (i / 16) * 1.8, 0), [bx, by] = gp.fp(-0.4 + (i / 16) * 1.8, 1);
    g.push(`<line x1="${n(ax)}" y1="${n(ay)}" x2="${n(bx)}" y2="${n(by)}" stroke="#000" stroke-opacity="0.07" stroke-width="2"/>`);
  }

  // Hedge and cypresses behind the far edge of the deck
  g.push(`<rect x="0" y="${n(horizon)}" width="${W}" height="${n(H * 0.075)}" fill="#3A4733"/>`);
  for (let i = 0; i < 9; i++) {
    g.push(cypress(W * 0.02 + i * W * 0.115 + between(r, -18, 18), horizon + H * 0.05, between(r, 150, 290), "#26301F", 0.92));
  }

  // Pool: coping, water, lane of reflected light off the building
  g.push(gp.quad(0.06, 0.72, 0.16, 0.78, "#D8C6A8"));
  g.push(gp.quad(0.09, 0.69, 0.2, 0.74, "url(#water)"));
  for (let i = 0; i < 12; i++) {
    const t = 0.22 + i * 0.045;
    const [ax, ay] = gp.fp(0.1, t), [bx, by] = gp.fp(0.68, t);
    g.push(`<line x1="${n(ax)}" y1="${n(ay)}" x2="${n(bx)}" y2="${n(by)}" stroke="#FFF" stroke-opacity="${(0.18 - i * 0.012).toFixed(3)}" stroke-width="${(4 - i * 0.2).toFixed(1)}"/>`);
  }
  g.push(gp.quad(0.5, 0.66, 0.2, 0.74, p.glow, 'opacity="0.3"'));

  // The right-hand wing throws a long shadow across the deck at this hour.
  g.push(gp.quad(0.72, 1.5, 0, 1, "#000", 'opacity="0.16"'));

  // Sun loungers beside the water, backrests raised
  for (let i = 0; i < 3; i++) {
    const t = 0.26 + i * 0.16;
    g.push(gp.solid(0.76, 0.9, t, t + 0.1, 0.028, "#A9967B", "#BFAC8E"));
    g.push(gp.solid(0.76, 0.9, t, t + 0.03, 0.06, "#A9967B", "#BFAC8E"));
  }
  // Planters on the near edge, cropped by the frame for depth
  for (let i = 0; i < 2; i++) {
    const u = -0.08 + i * 0.98;
    g.push(gp.solid(u, u + 0.16, -0.06, 0.06, 0.06, "#B0A48C", "#C6B99E"));
  }
  g.push(`<rect width="${W}" height="${H}" fill="url(#vig)"/>`);
  return wrap(W, H, `${skyDef("sky", p)}${blurDef("soft", 36)}${blurDef("soft2", 14)}
    <linearGradient id="glass" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0" stop-color="${p.glass[1]}"/><stop offset="1" stop-color="${p.glass[0]}"/></linearGradient>
    <linearGradient id="deckG" x1="0" y1="0" x2="0.2" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.22"/><stop offset="1" stop-color="#FFF" stop-opacity="0.10"/></linearGradient>
    <linearGradient id="water" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0" stop-color="#6FA0A6"/><stop offset="1" stop-color="#274A58"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.4" r="0.8">
      <stop offset="0.6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.3"/></radialGradient>
    ${grainDef("grain", 0.85)}`, g.join(""), p);
}

/** Unlabelled floor plan line drawing. Labels live in HTML so they translate. */
function plan(seed, rooms) {
  const W = 1200, H = 900;
  const g = [`<rect width="${W}" height="${H}" fill="#F6F3ED"/>`];
  const pad = 70;
  g.push(`<rect x="${pad}" y="${pad}" width="${W - pad * 2}" height="${H - pad * 2}" fill="#FFFDF9" stroke="#2A3238" stroke-width="10"/>`);
  for (const rm of rooms) {
    const x = pad + rm.x * (W - pad * 2), y = pad + rm.y * (H - pad * 2);
    const w = rm.w * (W - pad * 2), h = rm.h * (H - pad * 2);
    g.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${rm.wet ? "#EAF0F0" : "#FFFDF9"}" stroke="#2A3238" stroke-width="5"/>`);
    if (rm.n) {
      g.push(`<circle cx="${x + w / 2}" cy="${y + h / 2}" r="26" fill="#B08D4F"/>
        <text x="${x + w / 2}" y="${y + h / 2 + 10}" font-family="IBM Plex Sans Arabic, sans-serif" font-size="28" font-weight="600" fill="#fff" text-anchor="middle">${rm.n}</text>`);
    }
    if (rm.door) {
      g.push(`<path d="M ${x + w * 0.5} ${y + h} a 40 40 0 0 1 40 -40" fill="none" stroke="#8A9096" stroke-width="3"/>`);
    }
  }
  // North arrow
  g.push(`<g transform="translate(${W - 110} ${H - 90})" stroke="#2A3238" stroke-width="4" fill="none">
    <circle cx="0" cy="0" r="30"/><path d="M 0 -22 L 0 22 M 0 -22 L -9 -6 M 0 -22 L 9 -6" stroke-linecap="round"/></g>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img">${g.join("")}</svg>`;
}

function wrap(W, H, defs, body, p) {
  const grain = p && p.grain != null ? p.grain : 0.13;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
  <defs>${defs}</defs>
  ${body}
  <rect width="${W}" height="${H}" filter="url(#grain)" opacity="${grain}" style="mix-blend-mode:overlay"/>
</svg>`;
}

/* ------------------------------------------------------------------ build */

async function emit(name, svg, widths = WIDTHS) {
  await writeFile(resolve(IMG, `${name}.svg`), svg);
  const buf = Buffer.from(svg);
  for (const w of widths) {
    await sharp(buf, { density: 200 })
      .resize({ width: w })
      .webp({ quality: 78, effort: 6 })
      .toFile(resolve(IMG, `${name}-${w}.webp`));
  }
  console.log("  ✓", name);
}

const SCENES = [
  ["hero-home", () => skyline("home-hero-9", "dusk", { heroX: 0.26, heroW: 0.32, heroH: 0.5, tiers: 3, sunX: 0.72 })],
  ["hero-about", () => skyline("about-2", "golden", { heroX: 0.42, heroW: 0.26, heroH: 0.4, tiers: 2, sunX: 0.28, midCount: 6 })],
  ["hero-contact", () => skyline("contact-5", "night", { heroX: 0.34, heroW: 0.28, heroH: 0.44, tiers: 2, sunX: 0.5 })],
  ["project-residence76", () => skyline("res76", "dusk", { heroX: 0.3, heroW: 0.34, heroH: 0.52, tiers: 3, sunX: 0.74 })],
  ["project-crescent", () => skyline("crescent", "golden", { heroX: 0.22, heroW: 0.3, heroH: 0.46, tiers: 2, stepBack: "start", sunX: 0.8 })],
  ["project-sarw", () => skyline("sarw", "dawn", { heroX: 0.36, heroW: 0.3, heroH: 0.4, tiers: 2, sunX: 0.2, midCount: 4 })],
  ["project-alto", () => skyline("alto", "night", { heroX: 0.4, heroW: 0.22, heroH: 0.5, tiers: 1, sunX: 0.6 })],
  ["project-rabieh", () => courtyard("rabieh", "golden")],
  ["gallery-facade-1", () => facade("f1", "dusk", { cols: 4, rows: 3 })],
  ["gallery-facade-2", () => facade("f2", "golden", { cols: 3, rows: 2, stone: "#C8BCA6", shade: "#9C907C", glass: ["#243440", "#5C7683"] })],
  ["gallery-facade-3", () => facade("f3", "dawn", { cols: 5, rows: 3, stone: "#E3DCCC", shade: "#BCB4A2" })],
  ["gallery-interior-1", () => interior("i1", { winX: 0.5, winW: 0.42 })],
  ["gallery-interior-2", () => interior("i2", { wall: "#E6E2DA", floor: "#7A6248", accent: "#9C7C43", winX: 0.08, winW: 0.36 })],
  ["gallery-interior-3", () => interior("i3", { wall: "#F1ECE2", floor: "#94795C", accent: "#B08D4F", winX: 0.3, winW: 0.46 })],
  ["gallery-courtyard-1", () => courtyard("c1", "dusk")],
  ["gallery-courtyard-2", () => courtyard("c2", "dawn")],
  ["gallery-skyline-1", () => skyline("g-sky-1", "overcast", { heroX: 0.5, heroW: 0.28, heroH: 0.42, tiers: 2, sunX: 0.4 })],
  ["gallery-skyline-2", () => skyline("g-sky-2", "night", { heroX: 0.18, heroW: 0.3, heroH: 0.48, tiers: 3, sunX: 0.85 })],
];

const PLANS = {
  "plan-2br": [
    { x: 0.02, y: 0.02, w: 0.5, h: 0.46, n: 1, door: true },
    { x: 0.54, y: 0.02, w: 0.44, h: 0.28, n: 2 },
    { x: 0.54, y: 0.32, w: 0.44, h: 0.16, wet: true, n: 3 },
    { x: 0.02, y: 0.5, w: 0.36, h: 0.48, n: 4, door: true },
    { x: 0.4, y: 0.5, w: 0.32, h: 0.48, n: 5, door: true },
    { x: 0.74, y: 0.5, w: 0.24, h: 0.24, wet: true, n: 6 },
    { x: 0.74, y: 0.76, w: 0.24, h: 0.22, wet: true, n: 7 },
  ],
  "plan-3br": [
    { x: 0.02, y: 0.02, w: 0.44, h: 0.5, n: 1, door: true },
    { x: 0.48, y: 0.02, w: 0.3, h: 0.3, n: 2 },
    { x: 0.8, y: 0.02, w: 0.18, h: 0.3, wet: true, n: 3 },
    { x: 0.48, y: 0.34, w: 0.5, h: 0.18, n: 8 },
    { x: 0.02, y: 0.54, w: 0.3, h: 0.44, n: 4, door: true },
    { x: 0.34, y: 0.54, w: 0.3, h: 0.44, n: 5, door: true },
    { x: 0.66, y: 0.54, w: 0.32, h: 0.28, n: 9, door: true },
    { x: 0.66, y: 0.84, w: 0.32, h: 0.14, wet: true, n: 6 },
  ],
  "plan-4br": [
    { x: 0.02, y: 0.02, w: 0.4, h: 0.44, n: 1, door: true },
    { x: 0.44, y: 0.02, w: 0.28, h: 0.26, n: 2 },
    { x: 0.74, y: 0.02, w: 0.24, h: 0.26, n: 10 },
    { x: 0.44, y: 0.3, w: 0.28, h: 0.16, wet: true, n: 3 },
    { x: 0.74, y: 0.3, w: 0.24, h: 0.16, wet: true, n: 7 },
    { x: 0.02, y: 0.48, w: 0.24, h: 0.5, n: 4, door: true },
    { x: 0.28, y: 0.48, w: 0.22, h: 0.5, n: 5, door: true },
    { x: 0.52, y: 0.48, w: 0.22, h: 0.5, n: 5, door: true },
    { x: 0.76, y: 0.48, w: 0.22, h: 0.3, n: 9, door: true },
    { x: 0.76, y: 0.8, w: 0.22, h: 0.18, wet: true, n: 6 },
  ],
  "plan-duplex": [
    { x: 0.02, y: 0.02, w: 0.56, h: 0.54, n: 1, door: true },
    { x: 0.6, y: 0.02, w: 0.38, h: 0.32, n: 2 },
    { x: 0.6, y: 0.36, w: 0.38, h: 0.2, n: 11 },
    { x: 0.02, y: 0.58, w: 0.3, h: 0.4, n: 4, door: true },
    { x: 0.34, y: 0.58, w: 0.26, h: 0.4, n: 5, door: true },
    { x: 0.62, y: 0.58, w: 0.2, h: 0.4, wet: true, n: 6 },
    { x: 0.84, y: 0.58, w: 0.14, h: 0.4, n: 12 },
  ],
};

await mkdir(IMG, { recursive: true });
console.log("Rendering scenes…");
for (const [name, fn] of SCENES) await emit(name, fn());

console.log("Rendering floor plans…");
for (const [name, rooms] of Object.entries(PLANS)) {
  await writeFile(resolve(IMG, `${name}.svg`), plan(name, rooms));
  console.log("  ✓", name);
}

/* Open Graph card + icons — the brand mark is the client's own artwork
   (assets/img/logo-mark.png), composited over a generated background rather
   than redrawn, so the logo on the site is the real one. */
const LOGO = resolve(IMG, "logo-mark.png");

const ogBg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="#0E1417"/><stop offset="0.6" stop-color="#1C272D"/><stop offset="1" stop-color="#3A3428"/></linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0" stop-color="#3E525E"/><stop offset="1" stop-color="#1E2C35"/></linearGradient>
    ${blurDef("soft", 40)}${grainDef("grain", 0.9)}
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <circle cx="980" cy="520" r="260" fill="#B08D4F" opacity="0.25" filter="url(#soft)"/>
  ${(() => {
    const r = rng("og");
    const p = { ...PALETTES.dusk, litRate: 0.4 };
    let out = "";
    for (let i = 0; i < 7; i++) {
      const w = between(r, 80, 130), h = between(r, 150, 330);
      out += box(r, { x: 640 + i * 84, y: 630 - h, w, h, p, floors: Math.max(4, Math.round(h / 36)), opacity: 0.92, dx: w * 0.18, dy: -w * 0.08 });
    }
    return out;
  })()}
  <text x="80" y="416" font-family="IBM Plex Sans Arabic, sans-serif" font-size="64" font-weight="700" fill="#F8F5F0">شركة جنرال شيرمان للإسكان</text>
  <text x="80" y="472" font-family="IBM Plex Sans Arabic, sans-serif" font-size="32" font-weight="400" fill="#D6B87E">نبني مستقبلك — شقق سكنية في غرب عمّان</text>
  <text x="80" y="546" font-family="IBM Plex Sans Arabic, sans-serif" font-size="24" font-weight="500" fill="#9AA5AA" letter-spacing="3">GENERAL SHERMAN HOUSING · AMMAN, JORDAN</text>
</svg>`;

await writeFile(resolve(IMG, "og-image.svg"), ogBg);
const ogLogo = await sharp(LOGO).resize({ width: 190 }).toBuffer();
await sharp(Buffer.from(ogBg), { density: 200 })
  .resize(1200, 630)                      // resize runs before composite in sharp
  .composite([{ input: ogLogo, top: 86, left: 80 }])
  .png({ quality: 90 }).toFile(resolve(IMG, "og-image.png"));
console.log("  ✓ og-image");

// Browser tab icon: the mark alone, squared on transparency.
const markMeta = await sharp(LOGO).metadata();
const side = Math.max(markMeta.width, markMeta.height);
const squared = await sharp({
  create: { width: side, height: side, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } },
}).composite([{ input: LOGO, gravity: "center" }]).png().toBuffer();
await sharp(squared).resize(32, 32).png().toFile(resolve(ROOT, "favicon-32.png"));

// iOS tile: the same mark on the brand's ink, since iOS renders it opaque.
// sharp resizes before it composites, so the tile is built at full size and
// scaled down in a second pass rather than chained.
const tile = await sharp({ create: { width: 512, height: 512, channels: 4, background: "#0F1518" } })
  .composite([{ input: await sharp(LOGO).resize({ width: 340 }).toBuffer(), gravity: "center" }])
  .png().toBuffer();
await sharp(tile).resize(180, 180).png().toFile(resolve(ROOT, "apple-touch-icon.png"));
console.log("  ✓ icons");
console.log("Done.");
