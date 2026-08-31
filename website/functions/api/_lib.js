/**
 * Shared plumbing for the admin API: who is asking, and how to commit.
 *
 * Files whose name begins with "_" are not routes — Cloudflare Pages skips
 * them when it maps functions/ onto URLs — so this is a module, not an
 * endpoint.
 */

/**
 * A JSON response.
 *
 * One rule about `status`: never 502, and never 504.
 *
 * Not because the body is lost — it is not — but because those two statuses are
 * the ones Cloudflare itself answers with when a Pages Function dies or the
 * platform is unwell, and its "Bad gateway / Host Error" page carries the same
 * 502 this code would. So a 502 from here is indistinguishable, from a browser,
 * from the platform failing: seeing one tells you nothing about whether this
 * code ran at all. Hours went into that ambiguity on this project.
 *
 * 500 is also the more accurate word. This is not a gateway. When a call to
 * GitHub fails, that is our own request failing, and the panel owns it.
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

  /* Fetching Cloudflare's signing keys is the one step here that reaches the
     network, so it is the one that can fail for reasons nothing else explains:
     a mistyped ACCESS_TEAM_DOMAIN, or Cloudflare having a moment. Letting it
     throw hands the browser an opaque 502 from the platform — the failure says
     nothing, and the person reading it has no idea which of five variables to
     look at. Naming the domain that failed is the whole difference. */
  let keys;
  try {
    keys = await accessKeys(env.ACCESS_TEAM_DOMAIN);
  } catch (e) {
    return {
      error: `Could not fetch Cloudflare Access signing keys from ${env.ACCESS_TEAM_DOMAIN} (${e.message || e}). ` +
        "Check ACCESS_TEAM_DOMAIN — it should be your team domain with no https:// and no trailing slash, " +
        "and it must match the one in Zero Trust -> Settings -> Team domain.",
      status: 500,
    };
  }
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
    /* 401 and 403 are different diagnoses and must not share a sentence. A 401
       is GitHub saying the token is not a token — no permission change can fix
       that, and sending someone to the permission checkboxes wastes the trip.
       This message did exactly that, and cost a real evening. */
    const hint = res.status === 401
      ? " — GitHub rejected the token itself, not its permissions: the stored GITHUB_TOKEN is truncated, revoked or expired, so it has to be reissued and pasted again"
      : res.status === 403
        ? " — check the token's permissions: editing content needs Contents: Read and write, and the deploy list needs Actions: Read"
        : "";
    throw new Error(`GitHub ${init.method || "GET"} ${path} → ${res.status}${hint}: ${body.slice(0, 300)}`);
  }
  return res.json();
}

/**
 * Make the three calls the panel depends on, and report each one by name.
 *
 * `repoConfig` only proves the variables are set, which is a much weaker claim
 * than it looks: a token can be present and expired, present and truncated by a
 * copy-paste, or present and granted the wrong permissions. All of those read
 * as "configured" and then fail at the first real call — the end of a long
 * edit, which is the worst moment to find out.
 *
 * It probes each API separately because they do not fail together. Loading the
 * panel reads Contents; the deploy list reads Actions; saving writes Contents.
 * Those are three distinct permissions on a fine-grained token, and a token
 * carrying one and not another produces a panel that half works — which is
 * exactly the shape of the failure this was written during, where /api/content
 * answered and /api/deploys did not.
 *
 * Special care goes to GitHub's 404. A fine-grained token is not told that a
 * repository it cannot see exists, so "misspelt name" and "never granted"
 * arrive as the identical reply, and reporting only the status leaves the
 * reader guessing which they have. Naming both is the difference between a fix
 * and an afternoon.
 *
 * Never throws, and never hangs: this runs inside the one endpoint that still
 * answers when the others do not, and it must not become the reason it stops.
 */
export async function probeRepo(cfg) {
  const checks = [];
  let expires = null;

  /** One call, reported rather than thrown. A timeout is a result, not a hang. */
  const call = async (name, path, need) => {
    let res;
    try {
      res = await fetch(`https://api.github.com/repos/${cfg.repo}${path}`, {
        headers: {
          authorization: `Bearer ${cfg.token}`,
          accept: "application/vnd.github+json",
          "user-agent": "general-sherman-admin",
        },
        signal: AbortSignal.timeout(8000),
      });
    } catch (e) {
      const timedOut = e?.name === "TimeoutError" || e?.name === "AbortError";
      checks.push({
        name, ok: false,
        detail: timedOut
          ? "api.github.com did not answer within eight seconds."
          : `Could not reach api.github.com: ${e?.message || e}`,
      });
      return null;
    }

    /* Fine-grained tokens carry their own expiry in a response header, so "has
       it expired?" is answerable here rather than by asking someone to look. */
    expires = res.headers.get("github-authentication-token-expiration") || expires;

    if (res.ok) {
      checks.push({ name, ok: true });
      return res;
    }

    const msg = await headline(res);

    /* GitHub spends 403 on two unrelated things: a token without the
       permission, and a caller who has made too many requests. Reading the
       first as the second sends someone into the token settings to fix a
       permission that was never wrong, so the rate limit has to be ruled out
       before the word "permission" is used at all. */
    const rateLimited = (res.status === 403 || res.status === 429)
      && (res.headers.get("x-ratelimit-remaining") === "0" || /rate limit|secondary rate/i.test(msg));

    let detail;
    if (res.status === 401) {
      detail = "GitHub rejected the token as bad credentials, so the stored value is not a usable token. " +
        "Most often it was truncated on the way into the dashboard, or it has been revoked.";
    } else if (rateLimited) {
      const reset = Number(res.headers.get("x-ratelimit-reset"));
      const when = Number.isFinite(reset) && reset > 0
        ? ` It clears at ${new Date(reset * 1000).toISOString().slice(11, 16)} UTC.`
        : " It clears on its own shortly.";
      detail = `GitHub is rate-limiting these requests, so this says nothing about the token's permissions.${when}`;
    } else if (res.status === 404) {
      detail = "GitHub answered 404. Because a fine-grained token is not told that something it cannot see " +
        `exists, this reads as either a wrong name or a missing permission: check GITHUB_REPO is exactly ` +
        `"${cfg.repo}" (case does not matter, every other character does, including a trailing hyphen), and ` +
        `that the token grants ${need} on this repository.`;
    } else if (res.status === 403) {
      detail = `GitHub refused with 403, which usually means the token is missing ${need}. ${msg}`;
    } else {
      detail = `GitHub answered ${res.status}. ${msg}`;
    }
    checks.push({ name, ok: false, detail });
    return null;
  };

  const repoRes = await call("repository", "", "Contents: Read");
  if (repoRes) {
    const repo = await repoRes.json();
    /* Seeing the repository is not enough to save into it. Reading is the
       weaker permission, and the panel only ever fails on the write. */
    checks.push(repo.permissions?.push === true
      ? { name: "write access", ok: true }
      : {
        name: "write access", ok: false,
        detail: `The token can read ${repo.full_name} but not write to it. Set Repository permissions → ` +
          "Contents to 'Read and write' — 'Read-only' loads the panel and cannot save from it.",
      });

    const refRes = await call(`branch ${cfg.branch}`, `/git/ref/heads/${cfg.branch}`, "Contents: Read");
    if (!refRes && checks.at(-1)?.detail?.includes("404")) {
      checks.at(-1).detail += ` The default branch of ${repo.full_name} is "${repo.default_branch}" — if that ` +
        "is the one you meant, set GITHUB_BRANCH to it or remove the variable and let it default.";
    }
  }

  /* The deploy list is the one call that needs a permission nobody thinks to
     grant: Actions, not Contents. Probing it separately means a missing
     Actions grant reads as itself instead of as the panel being broken. */
  await call("deploy history", "/actions/workflows/deploy-website.yml/runs?per_page=1", "Actions: Read");

  const failed = checks.filter((c) => !c.ok);
  return {
    ok: failed.length === 0,
    checks,
    expires,
    problem: failed.length
      ? failed.map((c) => `${c.name}: ${c.detail}`).join(" ")
      : null,
  };
}

/** The first useful line of a GitHub error body, for putting inside a sentence. */
async function headline(res) {
  try {
    const body = await res.json();
    return String(body.message || "").slice(0, 200);
  } catch {
    return "GitHub gave no reason.";
  }
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

/**
 * Run a route so that nothing it throws reaches the platform.
 *
 * An uncaught throw in a Pages Function becomes a Cloudflare error page: a bare
 * 502 with no body, no clue, and nothing the person configuring this can act
 * on. Every other failure in this panel names itself; these should too.
 */
export function guard(handler) {
  return async (context) => {
    try {
      return await handler(context);
    } catch (e) {
      return json({
        error: `The admin API failed unexpectedly: ${e?.message || e}`,
        where: new URL(context.request.url).pathname,
      }, 500);
    }
  };
}

export { gh };
