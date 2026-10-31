"""Every /api/... URL the web app calls must exist as a FastAPI route.

The pages call the API through a proxy, so a renamed route fails only at runtime
as a 404 that the UI then shows as a broken button. This catches it in CI.
"""
import re
from pathlib import Path

from app.main import create_app

WEB = Path(__file__).resolve().parents[3] / "apps" / "web"
CALL = re.compile(r"""[`"'](/api/[A-Za-z0-9_\-/.${}\[\]]*)""")
TEMPLATE_PART = re.compile(r"\$\{[^}]*\}")
# next-auth owns /api/auth/*; dyslexic.ts and the onboarding workspace append a path at runtime.
DYNAMIC_PREFIXES = ("/api/auth/", "/api/dyslexic${")


def _routes() -> list[str]:
    """Route paths with every {param} replaced by 'x', no trailing slash."""
    return [re.sub(r"\{[^}]*\}", "x", p.rstrip("/") or "/") for p in create_app().openapi()["paths"]]


def _matcher(call: str) -> re.Pattern:
    return re.compile("[^/]+".join(re.escape(part) for part in TEMPLATE_PART.split(call)))


def test_every_web_call_has_a_route():
    routes = _routes()
    missing = set()
    for sub in ("app", "components", "lib", "hooks"):
        for f in (WEB / sub).rglob("*.ts*"):
            if f.suffix not in (".ts", ".tsx") or ".test." in f.name or "[...path]" in str(f):
                continue
            for m in CALL.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                raw = m.group(1).rstrip("/")
                # A nested template literal cuts the match short; skip what we cannot resolve.
                if raw.startswith(DYNAMIC_PREFIXES) or raw.endswith("${path}") or raw.count("${") != raw.count("}"):
                    continue
                matcher = _matcher(raw)
                if not any(matcher.fullmatch(r) for r in routes):
                    missing.add(f"{raw} <- {f.relative_to(WEB)}")
    assert not missing, "\n".join(sorted(missing))
