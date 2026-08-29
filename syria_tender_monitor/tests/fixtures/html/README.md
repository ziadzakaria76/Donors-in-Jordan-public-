# Reconstructed portal pages

Like `../api/`, these are **reconstructions, not captures** — no portal was
reachable from the build environment. They encode what each scraper assumes
about its page, so a wrong assumption fails in CI rather than silently on first
live contact.

Replace each file with a real capture as soon as you can reach the sites:

```bash
PYTHONPATH=src python -m syria_monitor.cli --capture giz   # writes tests/fixtures/live/
```

Then copy the captured HTML over the reconstruction and re-run the suite. A
failure at that point is information, not a nuisance: it names the field whose
mapping was wrong.

Each file carries a row for Syria, a row for somewhere else (so the country gate
is exercised), and one edge case — a missing deadline, an unclosed cell, or a
countdown before the publication date.

| File | Shape it mimics | Status |
|---|---|---|
| `ungm.html` | search-results rows, `/Public/Notice/<id>` anchors, relative countdown | reconstructed |
| `undp.html` | listing with `view_notice.cfm?notice_id=NNNNN` anchors | reconstructed |
| `srtf.html` | procurement list, `/procurements/...` anchors | reconstructed |
| `giz.html` | German header table, unclosed `<td>`, EU number format | reconstructed |
| `isdb.html` | card listing, `/project-procurement/...` anchors | reconstructed |
| `gtai.html` | KfW notices published by GTAI, `/en/trade/...` anchors | reconstructed |
