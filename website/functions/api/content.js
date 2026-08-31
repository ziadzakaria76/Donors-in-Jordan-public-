/**
 * GET  /api/content   the live content.json, and the commit it came from
 * PUT  /api/content   validate it, render data.js, commit both as one commit
 *
 * This is the whole write path of the admin panel. There is no database: the
 * repository is the store, so an edit is a diff with an author and a date, CI
 * runs on it, the deploy is the ordinary deploy, and undoing a mistake is
 * `git revert` rather than a support request.
 */

import { json, identify, repoConfig, readFile, commitFiles, guard } from "./_lib.js";
import { render } from "../../tools/render-data.mjs";
import { validate } from "../../tools/validate-content.mjs";

const CONTENT = "website/content.json";
const DATA = "website/assets/js/data.js";

export const onRequest = guard(async ({ request, env }) => {
  const who = await identify(request, env);
  if (who.error) return json({ error: who.error }, who.status);

  const cfg = repoConfig(env);
  if (cfg.error) return json({ error: cfg.error }, 503);

  if (request.method === "GET") {
    try {
      const { text, commit } = await readFile(cfg, CONTENT);
      return json({ content: JSON.parse(text), commit, editor: who.email });
    } catch (e) {
      return json({ error: String(e.message || e), where: "/api/content" }, 500);
    }
  }

  if (request.method !== "PUT") {
    return json({ error: `${request.method} is not allowed here.` }, 405);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "The request body was not valid JSON." }, 400);
  }

  const { content, commit: expect, message } = body || {};
  if (!content) return json({ error: "No content in the request body." }, 400);

  /* Validate before rendering, not after. A render of invalid content is a
     data.js that parses perfectly and quietly shows a blank where the aspect
     goes, which is exactly the failure mode this panel exists to prevent. */
  const errors = validate(content);
  if (errors.length) return json({ error: "The content did not pass validation.", errors }, 422);

  let dataJs;
  try {
    dataJs = render(content);
  } catch (e) {
    return json({ error: `Could not render data.js: ${e.message || e}` }, 500);
  }

  /* No syntax check here, deliberately. The obvious move is to parse the
     rendered file before committing it — but the Workers runtime blocks eval
     and new Function, so there is nothing to parse it with. The guarantee has
     to come from the renderer instead: every value goes through
     JSON.stringify, every key that is not an identifier is quoted, and the one
     place raw text reaches the file unquoted is a project's `notes`, which
     validate-content.mjs rejects if it contains a comment terminator.

     CI is the backstop. `npm run check` re-renders content.json and compares,
     and a data.js that will not parse fails `node --check` there before any
     deploy runs. A broken render would therefore stop at a red build, not at a
     blank site. */

  try {
    const result = await commitFiles(cfg, {
      files: [
        { path: CONTENT, content: `${JSON.stringify(content, null, 2)}\n` },
        { path: DATA, content: dataJs },
      ],
      message: message?.trim()
        ? `${message.trim()}\n\nEdited in the admin panel by ${who.email}.`
        : `Update the site content\n\nEdited in the admin panel by ${who.email}.`,
      expect,
      author: { name: who.email.split("@")[0], email: who.email },
    });

    if (result.conflict) {
      return json({
        error: "Somebody else changed the content while you were editing. Reload to pick up their version, " +
          "then make your change again — saving now would overwrite an edit this page never saw.",
        head: result.head,
      }, 409);
    }
    if (result.unchanged) return json({ unchanged: true, commit: result.commit });

    return json({ commit: result.commit });
  } catch (e) {
    return json({ error: String(e.message || e), where: "/api/content" }, 500);
  }
});
