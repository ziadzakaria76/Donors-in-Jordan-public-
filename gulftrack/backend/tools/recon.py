"""Identify which applicant tracking system each target employer runs.

Why this exists as a CI job rather than a local script: the environment
GulfTrack is developed in can reach GitHub and package registries only, so no
careers page is reachable from there. GitHub Actions runners have unrestricted
egress. This is the same route the tender monitor in this repository already
uses, and it is the only way to answer a question that requires actually
loading the page.

It is read-only. It issues a small number of GET requests to public careers
pages, follows redirects, and reports what platform served the response. It
submits nothing, logs in to nothing, and stores nothing.

    python tools/recon.py            # probe every target
    python tools/recon.py --oracle   # also test the ROSHN Oracle endpoint live
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.adapters.http import USER_AGENT  # noqa: E402

TIMEOUT = 25.0

# Ordered: the first marker found wins, so put the specific before the general.
ATS_MARKERS: tuple[tuple[str, str], ...] = (
    ("myworkdayjobs.com", "Workday"),
    ("workdayjobs.com", "Workday"),
    ("/wday/cxs/", "Workday"),
    # hcmUI is the recruiting product; fscmUI is finance and supplier
    # registration. Matching the bare oraclecloud.com host conflated the two
    # and put Expo 2030 down as an ATS it does not have.
    ("hcmui/candidateexperience", "Oracle Recruiting Cloud"),
    ("recruitingcejobrequisitions", "Oracle Recruiting Cloud"),
    ("successfactors.com", "SAP SuccessFactors"),
    ("successfactors.eu", "SAP SuccessFactors"),
    ("jobs.sap.com", "SAP SuccessFactors"),
    ("taleo.net", "Oracle Taleo"),
    ("boards.greenhouse.io", "Greenhouse"),
    ("greenhouse.io", "Greenhouse"),
    ("apply.workable.com", "Workable"),
    ("workable.com", "Workable"),
    ("jobs.lever.co", "Lever"),
    ("smartrecruiters.com", "SmartRecruiters"),
    ("icims.com", "iCIMS"),
    ("bamboohr.com", "BambooHR"),
    ("ashbyhq.com", "Ashby"),
    ("teamtailor.com", "Teamtailor"),
    ("recruitee.com", "Recruitee"),
    ("zohorecruit", "Zoho Recruit"),
    ("myworkdaysite.com", "Workday"),
    ("workforcenow.adp.com", "ADP"),
    ("oraclerecruiting", "Oracle Recruiting Cloud"),
)


@dataclass
class Target:
    employer: str
    lane: str
    urls: tuple[str, ...]


TARGETS: tuple[Target, ...] = (
    # Lane B — client-side / developer delivery
    Target("Qiddiya Investment Company", "B",
           ("https://qiddiya.com/careers/", "https://apply.workable.com/qiddiya-investment-company-1/")),
    Target("Diriyah Company", "B",
           ("https://www.diriyahcompany.sa/en/careers", "https://www.dgda.gov.sa/en/careers")),
    Target("ROSHN Group", "B", ("https://www.roshn.sa/careers",)),
    Target("Expo 2030 Riyadh Company", "B",
           ("https://www.expo2030riyadh.sa/en/careers", "https://www.expo2030riyadh.sa/")),
    Target("Jeddah Central Development Company", "B",
           ("https://jeddahcentral.com/en/careers", "https://jeddahcentral.com/")),
    Target("New Murabba", "B",
           ("https://newmurabba.com/en/careers", "https://newmurabba.com/")),
    Target("King Salman Park Development Company", "B",
           ("https://kingsalmanpark.com/en/careers", "https://kingsalmanpark.com/",
            "https://www.ksp.sa/")),
    Target("Saudi Entertainment Ventures (SEVEN)", "B",
           ("https://seven.sa/en/careers", "https://seven.sa/")),
    Target("KAFD DMC", "B", ("https://www.kafd.sa/en/careers", "https://www.kafd.sa/")),
    Target("Soudah Development", "B",
           ("https://soudah.sa/en/careers", "https://soudah.sa/")),
    Target("Royal Commission for Riyadh City", "B",
           ("https://www.rcrc.gov.sa/en/careers/",)),

    # Lane A — contractor operations
    Target("Nesma & Partners", "A", ("https://careers.nesmapartners.com/",)),
    Target("El Seif Engineering", "A",
           ("https://elseif.com.sa/career", "https://elseif.com.sa/careers", "https://elseif.com.sa/")),
    Target("Al Bawani", "A", ("https://albawani.com/en/careers", "https://albawani.com/en/")),
    Target("Almabani General Contractors", "A",
           ("https://www.almabani.com/careers", "https://www.almabani.com/")),
    Target("Alfanar Construction", "A",
           ("https://www.alfanar.com/en/careers", "https://www.alfanar.com/")),
    Target("Saudi Tabreed", "A",
           ("https://saudi-tabreed.com/careers", "https://saudi-tabreed.com/",
            "https://www.sauditabreed.com/")),
    Target("Marafiq", "A", ("https://www.marafiq.com.sa/en/careers", "https://www.marafiq.com.sa/")),
    Target("Zamil Air Conditioning", "A",
           ("https://www.zamilac.com/careers", "https://www.zamilac.com/")),
    Target("Alkifah Contracting", "A",
           ("https://www.alkifah.com.sa/en/careers", "https://www.alkifah.com.sa/")),
    Target("Hassan Allam Saudi", "A",
           ("https://hassanallam.com/careers/", "https://hassanallam.com/")),
    Target("Johnson Controls Arabia", "A", ("https://www.johnsoncontrols.com/careers",)),
)


def detect(final_url: str, body: str) -> str | None:
    haystack = f"{final_url}\n{body}".lower()
    for marker, name in ATS_MARKERS:
        if marker in haystack:
            return name
    return None


# Hosts worth extracting in full when they appear inside a page. Knowing an
# employer is "on Oracle" is not actionable; knowing the exact tenant host and
# site number is what an adapter needs.
ATS_HOST_PATTERN = re.compile(
    r"https?://[\w.\-]*(?:"
    r"myworkdayjobs\.com|myworkdaysite\.com|oraclecloud\.com|successfactors\.(?:com|eu)"
    r"|taleo\.net|greenhouse\.io|workable\.com|lever\.co|smartrecruiters\.com"
    r"|icims\.com|bamboohr\.com|ashbyhq\.com|teamtailor\.com|zohorecruit\.com"
    r")[^\s\"'<>\\)]*",
    re.IGNORECASE,
)

# A careers page frequently links out to the real portal rather than embedding
# it. Anything whose text or href looks like a job listing is worth reporting.
CAREER_LINK_PATTERN = re.compile(
    r"https?://[\w.\-]+/[^\s\"'<>\\)]*(?:job|career|vacan|recruit|apply|employment)"
    r"[^\s\"'<>\\)]*",
    re.IGNORECASE,
)


def extract_ats_urls(body: str, limit: int = 6) -> list[str]:
    """Exact ATS URLs embedded in the page, deduplicated, longest first.

    The longest match usually carries the site number or board token, which is
    the part an adapter cannot guess.
    """
    found = {m.group(0).rstrip(".,;") for m in ATS_HOST_PATTERN.finditer(body)}
    return sorted(found, key=len, reverse=True)[:limit]


def extract_career_links(body: str, own_host: str, limit: int = 6) -> list[str]:
    """Off-site links that look like a jobs portal.

    Restricted to other hosts: a link back into the same site tells us nothing
    we did not already have.
    """
    found = set()
    for match in CAREER_LINK_PATTERN.finditer(body):
        url = match.group(0).rstrip(".,;")
        host = urlparse(url).netloc.lower()
        if host and own_host.lower().lstrip("www.") not in host:
            found.add(url)
    return sorted(found, key=len, reverse=True)[:limit]


def probe(client: httpx.Client, url: str) -> dict:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}

    body = response.text[:400_000]
    # A short body behind a 403 is a bot challenge, not a careers page. Saying
    # so is more useful than reporting "not identified".
    blocked = response.status_code == 403 and len(response.content) < 20_000

    return {
        "url": url,
        "status": response.status_code,
        "final_url": str(response.url),
        "ats": detect(str(response.url), body),
        "ats_urls": extract_ats_urls(body),
        "career_links": extract_career_links(body, urlparse(url).netloc),
        "bot_challenge": blocked,
        "bytes": len(response.content),
    }


# Candidate endpoints for the platforms the page probe actually confirmed.
# Every one of these is a guess about request shape; the point of running them
# is to find out which is real rather than to ship an adapter built on a hunch.
API_CANDIDATES: tuple[tuple[str, str, str, dict | None], ...] = (
    # Qiddiya — Workable board apply.workable.com/qiddiya-investment-company-1
    ("qiddiya/workable", "GET",
     "https://apply.workable.com/api/v3/accounts/qiddiya-investment-company-1/jobs", None),
    ("qiddiya/workable", "POST",
     "https://apply.workable.com/api/v3/accounts/qiddiya-investment-company-1/jobs",
     {"query": "", "location": [], "department": [], "worktype": [], "remote": []}),
    ("qiddiya/workable-spi", "GET",
     "https://apply.workable.com/spi/v3/accounts/qiddiya-investment-company-1/jobs", None),

    # ROSHN — Oracle tenant confirmed by the page probe; the REST call 403'd, so
    # try the variations that differ in how the finder and headers are formed.
    ("roshn/oracle-plain", "GET",
     "https://fa-epph-saasfaprod1.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest"
     "/recruitingCEJobRequisitions?onlyData=true"
     "&finder=findReqs;siteNumber=CX_1,limit=5", None),
    ("roshn/oracle-11.13", "GET",
     "https://fa-epph-saasfaprod1.fa.ocs.oraclecloud.com/hcmRestApi/resources/11.13.18.05"
     "/recruitingCEJobRequisitions?onlyData=true"
     "&finder=findReqs;siteNumber=CX_1,limit=5", None),

    # Diriyah — SuccessFactors instance career23.sapsf.com, company thediriyah.
    ("diriyah/sapsf-rss", "GET",
     "https://career23.sapsf.com/careers?company=thediriyah&rss=true", None),
    ("diriyah/sapsf-search", "GET",
     "https://career23.sapsf.com/search?company=thediriyah", None),

    # Johnson Controls — Workday tenant jci, site JCI, on wd5.
    ("jci/workday", "POST",
     "https://jci.wd5.myworkdayjobs.com/wday/cxs/jci/JCI/jobs",
     {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "Saudi"}),
)


def probe_apis() -> list[dict]:
    """Call each candidate endpoint once and report exactly what came back.

    No retries and no politeness delay: this is a handful of one-off requests
    to find the real shape, not a scan.
    """
    results = []
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/xml;q=0.9, */*;q=0.5",
        },
    ) as client:
        for label, method, url, body in API_CANDIDATES:
            entry = {"label": label, "method": method, "url": url}
            try:
                if method == "POST":
                    response = client.post(url, json=body)
                else:
                    response = client.get(url)
            except httpx.HTTPError as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                results.append(entry)
                continue

            entry["status"] = response.status_code
            entry["content_type"] = response.headers.get("content-type", "")
            text = response.text
            entry["bytes"] = len(response.content)
            try:
                payload = response.json()
            except ValueError:
                entry["json"] = False
                entry["snippet"] = text[:400]
            else:
                entry["json"] = True
                entry["top_level_keys"] = (
                    sorted(payload)[:15] if isinstance(payload, dict) else "list"
                )
                entry["snippet"] = json.dumps(payload, ensure_ascii=False)[:900]
            results.append(entry)
    return results


def probe_oracle_live() -> dict:
    """Call ROSHN's Oracle endpoint exactly as the adapter would."""
    from app.adapters.oracle_orc import ROSHN, OracleRecruitingAdapter
    from app.adapters.http import PoliteClient

    adapter = OracleRecruitingAdapter(ROSHN, PoliteClient(delay_seconds=4.0))
    try:
        postings = adapter.fetch()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "ok": True,
        "count": len(postings),
        "sample": [
            {
                "id": p.source_job_id,
                "title": p.title,
                "location": p.location,
                "posted": str(p.posted_date) if p.posted_date else None,
                "has_description": bool(p.description),
                "url": p.url,
            }
            for p in postings[:5]
        ],
        # The field names the tenant actually returned, which is the thing the
        # adapter's mapping has to be checked against.
        "observed_fields": sorted(postings[0].raw)[:40] if postings else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", action="store_true",
                        help="also run the ROSHN Oracle adapter against the live tenant")
    parser.add_argument("--api-probe", action="store_true",
                        help="call candidate ATS API endpoints and report what each returns")
    parser.add_argument("--skip-pages", action="store_true",
                        help="skip the page sweep; useful when only the API probe is wanted")
    args = parser.parse_args()

    if args.api_probe:
        print("## Candidate API endpoints\n")
        for entry in probe_apis():
            print(f"### {entry['label']} — {entry['method']}")
            print(f"`{entry['url']}`\n")
            print("```json")
            print(json.dumps(entry, indent=2, ensure_ascii=False)[:2500])
            print("```\n")

    if args.skip_pages:
        return 0

    client = httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en,ar;q=0.8"},
    )

    print("## ATS reconnaissance\n")
    print("| Employer | Lane | Result | Platform | Exact portal URL or final URL |")
    print("| --- | --- | --- | --- | --- |")

    findings: list[dict] = []
    for target in TARGETS:
        best: dict | None = None
        for url in target.urls:
            result = probe(client, url)
            findings.append({"employer": target.employer, **result})
            if result.get("ats_urls"):
                best = result
                break
            if result.get("ats") and best is None:
                best = result
            if best is None or (
                result.get("status") == 200 and best.get("status") != 200
            ):
                best = result

        assert best is not None
        if best.get("error"):
            outcome, platform = "unreachable", best["error"][:60]
        elif best.get("bot_challenge"):
            outcome, platform = "HTTP 403", "bot challenge — needs a browser"
        elif best.get("ats"):
            outcome, platform = f"HTTP {best['status']}", best["ats"]
        else:
            outcome, platform = f"HTTP {best['status']}", "not identified"

        exact = (best.get("ats_urls") or [None])[0]
        final = exact or best.get("final_url", best["url"])
        print(f"| {target.employer} | {target.lane} | {outcome} | {platform} | {final[:90]} |")

    client.close()

    identified = [f for f in findings if f.get("ats")]
    print(f"\n**{len(identified)} of {len(TARGETS)} employers identified.**\n")

    if args.oracle:
        print("\n## ROSHN Oracle adapter, live\n")
        result = probe_oracle_live()
        print("```json")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:6000])
        print("```")

    # Full detail for anything the table flattened.
    print("\n<details><summary>Every probe</summary>\n")
    print("```json")
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:60_000])
    print("```\n</details>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
