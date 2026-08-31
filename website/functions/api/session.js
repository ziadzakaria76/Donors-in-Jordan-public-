/**
 * GET /api/session — who you are, and whether the panel is actually wired up.
 *
 * The panel calls this before anything else, so that a misconfiguration reads
 * as "GITHUB_TOKEN is not set, here is where to set it" rather than a save
 * button that fails at the end of a long edit.
 *
 * It asks GitHub rather than only reading the variables. Checking that the
 * variables exist and calling that "ready" is how this project lost twelve
 * hours once already: the Git connection was configured, the dashboard said so,
 * and main was not reaching the site. A setting is a claim about the world, and
 * the only way to check a claim is to make the call.
 *
 * That also makes this the endpoint to read when the others are failing. It is
 * the one route that reaches GitHub and still returns 200 when the answer is
 * bad news, so it can describe a broken token instead of becoming another
 * error page.
 */

import { json, identify, repoConfig, probeRepo, guard } from "./_lib.js";

export const onRequest = guard(async ({ request, env }) => {
  const who = await identify(request, env);
  if (who.error) return json({ error: who.error }, who.status);

  const cfg = repoConfig(env);
  if (cfg.error) {
    return json({ email: who.email, repo: null, branch: null, ready: false, error: cfg.error });
  }

  const probe = await probeRepo(cfg);

  return json({
    email: who.email,
    repo: cfg.repo,
    branch: cfg.branch,
    ready: probe.ok,
    error: probe.ok ? null : probe.problem,
    /* Reported whether or not anything is wrong: a token that works today and
       expires in a fortnight is worth seeing before the fortnight is up. */
    tokenExpires: probe.expires || null,
  });
});
