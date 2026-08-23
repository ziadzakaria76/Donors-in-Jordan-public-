"""GIZ tenders (ausschreibungen.giz.de).

German-language portal: dates arrive as 31.12.2026 or "15. Januar 2027" and
values use dot-as-thousands (EUR 1.500.000 is 1.5 million, not 1.5). Both are
handled in dates.py and money.py.

Its listing is a header table, and at least one row ships an unclosed <td>,
which is why table extraction takes each cell's OWN text -- see
extraction.cell_text() for the full explanation.
"""

from __future__ import annotations

from .base import HtmlPortal


class GizPortal(HtmlPortal):
    name = "giz"
    label = "GIZ"
    url = "https://ausschreibungen.giz.de/"
    anchor_pattern = r"/Satellite/(company/)?\w+"
    selectors = None
