/**
 * Shared plumbing for the admin API: who is asking, and how to commit.
 *
 * Files whose name begins with "_" are not routes — Cloudflare Pages skips
 * them when it maps functions/ onto URLs — so this is a module, not an
 * endpoint.
 */

export const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      /* Nothing here may ever be cached. The panel reads the live schedule and
         writes it back; a cached GET means editing a copy of yesterday. */
      "cache-control": "no-store",
    },
  });

/* ============================================================== identity ===
   The panel is protected by Cloudflare Access, which sits in front of these
   routes and will not let an unauthenticated request through.

   This still verifies the assertion itself rather than trusting the
   Cf-Access-Authenticated-User-Email header, because "Access is in front of
   it" is a claim about a dashboard setting — the same class of claim as the
   Git connection that silently was not there while main stopped reaching the
   site for twelve hours. If the Access policy is ever removed, misapplied to
   the wrong path, or scoped to /admin but not /api, the header simply stops
   arriving and an unprotected write endpoint is left facing the internet.
   Verifying the signature means that failure is a 401, not a stranger with
   commit access.
   ========================================================================= */

/** Cache the signing keys for the lifetime of the isolate — they rotate slowly. */
let keyCache = null;

async function accessKeys(teamDomain) {
  if (keyCache && keyCache.domain === teamDomain && Date.now() - keyCache.at < 3600_000) {
    return keyCache.keys;
  }
  const res = await fetch(`https://${teamDomain}/cdn-cgi/access/certs`);
  if (!res.ok) throw new Error(`Access certs: ${res.status}`);
  const { keys } = await res.json();
  const imported = new Map();
  for (const jwk of keys) {
    imported.set(jwk.kid, await crypto.subtle.importKey(
      "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"],
    ));
  }
  keyCache = { domain: teamDomain, keys: imported, at: Date.now() };
  return imported;
}

const b64url = (s) => {
  const pad = s.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(pad + "=".repeat((4 - (pad.length % 4)) % 4)), (c) => c.charCodeAt(0));
};

/**
 * @returns {Promise<{email: string} | {error: string, status: number}>}
 */
export async function identify(request, env) {
  const missing = ["ACCESS_TEAM_DOMAIN", "ACCESS_AUD"].filter((k) => !env[k]);
  if (missing.length) {
    return {
      error: `The admin API is not configured: ${missing.join(" and ")} ${missing.length === 1 ? "is" : "are"} not set. ` +
        "Cloudflare dashboard → Workers & Pages → the project → Settings → Variables and Secrets.",
      status: 503,
    };
  }

  const token = request.headers.get("Cf-Access-Jwt-Assertion")
    || (request.headers.get("cookie") || "").match(/CF_Authorization=([^;]+)/)?.[1];
  if (!token) {
    return {
      error: "No Cloudflare Access assertion on this request. Either you reached this URL from outside " +
        "Access, or the Access application does not cover this path — it must cover /api/* as well as /admin/*.",
      status: 401,
    };
  }

  const [rawHeader, rawPayload, rawSig] = token.split(".");
  if (!rawSig) return { error: "Malformed Access assertion.", status: 401 };

  let head, payload;
  try {
    head = JSON.parse(new TextDecoder().decode(b64url(rawHeader)));
    payload = JSON.parse(new TextDecoder().decode(b64url(rawPayload)));
  } catch {
    return { error: "Unreadable Access assertion.", status: 401 };
  }

  const keys = await accessKeys(env.ACCESS_TEAM_DOMAIN);
  const key = keys.get(head.kid);
  if (!key) return { error: "Access assertion signed by an unknown key.", status: 401 };

  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", key, b64url(rawSig), new TextEncoder().encode(`${rawHeader}.${rawPayload}`),
  );
  if (!ok) return { error: "Access assertion failed signature verification.", status: 401 };

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < now) return { error: "Your session has expired. Reload the page to sign in again.", status: 401 };
  if (payload.iss !== `https://${env.ACCESS_TEAM_DOMAIN}`) return { error: "Access assertion issued for another team.", status: 401 };

  /* aud is the Access application's tag. Without this check, any application in
     the same Access team would be a valid key to this one.

     ACCESS_AUD may name more than one, comma-separated, because covering both
     /admin and /api took two Access applications — the dashboard's form allows
     a single hostname per application. A token issued by either one is
     legitimate here: both are ours and both enforce the same policy, and which
     of them signed the token depends on where the person landed first. Naming
     only one would reject a valid session for no reason a user could act on.

     What this still refuses is a token from an application we did not name,
     which is the check that matters. */
  const allowed = String(env.ACCESS_AUD).split(",").map((s) => s.trim()).filter(Boolean);
  const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!aud.some((a) => allowed.includes(a))) {
    return { error: "Access assertion issued for another application.", status: 401 };
  }

  return { email: payload.email || "unknown" };
}

/* ================================================================ github ===
   The panel has no database. It saves by committing to the repository, which
   means every edit is a diff with an author and a date, CI runs on it, and the
   deploy is the same deploy as any other change. Reverting a mistake is
   `git revert`, not a support request.
   ========================================================================= */

export function repoConfig(env) {
  const missing = ["GITHUB_TOKEN", "GITHUB_REPO"].filter((k) => !env[k]);
  if (missing.length) {
    return {
      error: `Cannot reach the repository: ${missing.join(" and ")} not set. ` +
        "Cloudflare dashboard → Workers & Pages → the project → Settings → Variables and Secrets. " +
        "GITHUB_TOKEN must be a fine-grained token with Contents: read and write on this repository, and it must be encrypted.",
    };
  }
  return { repo: env.GITHUB_REPO, branch: env.GITHUB_BRANCH || "main", token: env.GITHUB_TOKEN };
}

async function gh(cfg, path, init = {}) {
  const res = await fetch(`https://api.github.com/repos/${cfg.repo}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${cfg.token}`,
      accept: "application/vnd.github+json",
      "user-agent": "general-sherman-admin",
      ...(init.body ? { "content-type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    const hint = res.status === 401 || res.status === 403
      ? " — check GITHUB_TOKEN has Contents: read and write on this repository and has not expired"
      : "";
    throw new Error(`GitHub ${init.method || "GET"} ${path} → ${res.status}${hint}: ${body.slice(0, 300)}`);
  }
  return res.json();
}

/** The branch head, and a file from it, in one round trip each. */
export async function readFile(cfg, path) {
  const ref = await gh(cfg, `/git/ref/heads/${cfg.branch}`);
  const sha = ref.object.sha;
  const res = await fetch(
    `https://api.github.com/repos/${cfg.repo}/contents/${encodeURIComponent(path).replace(/%2F/g, "/")}?ref=${sha}`,
    { headers: { authorization: `Bearer ${cfg.token}`, accept: "application/vnd.github.raw", "user-agent": "general-sherman-admin" } },
  );
  if (!res.ok) throw new Error(`GitHub could not read ${path} at ${sha.slice(0, 7)}: ${res.status}`);
  return { text: await res.text(), commit: sha };
}

/**
 * Commit several files as one commit.
 *
 * One commit, not one per file, because content.json and the data.js rendered
 * from it must never be separately visible: a commit with only one of them is a
 * commit where `npm run check` fails, and CI would reject the deploy of an edit
 * that was actually fine.
 *
 * `expect` is the commit the panel was looking at when it started editing. If
 * the branch has moved since — someone pushed, or a second tab saved — this
 * returns a conflict rather than overwriting work it never saw.
 */
export async function commitFiles(cfg, { files, message, expect, author }) {
  const ref = await gh(cfg, `/git/ref/heads/${cfg.branch}`);
  const head = ref.object.sha;
  if (expect && expect !== head) {
    return { conflict: true, head };
  }

  const base = await gh(cfg, `/git/commits/${head}`);

  const tree = await gh(cfg, "/git/trees", {
    method: "POST",
    body: JSON.stringify({
      base_tree: base.tree.sha,
      tree: files.map((f) => ({ path: f.path, mode: "100644", type: "blob", content: f.content })),
    }),
  });

  /* Nothing changed. Saying so beats an empty commit in the history. */
  if (tree.sha === base.tree.sha) return { unchanged: true, commit: head };

  const commit = await gh(cfg, "/git/commits", {
    method: "POST",
    body: JSON.stringify({
      message,
      tree: tree.sha,
      parents: [head],
      author: author ? { name: author.name, email: author.email, date: new Date().toISOString() } : undefined,
    }),
  });

  await gh(cfg, `/git/refs/heads/${cfg.branch}`, {
    method: "PATCH",
    body: JSON.stringify({ sha: commit.sha }),
  });

  return { commit: commit.sha };
}

export { gh };
