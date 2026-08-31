/**
 * GET /api/session — who you are, and whether the panel is actually wired up.
 *
 * The panel calls this before anything else, so that a misconfiguration reads
 * as "the token cannot write to this repository, here is where to fix it"
 * rather than a save button that fails at the end of a long edit.
 *
 * It asks GitHub rather than only reading the variables. Checking that the
 * variables exist and calling that "ready" is how this project lost twelve
 * hours once already: the Git connection was configured, the dashboard said so,
 * and main was not reaching the site. A setting is a claim about the world, and
 * the only way to test a claim is to make the call.
 *
 * That also makes this the endpoint to read when the others are failing, so it
 * is built not to fail with them. The probe cannot throw, every call inside it
 * times out rather than hanging, and `?probe=0` skips it entirely — if this
 * endpoint ever stops answering, that switch is what distinguishes "the GitHub
 * calls are what break it" from "something else is wrong", which is a question
 * no amount of reading the code settles.
 */

import { json, identify, repoConfig, probeRepo, guard } from "./_lib.js";

export const onRequest = guard(async ({ request, env }) => {
  const who = await identify(request, env);
  if (who.error) return json({ error: who.error }, who.status);

  const cfg = repoConfig(env);
  if (cfg.error) {
    return json({ email: who.email, repo: null, branch: null, ready: false, error: cfg.error });
  }

  const base = { email: who.email, repo: cfg.repo, branch: cfg.branch };

  if (new URL(request.url).searchParams.get("probe") === "0") {
    return json({ ...base, ready: null, error: null, checks: [], skipped: "GitHub was not contacted." });
  }

  const probe = await probeRepo(cfg);

  return json({
    ...base,
    ready: probe.ok,
    error: probe.problem,
    /* Each call reported by name, not merged into a verdict. Which of them
       failed is the whole diagnosis: reading content, writing it and listing
       deploys are three different permissions on a fine-grained token, and a
       token can carry one without the others. */
    checks: probe.checks,
    /* Reported whether or not anything is wrong: a token that works today and
       expires in a fortnight is worth seeing before the fortnight is out. */
    tokenExpires: probe.expires || null,
  });
});
