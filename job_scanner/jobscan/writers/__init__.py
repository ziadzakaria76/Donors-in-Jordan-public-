"""Output writers. Re-exported so scanner.py imports one module, not four.

__all__ rather than a noqa comment: pyflakes does not honour noqa, and the
repository's CI lints with pyflakes.
"""

from .excel import write_xlsx
from .page import write_html
from .payload import write_json
from .shortlist import write_docx

__all__ = ["write_xlsx", "write_docx", "write_json", "write_html"]
