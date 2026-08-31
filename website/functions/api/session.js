/**
 * GET /api/session — who you are, and whether the panel is wired up.
 *
 * The panel calls this before anything else, so that a missing environment
 * variable reads as "GITHUB_TOKEN is not set, here is where to set it" rather
 * than a save button that fails at the end of a long edit.
 */

import { json, identify, repoConfig , guard } from "./_lib.js";

export const onRequest = guard(async ({ request, env }) => {
  const who = await identify(request, env);
  if (who.error) return json({ error: who.error }, who.status);

  const cfg = repoConfig(env);
  return json({
    email: who.email,
    repo: cfg.error ? null : cfg.repo,
    branch: cfg.error ? null : cfg.branch,
    ready: !cfg.error,
    error: cfg.error || null,
  });
});
