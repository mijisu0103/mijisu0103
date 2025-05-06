import asyncio
from playwright.async_api import async_playwright
import os

# URL of the public TryHackMe badge widget
BADGE_URL = "https://tryhackme.com/api/v2/badges/public-profile?userPublicId=4240160"

# Output file path for the captured badge image
OUT_PATH = "badges/tryhackme_badge.png"

async def run():
    # Create the output directory if it doesn't exist
    os.makedirs("badges", exist_ok=True)

    async with async_playwright() as p:
        # Launch a headless Chromium browser
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Open the badge URL and wait until network activity stops
        await page.goto(BADGE_URL, wait_until='networkidle')

        # Locate the badge element using its CSS ID
        badge = await page.query_selector('#thm-badge')
        if badge:
            # Get the exact position and size of the badge element
            box = await badge.bounding_box()
            if box:
                # Take a screenshot of the badge only (without background or extra padding)
                await page.screenshot(
                    path=OUT_PATH,
                    clip={
                        "x": box["x"],
                        "y": box["y"],
                        "width": box["width"],
                        "height": box["height"]
                    },
                    omit_background=True   # Make background transparent
                )
            else:
                print("Could not get bounding box for badge element.")
        else:
            print("Could not find the badge element.")

        # Close the browser after capturing
        await browser.close()

# Run the async Playwright script
asyncio.run(run())
