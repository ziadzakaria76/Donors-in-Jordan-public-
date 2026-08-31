/**
 * Tests for probeRepo — the admin panel's "what is actually wrong" diagnosis.
 *
 * Every reply here is stubbed rather than fetched. That is the point: what is
 * under test is which sentence the panel shows for which GitHub reply, and a
 * test that asked the real API would depend on that API's mood and on a token
 * this runner does not have.
 *
 * The case that earned this file is the rate limit. GitHub spends 403 on two
 * unrelated things — a token without the permission, and a caller who has made
 * too many requests — and an earlier version read every 403 as the first,
 * sending the reader to change a permission that was never wrong. Live testing
 * found it by being rate-limited; nothing else would have.
 *
 * Run: node tools/test-probe.mjs
 */

const reply = (status, body = {}, headers = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

let routes = {};
globalThis.fetch = async (url) => {
  const path = new URL(url).pathname;
  for (const [fragment, make] of Object.entries(routes)) {
    if (fragment === "*" || path.includes(fragment)) return make();
  }
  return reply(500, { message: "the test routed nothing to this URL" });
};

const { probeRepo, gh } = await import("../functions/api/_lib.js");

const CFG = { repo: "owner/repo-", branch: "main", token: "github_pat_example" };
const HEALTHY = () => reply(
  200,
  { full_name: "owner/repo-", default_branch: "main", permissions: { push: true } },
  { "github-authentication-token-expiration": "2026-11-29 00:00:00 UTC" },
);

let passed = 0;
const failures = [];

async function test(label, stubs, expect) {
  routes = stubs;
  const out = await probeRepo(CFG);
  const text = out.checks.map((c) => `${c.name}|${c.detail || ""}`).join("\n");
  if (expect(out, text)) {
    passed++;
    console.log(`  ✓ ${label}`);
  } else {
    failures.push(label);
    console.log(`  ✗ ${label}\n${text.replace(/^/gm, "      ")}`);
  }
}

await test("a healthy token passes every check and reports its expiry",
  { "*": HEALTHY },
  (o) => o.ok && o.expires === "2026-11-29 00:00:00 UTC" && o.problem === null);

await test("401 is read as a token that is not usable, not as a permission",
  { "*": () => reply(401, { message: "Bad credentials" }) },
  (o, s) => !o.ok && s.includes("bad credentials") && !s.includes("permission"));

await test("404 names both of its causes, because GitHub will not say which",
  { "*": () => reply(404, { message: "Not Found" }) },
  (o, s) => !o.ok && s.includes("trailing hyphen") && s.includes("Contents: Read"));

await test("a rate limit is never reported as a missing permission",
  { "*": () => reply(403, { message: "API rate limit exceeded for 1.2.3.4." },
    { "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1800000000" }) },
  (o, s) => !o.ok && s.includes("rate-limiting") && !s.includes("missing Contents"));

await test("a genuine 403 still names the permission it needs",
  { "*": () => reply(403, { message: "Resource not accessible by personal access token" },
    { "x-ratelimit-remaining": "4999" }) },
  (o, s) => !o.ok && s.includes("missing Contents: Read") && !s.includes("rate-limiting"));

await test("a read-only token fails on write access, not on reading",
  { "/repos/owner/repo-": () => reply(200, { full_name: "owner/repo-", default_branch: "main", permissions: { push: false } }), "*": HEALTHY },
  (o, s) => !o.ok && s.includes("not write to it") && o.checks.find((c) => c.name === "repository").ok);

await test("a missing branch names the default branch instead",
  { "git/ref/heads": () => reply(404, { message: "Not Found" }), "*": HEALTHY },
  (o, s) => !o.ok && s.includes('default branch of owner/repo- is "main"'));

/* The failure this whole file exists to catch: Contents and Actions are
   separate grants, so the deploy list can be the only broken thing. */
await test("a missing Actions grant fails only the deploy history",
  { "actions/workflows": () => reply(403, { message: "Resource not accessible by personal access token" },
    { "x-ratelimit-remaining": "4999" }), "*": HEALTHY },
  (o, s) => !o.ok && s.includes("Actions: Read")
    && o.checks.filter((c) => !c.ok).length === 1
    && o.checks.find((c) => !c.ok).name === "deploy history");

await test("a network failure is reported rather than thrown",
  { "*": () => { throw new Error("boom"); } },
  (o, s) => !o.ok && s.includes("Could not reach api.github.com"));

/* The hint gh() attaches to a failure. It once told a 401 to go and check the
   Contents permission — advice that cannot fix a token GitHub will not accept
   at all, and that sent a real evening into the wrong settings page. */

async function hintFor(status, body) {
  routes = { "*": () => reply(status, body) };
  try {
    await gh(CFG, "/actions/workflows/deploy-website.yml/runs");
    return "(no error thrown)";
  } catch (e) {
    return e.message;
  }
}

const h401 = await hintFor(401, { message: "Bad credentials" });
await test("a 401 hint says the token is not a token, and names no permission",
  {}, () => /truncated, revoked or expired/.test(h401) && !/Contents: Read and write/.test(h401));

const h403 = await hintFor(403, { message: "Resource not accessible by personal access token" });
await test("a 403 hint names both permissions the panel needs",
  {}, () => /Contents: Read and write/.test(h403) && /Actions: Read/.test(h403));

console.log();
if (failures.length) {
  console.log(`  ✗ ${failures.length} of ${passed + failures.length} probe tests failed`);
  process.exit(1);
}
console.log(`  ✓ ${passed} probe tests pass`);
