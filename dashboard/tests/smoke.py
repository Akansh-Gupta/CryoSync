"""Smoke test for the dashboard shell and every registered page.

Streamlit is not running here, so this test does not exercise layout. It does
check the things that actually break in practice: that every page module
imports, that each one exposes ``render``, and that the registry and the page
package agree with each other.

Run from the ``dashboard`` directory:

    python -m tests.smoke
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from core.registry import NAV_GROUPS, NAV_ITEMS  # noqa: E402


def main() -> int:
    failures: list[str] = []

    print(f"Registry: {len(NAV_GROUPS)} groups, {len(NAV_ITEMS)} pages\n")

    for group in NAV_GROUPS:
        print(f"  {group.label} ({group.key})")

        for item in group.items:
            try:
                module = importlib.import_module(item.module)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{item.slug}: import failed - {exc}")
                print(f"    FAIL  {item.label:<20} {exc}")
                continue

            if not callable(getattr(module, "render", None)):
                failures.append(f"{item.slug}: {item.module} has no render()")
                print(f"    FAIL  {item.label:<20} no render()")
                continue

            print(f"    ok    {item.label:<20} {item.module}")

    # Modules present but not registered would be dead code.
    package = DASHBOARD_DIR / "pages_bundle"

    registered = {item.module.rsplit(".", 1)[-1] for item in NAV_ITEMS}

    on_disk = {
        path.stem
        for path in package.glob("*.py")
        if not path.stem.startswith("_")
    }

    for orphan in sorted(on_disk - registered):
        print(f"\n  note  pages_bundle/{orphan}.py is not registered")

    for missing in sorted(registered - on_disk):
        failures.append(f"registered page has no module: {missing}")
        print(f"\n  FAIL  registered but missing: pages_bundle/{missing}.py")

    print()

    if failures:
        print(f"{len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("All pages import and expose render().")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
