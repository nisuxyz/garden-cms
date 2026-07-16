"""Screenshot one or more themes (home + docs) for review.

Self-contained: starts its own dev server, activates each requested
theme in turn, captures home + docs, then restores the theme that was
active before. Never leaves the active theme changed.

Usage:
    PYTHONPATH=. uv run python scripts/screenshot_themes.py sprig mycelium
    PYTHONPATH=. uv run python scripts/screenshot_themes.py              # all three
"""
import asyncio
import os
import signal
import subprocess
import sys
import time
import urllib.request

os.environ.setdefault("ADMIN_PASSWORD", "devpassword")

from playwright.async_api import async_playwright
from piccolo_conf import DB
from db.tables import Theme

BASE = "http://localhost:8765"
OUT = "screenshots"
ALL = ["mycelium", "sprig", "nightshade"]
# Themes that default to light unless told otherwise still render fine;
# for dark-capable themes we grab dark too.
SCHEMES = {"nightshade": ["dark", "light"], "mycelium": ["light"], "sprig": ["light", "dark"]}


def _wait_up(timeout=45) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                if r.status:
                    return True
        except Exception:
            time.sleep(1)
    return False


async def _set_active(slug: str) -> None:
    await Theme.update({Theme.active: False}, force=True)
    await Theme.update({Theme.active: True}).where(Theme.slug == slug)


async def _current_active() -> str:
    row = await Theme.select(Theme.slug).where(Theme.active.eq(True)).first()
    return row["slug"] if row else "mycelium"


async def _shoot(browser, path, out, scheme):
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900}, device_scale_factor=2
    )
    await ctx.add_init_script(f"localStorage.setItem('theme', '{scheme}');")
    page = await ctx.new_page()
    await page.goto(f"{BASE}{path}")
    await page.wait_for_load_state("networkidle")
    await page.evaluate("async () => { if (document.fonts) await document.fonts.ready; }")
    await page.wait_for_timeout(600)  # let UnoCSS/fonts settle
    await page.screenshot(path=f"{OUT}/{out}", full_page=True)
    print(f"  ✓ {out}")
    await ctx.close()


async def main():
    targets = sys.argv[1:] or ALL
    await DB.start_connection_pool()
    original = await _current_active()
    print(f"active theme was: {original!r}")
    await DB.close_connection_pool()

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", "8765", "--log-level", "warning"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid,
    )
    try:
        if not _wait_up():
            print("server did not come up", file=sys.stderr)
            return
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            for slug in targets:
                await DB.start_connection_pool()
                await _set_active(slug)
                await DB.close_connection_pool()
                print(f"[{slug}]")
                for scheme in SCHEMES.get(slug, ["light"]):
                    suffix = f"-{scheme}" if len(SCHEMES.get(slug, ["light"])) > 1 else ""
                    await _shoot(browser, "/", f"{slug}-home{suffix}.png", scheme)
                    await _shoot(browser, "/docs", f"{slug}-docs{suffix}.png", scheme)
            await browser.close()
    finally:
        try:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        except Exception:
            server.terminate()
        await DB.start_connection_pool()
        await _set_active(original)
        print(f"restored active theme: {original!r}")
        await DB.close_connection_pool()


asyncio.run(main())
