/**
 * GET /api/deploys — the last few deploy runs, for the dashboard.
 *
 * Saving in the panel commits; the commit triggers CI; CI deploys. Those are
 * three steps, and between the second and the third is where this site's worst
 * outage lived — main was green and the live pages were twelve hours stale,
 * because nothing in the repository said the deploy was not running.
 *
 * So the panel does not tell you "saved" and stop. It tells you whether the
 * commit you just made has actually reached the site.
 */

import { json, identify, repoConfig, gh , guard } from "./_lib.js";

export const onRequest = guard(async ({ request, env }) => {
  const who = await identify(request, env);
  if (who.error) return json({ error: who.error }, who.status);

  const cfg = repoConfig(env);
  if (cfg.error) return json({ error: cfg.error }, 503);

  try {
    const runs = await gh(cfg, "/actions/workflows/deploy-website.yml/runs?per_page=5");
    return json({
      runs: (runs.workflow_runs || []).map((r) => ({
        sha: r.head_sha,
        status: r.status,
        conclusion: r.conclusion,
        started: r.created_at,
        url: r.html_url,
        message: (r.head_commit?.message || "").split("\n")[0],
      })),
    });
  } catch (e) {
    return json({ error: String(e.message || e) }, 502);
  }
});
