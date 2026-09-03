#!/usr/bin/env python3
"""Find the search endpoint behind a JavaScript careers page.

    python discover_playwright.py https://employer.example/careers
    python discover_playwright.py https://employer.example/careers --key burjeel

Opens the page headless, watches every network response, and scores each JSON
body by whether it holds a repeated array of objects carrying title-like and
location-like fields. Prints a sources.yaml block ready to paste.

This is a DISCOVERY tool, run by hand, once per employer. It is deliberately
not importable by scanner.py and Playwright is deliberately absent from
requirements.txt: once an endpoint is found it gets hard-coded into
sources.yaml, and the weekly run stays a handful of HTTP requests.

Finding no JSON is a RESULT, not a failure. Plenty of careers pages are
server-rendered -- their vacancy table is in the HTML document itself -- and
for those the tool emits an html_table block instead. A tool that reported
"discovery failed" there would send you hunting for an XHR that does not exist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Field-name vocabularies. A candidate array has to look like vacancies, not
# merely like an array -- analytics beacons and menu payloads are arrays too.
TITLE_KEYS = (
    "title", "jobtitle", "job_title", "positiontitle", "position", "name",
    "requisitiontitle", "externaltitle", "vacancytitle", "postingtitle", "jobname",
)
LOCATION_KEYS = (
    "location", "locationname", "city", "country", "primarylocation", "joblocation",
    "job_location", "geography", "region", "site", "workplace", "locationtext",
)
ID_KEYS = ("id", "jobid", "job_id", "jobreqid", "requisitionid", "uuid", "slug", "reqid", "code")
URL_KEYS = ("url", "applyurl", "joburl", "apply_url", "public_url", "externalurl", "link", "href")
POSTED_KEYS = (
    "posteddate", "posted_at", "published_at", "publisheddate", "createddate",
    "createdat", "creationdate", "postingstartdate", "datposted", "startdate",
)
# Kept strictly apart from POSTED_KEYS. Mapping one of these to posted_at makes
# every ancient vacancy look fresh, which is the failure max_age_days exists
# to catch.
CLOSING_KEYS = (
    "closingdate", "closing_date", "expires_at", "expirydate", "deadline",
    "applicationdeadline", "postingenddate", "enddate", "lastdate",
)
DEPARTMENT_KEYS = (
    "department", "division", "businessunit", "jobfamily", "category",
    "job_category", "specialty", "speciality", "function", "organizationname",
)
TYPE_KEYS = ("employmenttype", "employment_type", "jobtype", "job_type", "type", "workertype", "scheduletype")

SKIP_URL_PATTERNS = re.compile(
    r"(google|facebook|doubleclick|hotjar|segment|analytics|gtm|sentry|"
    r"cookielaw|onetrust|recaptcha|cloudflare|adobedtm|clarity\.ms)",
    re.I,
)


def _find_browser() -> str | None:
    """Locate a chromium the installed Playwright can actually launch."""
    override = os.environ.get("PW_CHROMIUM_PATH")
    if override and Path(override).exists():
        return override
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if root.exists():
        candidates = sorted(root.glob("chromium-*/chrome-linux/chrome"), reverse=True)
        if candidates:
            return str(candidates[0])
    return None   # let Playwright use its own download


def _keys_of(record: dict) -> dict[str, str]:
    return {key.lower(): key for key in record if isinstance(key, str)}


def _match(keys: dict[str, str], vocabulary: tuple[str, ...]) -> str | None:
    """Exact key match first, then suffix/prefix, so 'jobTitle' beats 'subtitle'."""
    for word in vocabulary:
        if word in keys:
            return keys[word]
    for word in vocabulary:
        for low, original in keys.items():
            if low.endswith(word) or low.startswith(word):
                return original
    return None


def _walk(payload, path: str = "", depth: int = 0):
    """Yield every (path, list-of-dicts) in the body."""
    if depth > 8:
        return
    if isinstance(payload, list):
        if payload and sum(1 for item in payload[:20] if isinstance(item, dict)) >= max(1, len(payload[:20]) // 2):
            yield path, payload
        for index, item in enumerate(payload[:3]):
            yield from _walk(item, f"{path}.{index}" if path else str(index), depth + 1)
    elif isinstance(payload, dict):
        for key, value in payload.items():
            yield from _walk(value, f"{path}.{key}" if path else str(key), depth + 1)


def score_array(records: list) -> tuple[int, dict[str, str]]:
    """How much does this array look like a list of vacancies?"""
    sample = [r for r in records[:20] if isinstance(r, dict)]
    if not sample:
        return 0, {}
    keys = _keys_of(sample[0])
    # Prefer keys shared across the sample: a real record set is homogeneous.
    for record in sample[1:5]:
        shared = _keys_of(record)
        keys = {k: v for k, v in keys.items() if k in shared} or keys

    mapping = {
        "title": _match(keys, TITLE_KEYS),
        "location": _match(keys, LOCATION_KEYS),
        "id": _match(keys, ID_KEYS),
        "url": _match(keys, URL_KEYS),
        "posted_at": _match(keys, POSTED_KEYS),
        "closing_at": _match(keys, CLOSING_KEYS),
        "department": _match(keys, DEPARTMENT_KEYS),
        "employment_type": _match(keys, TYPE_KEYS),
    }

    score = 0
    if mapping["title"]:
        score += 50            # without a title it is not a vacancy list
    if mapping["location"]:
        score += 30
    if mapping["id"]:
        score += 10
    if mapping["url"]:
        score += 10
    if mapping["posted_at"]:
        score += 10
    if mapping["closing_at"]:
        score += 5
    if mapping["department"]:
        score += 5
    score += min(len(records), 25)            # a longer list is more likely the real one
    if len(records) == 1:
        score -= 15                            # often a "featured job" widget
    if not mapping["title"]:
        score = min(score, 15)                 # cap: cannot be the answer
    return score, {k: v for k, v in mapping.items() if v}


def analyse_html(html: str, page_url: str) -> dict | None:
    """Look for a server-rendered vacancy table when no JSON turned up."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    soup = BeautifulSoup(html, "lxml")

    best = None
    # Ordered most- to least-precise. Rows are counted excluding header rows (a
    # tr of th and no td), so "table tbody tr" and "table tr" tie on a normal
    # table and the strict > below keeps the tighter selector.
    for selector in ("table tbody tr", "table tr", "ul.job-list li", "div.job-listing",
                     "article.job", "div.job-card", "li.job"):
        rows = [r for r in soup.select(selector) if r.find("td") is not None or r.name != "tr"]
        linked = [r for r in rows if r.select_one("a[href]")]
        if len(rows) >= 3 and len(linked) >= 2:
            if best is None or len(rows) > best[1]:
                best = (selector, len(rows), linked[0])
    if not best:
        return None

    selector, count, sample = best
    headers = []
    table = soup.select_one(selector.split(" tbody")[0]) if "tr" in selector else None
    if table:
        headers = [th.get_text(" ", strip=True) for th in table.select("thead th, tr:first-child th")]
    return {"row_selector": selector, "rows": count, "headers": headers,
            "sample": sample.get_text(" ", strip=True)[:120]}


def _yaml_block(key: str, page_url: str, best: dict | None, html_hint: dict | None) -> str:
    host = urlparse(page_url).netloc
    lines = [f"  - key: {key}", f"    name: TODO  # employer name", "    country: TODO",
             f"    careers_url: \"{page_url}\""]

    if best:
        platform = "successfactors" if "successfactors" in best["url"] else (
            "oracle_orc" if "hcmRestApi" in best["url"] or "oraclecloud" in best["url"] else (
                "elevatus" if "elevatus" in best["url"] else "successfactors"))
        lines += [
            f"    platform: {platform}",
            "    enabled: true",
            "    verified: true            # ONLY if this call returned postings",
            "    api:",
            f'      url: "{best["url"]}"',
            f'      method: {best["method"]}',
            f'      records_path: "{best["records_path"]}"',
            "      fields:",
        ]
        for field, source_key in best["fields"].items():
            lines.append(f'        {field}: "{source_key}"')
        if "posted_at" not in best["fields"]:
            lines.append(
                "      # NOTE: no posting-date field found. Leave posted_at unmapped --"
            )
            lines.append(
                "      # do NOT point it at the closing date; a deadline is not a posting date."
            )
        lines.append(
            f"    note: >-\n      Endpoint captured from {host} on a live page load; "
            f"{best['records']} record(s) at records_path."
        )
    elif html_hint:
        lines += [
            "    platform: html_table",
            "    enabled: true",
            "    verified: true            # ONLY if this call returned postings",
            "    html:",
            f'      url: "{page_url}"',
            f'      row_selector: "{html_hint["row_selector"]}"',
            f"    note: >-\n      Server-rendered: the vacancy table is in the HTML document and no "
            f"JSON search endpoint is called. {html_hint['rows']} rows matched.",
        ]
    else:
        lines += [
            "    platform: unknown",
            "    enabled: false",
            "    verified: unconfirmed",
            "    note: >-\n      Nothing found: no JSON response looked like a vacancy list and no "
            "repeated row structure was present in the HTML. The list may need a search to be "
            "submitted, or a session/login.",
        ]
    return "\n".join(lines)


def discover(url: str, key: str, timeout: int = 45000, wait: int = 6000, headed: bool = False) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed.\n  pip install -r requirements-browser.txt\n"
              "  playwright install chromium\n  playwright install-deps   # Linux, needs sudo",
              file=sys.stderr)
        return 3

    captured: list[dict] = []
    executable = _find_browser()

    with sync_playwright() as pw:
        launch: dict = {"headless": not headed}
        if executable:
            launch["executable_path"] = executable
        try:
            browser = pw.chromium.launch(**launch)
        except Exception as exc:
            print(f"could not launch chromium: {exc}", file=sys.stderr)
            return 3

        page = browser.new_page()

        def on_response(response):
            if SKIP_URL_PATTERNS.search(response.url):
                return
            content_type = (response.headers or {}).get("content-type", "")
            if "json" not in content_type.lower():
                return
            try:
                body = response.json()
            except Exception:
                return
            for path, array in _walk(body):
                score, mapping = score_array(array)
                if score > 0:
                    captured.append({
                        "url": response.url, "method": response.request.method,
                        "records_path": path, "records": len(array),
                        "score": score, "fields": mapping,
                    })

        page.on("response", on_response)

        print(f"opening {url}", file=sys.stderr)
        nav_error = ""
        try:
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            page.wait_for_timeout(wait)
            # Many boards only fetch once the list scrolls into view.
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(wait // 2)
        except Exception as exc:
            nav_error = str(exc)[:300]
            print(f"page load problem: {nav_error}", file=sys.stderr)

        html = ""
        try:
            html = page.content()
        except Exception:
            pass
        browser.close()

    captured.sort(key=lambda c: -c["score"])
    best = next((c for c in captured if c["fields"].get("title")), None)

    print("\n" + "=" * 72)
    print(f"DISCOVERY REPORT  —  {url}")
    print("=" * 72)

    # A page that never loaded and a page with no XHR look identical in the
    # capture list -- both are empty. Reporting them the same way would send
    # someone hunting for a hidden endpoint on a site they simply cannot reach.
    if nav_error and not captured:
        blocked = any(
            marker in nav_error
            for marker in ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_PROXY", "ERR_CONNECTION_REFUSED",
                           "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_TIMED_OUT", "ERR_SOCKS")
        )
        print("\nTHE PAGE DID NOT LOAD. Nothing was observed, so nothing can be concluded")
        print("about this employer's careers site.\n")
        print(f"  {nav_error.splitlines()[0]}")
        if blocked:
            print("\nThis is a NETWORK/EGRESS block: the request never reached the site.")
            print("It is not evidence about the site's platform. Re-run from a network")
            print("that can reach the host before recording anything in sources.yaml.")
        print("\nLeaving the source unconfirmed and disabled.")
        print("-" * 72)
        print(_yaml_block(key, url, None, None))
        print("-" * 72)
        return 2

    if captured:
        print(f"\n{len(captured)} candidate array(s) seen. Top by score:\n")
        for candidate in captured[:6]:
            marker = "*" if candidate is best else " "
            print(f" {marker} score {candidate['score']:>3}  {candidate['records']:>4} rec  "
                  f"path={candidate['records_path'] or '(root)'!r}")
            print(f"     {candidate['url'][:100]}")
            print(f"     fields: {candidate['fields'] or '(none recognised)'}")
    else:
        print("\nNo JSON response contained anything resembling a vacancy list.")

    html_hint = None
    if not best:
        html_hint = analyse_html(html, url) if html else None
        if html_hint:
            print("\nThe page is SERVER-RENDERED: the vacancy list is in the HTML document,")
            print("not fetched over XHR. That is a result, not a failure.")
            print(f"  row_selector: {html_hint['row_selector']!r}  ({html_hint['rows']} rows)")
            if html_hint["headers"]:
                print(f"  table headers: {html_hint['headers']}")
            print(f"  first row: {html_hint['sample']!r}")

    print("\n" + "-" * 72)
    print("Paste into sources.yaml (check every TODO, and read the verified: note):")
    print("-" * 72)
    print(_yaml_block(key, url, best, html_hint))
    print("-" * 72)
    print("verified: true is a claim that THIS endpoint returned postings. If you have")
    print("not seen postings come back through scanner.py, set url-confirmed instead.")
    return 0 if (best or html_hint) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", help="careers page URL")
    parser.add_argument("--key", default=None, help="source key for the emitted block")
    parser.add_argument("--wait", type=int, default=6000, help="ms to wait for XHR after load")
    parser.add_argument("--timeout", type=int, default=45000, help="ms page-load timeout")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    args = parser.parse_args(argv)
    key = args.key or re.sub(r"[^a-z0-9]+", "_", urlparse(args.url).netloc.lower()).strip("_")
    return discover(args.url, key, timeout=args.timeout, wait=args.wait, headed=args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
