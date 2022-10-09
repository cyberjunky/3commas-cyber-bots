"""Cyberjunky's 3Commas bot helpers."""
import json
from playwright.sync_api import sync_playwright

def get_shared_bot_data(logger, bot_id, bot_secret):
    """Get the shared bot data from the 3C website"""

    url = "https://app.3commas.io/wapi/bots/%s/get_bot_data?secret=%s" % (bot_id, bot_secret)

    data = {}
    try:
        with sync_playwright() as p:
            # Webkit is fastest to start and hardest to detect
            browser = p.webkit.launch(headless=True)

            page = browser.new_page()
            page.goto(url)

            # Use evaluate instead of `content` not to import bs4 or lxml
            html = page.evaluate('document.querySelector("pre").innerText')

        try:
            data = json.loads(html)

            logger.info("Fetched %s 3C shared bot data OK" % (bot_id))
        except:
            # Still might fail sometimes
            data = None
            logger.error("Failed to fetch %s 3C shared bot data" % (bot_id))

    except json.decoder.JSONDecodeError as err:
        logger.error(f"Shared bot data ({bot_id}) is not valid json")

    return data
