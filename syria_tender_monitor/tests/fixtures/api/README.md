# Reconstructed API payloads

These are **not captured from the live APIs** — the build environment could not
reach any of them. They are reconstructions of each API's documented response
shape, and they exist so the field mapping in `src/syria_monitor/portals/*.py`
is pinned by a test rather than discovered on first live contact.

Treat them as assumptions under test, not evidence. The moment you can reach the
real endpoints, replace each file with a genuine response:

```bash
PYTHONPATH=src python -m syria_monitor.cli --capture worldbank   # prints the raw payload
```

If a real payload differs, the contract test will fail — that failure is the
point. Fix the parser, then commit the real payload over the reconstruction and
note it here.

Every file carries one record for our country, one for another country, and one
edge case, so the country gate is exercised alongside the field mapping.

| File | Status |
|---|---|
| `worldbank.json` | reconstructed, unverified |
| `ted.json` | reconstructed, unverified |
| `samgov.json` | reconstructed, unverified |
| `uk_fts.json` | reconstructed, unverified |
