from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
import sys


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
REPO_ROOT = Path(__file__).resolve().parents[1]


HREF_RE = re.compile(r'href="([^"]+)"')
ACTION_RE = re.compile(r'action="([^"]+)"')


def iter_template_files() -> Iterable[Path]:
    for p in TEMPLATE_DIR.rglob("*.html"):
        yield p


def extract_paths(html: str) -> list[str]:
    values: list[str] = []
    values += [m.group(1) for m in HREF_RE.finditer(html)]
    values += [m.group(1) for m in ACTION_RE.finditer(html)]
    out: list[str] = []
    for v in values:
        v = v.strip()
        if not v.startswith("/"):
            continue
        if v.startswith("//"):
            continue
        if v.startswith("/static/"):
            continue
        if "{{" in v or "{%" in v:
            # dynamic (e.g. {{ admin_prefix }}) - skip static validation
            continue
        out.append(v.split("?", 1)[0])
    return out


def route_to_regex(path: str) -> re.Pattern:
    # Convert `/chat/{conversation_id}` to regex `^/chat/[^/]+$`
    pattern = re.escape(path)
    pattern = re.sub(r"\\\{[^\\}]+\\\}", r"[^/]+", pattern)
    return re.compile("^" + pattern + "$")


def main() -> int:
    # Ensure repo root is on sys.path (so `import main` works when running from scripts/).
    sys.path.insert(0, str(REPO_ROOT))

    # Import the app (this also registers routers)
    import main as app_main

    route_patterns: list[re.Pattern] = []
    for r in app_main.app.router.routes:
        p = getattr(r, "path", None)
        if not p:
            continue
        route_patterns.append(route_to_regex(p))

    missing: list[tuple[str, str]] = []
    for f in iter_template_files():
        text = f.read_text(encoding="utf-8")
        for p in extract_paths(text):
            if any(rx.match(p) for rx in route_patterns):
                continue
            missing.append((str(f.relative_to(TEMPLATE_DIR)), p))

    if missing:
        print("BROKEN_LINKS_FOUND")
        for file_rel, path in sorted(set(missing)):
            print(f"- {file_rel}: {path}")
        return 1

    print("LINK_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

