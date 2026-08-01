import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BADGE_URL = (
    "https://tryhackme.com/api/v2/badges/public-profile"
    "?userPublicId=4240160"
)

BASE_DIR = Path(__file__).resolve().parent
OUT_PATH = BASE_DIR / "badges" / "tryhackme_badge.png"


async def run() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        page = await browser.new_page(
            viewport={
                "width": 1200,
                "height": 800,
            },
            device_scale_factor=2,
        )

        try:
            response = await page.goto(
                BADGE_URL,
                wait_until="networkidle",
                timeout=60_000,
            )

            if response is None:
                raise RuntimeError("TryHackMe badge page returned no response.")

            if not response.ok:
                raise RuntimeError(
                    f"TryHackMe badge request failed: "
                    f"{response.status} {response.status_text}"
                )

            await page.wait_for_selector(
                "body",
                state="visible",
                timeout=30_000,
            )

            badge = page.locator("#thm-badge")

            if await badge.count() > 0:
                await badge.first.screenshot(
                    path=str(OUT_PATH),
                    omit_background=True,
                )
            else:
                print(
                    "Warning: #thm-badge was not found. "
                    "Capturing the visible page content instead."
                )

                body = page.locator("body")
                await body.screenshot(
                    path=str(OUT_PATH),
                    omit_background=True,
                )

            if not OUT_PATH.is_file():
                raise RuntimeError(
                    f"Screenshot was not created at {OUT_PATH}"
                )

            if OUT_PATH.stat().st_size == 0:
                raise RuntimeError(
                    f"Screenshot was created but is empty: {OUT_PATH}"
                )

            print(
                f"Badge screenshot saved to {OUT_PATH} "
                f"({OUT_PATH.stat().st_size} bytes)"
            )

        except Exception:
            debug_path = BASE_DIR / "badge-debug.png"

            try:
                await page.screenshot(
                    path=str(debug_path),
                    full_page=True,
                )
                print(f"Debug screenshot saved to {debug_path}")
            except Exception as debug_error:
                print(f"Could not save debug screenshot: {debug_error}")

            raise

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
