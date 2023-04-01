#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import json
import time

import cloudscraper
import requests
from bs4 import BeautifulSoup

def get_lunarcrush_data(logger, program, config, section, usdtbtcprice):
    """Get the top x GalaxyScore, AltRank coins from LunarCrush."""

    lccoins = {}
    lcapikey = config.get(section, "lc-apikey")
    lcfetchlimit = config.get(section, "lc-fetchlimit")

    # Construct headers
    headers = {"Authorization": f"Bearer {lcapikey}"}

    # Construct query for LunarCrush data
    if "altrank" in program:
        parms = {
            "sort": "alt_rank",
            "limit": lcfetchlimit,
            "desc": 0,
        }
    elif "galaxyscore" in program:
        parms = {
            "sort": "galaxy_score",
            "limit": lcfetchlimit,
        }
    else:
        logger.error("Fetching LunarCrush data failed, could not determine datatype to fetch")
        return {}

    try:
        result = requests.request(
            "GET", "https://lunarcrush.com/api3/coins",
            headers=headers,
            params=parms,
            timeout=(3.05, 30.0)
        )
        result.raise_for_status()
        data = result.json()

        if "data" in data.keys():
            for i, crush in enumerate(data["data"], start=1):
                crush["categories"] = (
                    list(crush["categories"].split(",")) if crush["categories"] else []
                )
                crush["rank"] = i
                crush["volbtc"] = crush["v"] / float(usdtbtcprice)
                logger.debug(
                    f"rank:{crush['rank']:3d}  acr:{crush['acr']:4d}   gs:{crush['gs']:3.1f}   "
                    f"s:{crush['s']:8s} '{crush['n']:25}'   volume in btc:{crush['volbtc']:12.2f}"
                    f"   categories:{crush['categories']}"
                )
            lccoins = data["data"]

    except requests.exceptions.HTTPError as err:
        logger.error(
            "Fetching LunarCrush data failed with code %d: %s" %
            (err.response.status_code, err.response.text)
        )
        return {}

    logger.info("Fetched LunarCrush ranking OK (%s coins)" % (len(lccoins)))

    return lccoins


def get_coinmarketcap_data(logger, cmc_apikey, start_number, limit, convert):
    """Get the data from CoinMarketCap."""

    cmcdict = {}
    statuscode = -1
    statusmessage = ""

    # Construct query for CoinMarketCap data
    parms = {
        "start": start_number,
        "limit": limit,
        "convert": convert,
        "aux": "cmc_rank",
    }

    headrs = {
        "X-CMC_PRO_API_KEY": cmc_apikey,
    }

    try:
        result = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
            params=parms,
            headers=headrs,
            timeout=(3.05, 30.0)
        )

        data = result.json()

        if result.ok:
            if "data" in data.keys():
                for i, cmc in enumerate(data["data"], start=1):
                    cmc["rank"] = i
                    logger.debug(
                        f"rank:{cmc['rank']:3d}  cmc_rank:{cmc['cmc_rank']:3d}  s:{cmc['symbol']:8}"
                        f"'{cmc['name']:25}' volume_24h:{cmc['quote'][convert]['volume_24h']:12.2f}"
                        f"volume_change_24h:{cmc['quote'][convert]['volume_change_24h']:5.2f} "
                        f"market_cap:{cmc['quote'][convert]['market_cap']:12.2f}"
                    )
                cmcdict = data["data"]
        else:
            statuscode = data['status']['error_code']
            statusmessage = data['status']['error_message']
    except requests.exceptions.HTTPError as err:
        logger.error(f"Fetching CoinMarketCap data failed with error: {err}")
        return 0, err, {}

    return statuscode, statusmessage, cmcdict


def get_coingecko_data(logger, cg_apikey, start_number, end_number, convert, delay_sec):
    """Get the data from CoinGecko."""

    cgdict = []
    statuscode = -1

    # Construct query for CoinGecko data
    pagecount = 250
    parms = {
        "per_page": pagecount,
        "page": 1,
        "sparkline": False,
        "vs_currency": convert,
        "order": "market_cap_desc",
        "price_change_percentage": "1h,24h,7d,14d,30d,200d,1y"
    }

    if cg_apikey:
        parms["x_cg_pro_api_key"] = cg_apikey

    try:
        # Range from first page number to fetch (always 1 or higher), to page
        # number to stop at (hence the +2)
        for page in range(int(start_number / pagecount) + 1, int(end_number / pagecount) + 2):
            # Optimize a bit, request only the remaining coins on the last page
            if page * pagecount > end_number:
                if end_number < pagecount:
                    # Single page with less than 250 coins requested
                    parms["per_page"] = end_number
                else:
                    # Multiple pages, substract the fetched number of coins from the previous pages
                    parms["per_page"] = end_number - ((page - 1) * pagecount)

            parms["page"] = page

            result = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params=parms,
                timeout=(3.05, 30.0)
            )

            if result.ok:
                data = result.json()
                for coin in data:
                    if coin.get("market_cap_rank") is not None:
                        if int(coin["market_cap_rank"]) < start_number:
                            continue

                        if int(coin["market_cap_rank"]) > end_number:
                            break

                        cgdict.append(coin)
                    else:
                        logger.debug(
                            f"Unprocessable coin without readable market_cap_rank: {coin}"
                        )

                # Prevent rate limit error by waiting a bit for the next request
                time.sleep(delay_sec)
            else:
                statuscode = result.status_code
                break
    except requests.exceptions.HTTPError as err:
        logger.error(f"Fetching CoinGecko data failed with error: {err}")
        return 0, {}

    return statuscode, cgdict


def get_botassist_data(logger, botassistlist, start_number, limit):
    """Get the top pairs from 3c-tools bot-assist explorer."""

    url = "https://www.3c-tools.com/markets/bot-assist-explorer"
    parms = {"list": botassistlist}

    pairs = list()
    try:
        result = requests.get(url, params=parms)
        result.raise_for_status()
        soup = BeautifulSoup(result.text, features="html.parser")
        data = soup.find("table", class_="table table-striped table-sm")

        if data is not None:
            columncount = 0
            columndict = {}

            # Build list of columns we are interested in
            tablecolumns = data.find_all("th")

            for column in tablecolumns:
                if column.text not in ("#"):
                    columndict[columncount] = column.text

                columncount += 1

            tablerows = data.find_all("tr")
            for row in tablerows:
                rowcolums = row.find_all("td")
                if len(rowcolums) > 0:
                    rank = int(rowcolums[0].text)
                    if start_number and rank < start_number:
                        continue

                    pairdata = {}

                    # Iterate over the available columns and collect the data
                    for key, value in columndict.items():
                        if value == "24h volume":
                            pairdata[value] = float(
                                    rowcolums[key].text.replace(" BTC", "").replace(",", "")
                                )
                        elif value == "volatility":
                            pairdata[value] = float(
                                    rowcolums[key].text.replace("%", "").replace(",", "")
                                )
                        else:
                            pairdata[value] = rowcolums[key].text.replace("\n", "")

                    # For some the symbol is unknown, so extract it from the pair
                    if pairdata["symbol"].replace(" ", "") == "-":
                        pairdata["symbol"] = pairdata["pair"].split("_")[1]

                    logger.debug(f"Rank {rank}: {pairdata}")
                    pairs.append(pairdata)

                    if limit and rank == limit:
                        break
        else:
            logger.warning(
                f"Table on {botassistlist} does not have any content (rows/columns). Cannot fetch "
                f"any pairs. This could be ok when no pairs are listed."
            )

    except requests.exceptions.HTTPError as err:
        logger.error("Fetching 3c-tools bot-assist data failed with error: %s" % err)
        if result.status_code == 500:
            logger.error(f"Check if the list setting '{botassistlist}' is correct")

        return pairs

    logger.info(
        f"Fetched 3c-tools {botassistlist} data OK ({len(pairs)} pairs)"
    )

    return pairs


def get_shared_bot_data(logger, bot_id, bot_secret):
    """Get the shared bot data from the 3C website"""

    url = "https://app.3commas.io/wapi/bots/%s/get_bot_data?secret=%s" % (bot_id, bot_secret)

    data = {}
    try:
        statuscode = 0
        scrapecount = 0
        while (scrapecount < 3) and (statuscode != 200):
            scraper = cloudscraper.create_scraper(
                interpreter = "nodejs", delay = scrapecount * 6, debug = False
            )

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

    except json.decoder.JSONDecodeError:
        logger.error(f"Shared bot data ({bot_id}) is not valid json")

    return data
