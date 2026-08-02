"""
Tiny assertion harness.

Deliberately not pytest: the suite must run in CI with nothing installed beyond
the project's own requirements, and a test runner is not worth a dependency
here. Every check is counted so the README can state a real number rather than
a vague "the tests pass".
"""

from __future__ import annotations

import traceback

_PASSED: list[str] = []
_FAILED: list[tuple[str, str]] = []


def check(condition, label: str, detail: str = "") -> bool:
    """Assert one thing. Never raises -- a failure must not hide later checks."""
    if condition:
        _PASSED.append(label)
        return True
    _FAILED.append((label, detail or "expected a truthy value"))
    return False


def check_eq(got, want, label: str) -> bool:
    return check(got == want, label, f"got {got!r}, wanted {want!r}")


def check_raises(fn, exc_type, label: str) -> bool:
    try:
        fn()
    except exc_type:
        return check(True, label)
    except Exception as exc:  # noqa: BLE001
        return check(False, label, f"raised {type(exc).__name__} not {exc_type.__name__}: {exc}")
    return check(False, label, f"did not raise {exc_type.__name__}")


def run_suite(name: str, functions: list) -> None:
    print(f"\n{name}")
    print("-" * len(name))
    for fn in functions:
        before_failed = len(_FAILED)
        before_passed = len(_PASSED)
        try:
            fn()
        except Exception:  # noqa: BLE001 - a crashing test is a failing test
            _FAILED.append((fn.__name__, traceback.format_exc(limit=3)))
        added_f = len(_FAILED) - before_failed
        added_p = len(_PASSED) - before_passed
        mark = "ok  " if added_f == 0 else "FAIL"
        print(f"  {mark} {fn.__name__:52} {added_p} check(s)")


def report() -> int:
    total = len(_PASSED) + len(_FAILED)
    print("\n" + "=" * 72)
    if _FAILED:
        print(f"{len(_FAILED)} of {total} checks FAILED\n")
        for label, detail in _FAILED:
            print(f"  FAIL {label}\n       {detail}\n")
        return 1
    print(f"All {total} checks passed.")
    print("=" * 72)
    return 0


def counts() -> tuple[int, int]:
    return len(_PASSED), len(_FAILED)
