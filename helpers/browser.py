"""Cyberjunky's 3Commas bot helpers."""
import cloudscraper
import json

def get_shared_bot_data(logger, bot_id, bot_secret):
    """Get the shared bot data from the 3C website"""

    url = "https://app.3commas.io/wapi/bots/%s/get_bot_data?secret=%s" % (bot_id, bot_secret)

    data = {}
    try:
        statuscode = 0
        scrapecount = 0
        while (scrapecount < 3) and (statuscode != 200):
            scraper = cloudscraper.create_scraper(interpreter = "nodejs", delay = scrapecount * 6, debug = False)

            page = scraper.get(url)
            statuscode = page.status_code

            logger.debug(
                f"Status {statuscode} for bot {bot_id}"
            )

            if statuscode == 200:
                data = json.loads(page.text)
                logger.info("Fetched %s 3C shared bot data OK" % (bot_id))

            scrapecount += 1
        
        if statuscode != 200:
            data = None
            logger.error("Failed to fetch %s 3C shared bot data" % (bot_id))

    except json.decoder.JSONDecodeError as err:
        logger.error(f"Shared bot data ({bot_id}) is not valid json")

    return data