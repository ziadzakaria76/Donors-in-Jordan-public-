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
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.adapters.http import USER_AGENT  # noqa: E402

TIMEOUT = 25.0

# Ordered: the first marker found wins, so put the specific before the general.
ATS_MARKERS: tuple[tuple[str, str], ...] = (
    ("myworkdayjobs.com", "Workday"),
    ("workdayjobs.com", "Workday"),
    ("/wday/cxs/", "Workday"),
    ("hcmui/candidateexperience", "Oracle Recruiting Cloud"),
    ("recruitingcejobrequisitions", "Oracle Recruiting Cloud"),
    ("oraclecloud.com", "Oracle Cloud (HCM likely)"),
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
           ("https://careers.qiddiya.com/", "https://qiddiya.com/careers/")),
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
           ("https://www.kingsalmanpark.sa/en/careers", "https://www.kingsalmanpark.sa/")),
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
           ("https://www.elseif.com.sa/careers", "https://www.elseif.com.sa/")),
    Target("Al Bawani", "A", ("https://www.albawani.net/careers", "https://www.albawani.net/")),
    Target("Almabani General Contractors", "A",
           ("https://www.almabani.com/careers", "https://www.almabani.com/")),
    Target("Alfanar Construction", "A", ("https://www.alfanar.com/careers",)),
    Target("Saudi Tabreed", "A",
           ("https://www.saudi-tabreed.com.sa/careers", "https://www.saudi-tabreed.com.sa/")),
    Target("Marafiq", "A", ("https://www.marafiq.com.sa/en/careers", "https://www.marafiq.com.sa/")),
    Target("Zamil Air Conditioning", "A",
           ("https://www.zamilac.com/careers", "https://www.zamilac.com/")),
    Target("Alkifah Contracting", "A", ("https://alkifah.com/en/careers", "https://alkifah.com/")),
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


def probe(client: httpx.Client, url: str) -> dict:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}

    body = response.text[:400_000]
    return {
        "url": url,
        "status": response.status_code,
        "final_url": str(response.url),
        "ats": detect(str(response.url), body),
        "bytes": len(response.content),
    }


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
    args = parser.parse_args()

    client = httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en,ar;q=0.8"},
    )

    print("## ATS reconnaissance\n")
    print("| Employer | Lane | Result | Platform | Final URL |")
    print("| --- | --- | --- | --- | --- |")

    findings: list[dict] = []
    for target in TARGETS:
        best: dict | None = None
        for url in target.urls:
            result = probe(client, url)
            findings.append({"employer": target.employer, **result})
            if result.get("ats"):
                best = result
                break
            if best is None or (
                result.get("status") == 200 and best.get("status") != 200
            ):
                best = result

        assert best is not None
        if best.get("error"):
            outcome, platform = "unreachable", best["error"][:60]
        elif best.get("ats"):
            outcome, platform = f"HTTP {best['status']}", best["ats"]
        else:
            outcome, platform = f"HTTP {best['status']}", "not identified"

        final = best.get("final_url", best["url"])
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
