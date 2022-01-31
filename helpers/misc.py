"""Cyberjunky's 3Commas bot helpers."""
import time

import requests
from bs4 import BeautifulSoup


def wait_time_interval(logger, notification, time_interval, notify=True):
    """Wait for time interval."""

    if time_interval > 0:
        localtime = time.time()
        nexttime = localtime + int(time_interval)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info(
            "Next update in %s Seconds at %s" % (time_interval, timeresult), notify
        )
        notification.send_notification()
        time.sleep(time_interval)
        return True

    notification.send_notification()
    time.sleep(2)

    return False


def populate_pair_lists(pair, blacklist, blackpairs, badpairs, newpairs, tickerlist):
    """Check pair conditions."""

    # Check if pair is in tickerlist and on 3Commas blacklist
    if pair in tickerlist:
        if pair in blacklist:
            blackpairs.append(pair)
        else:
            newpairs.append(pair)
    else:
        badpairs.append(pair)


def get_lunarcrush_data(logger, program, config, usdtbtcprice):
    """Get the top x GalaxyScore or AltRank coins from LunarCrush."""

    lccoins = {}
    lcapikey = config.get("settings", "lc-apikey")
    lcfetchlimit = config.get("settings", "lc-fetchlimit")

    # Construct query for LunarCrush data
    if "altrank" in program:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "acr",
            "limit": lcfetchlimit,
            "key": lcapikey,
        }
    else:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "gs",
            "limit": lcfetchlimit,
            "key": lcapikey,
            "desc": True,
        }

    try:
        result = requests.get("https://api.lunarcrush.com/v2", params=parms)
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
        logger.error("Fetching LunarCrush data failed with error: %s" % err)
        return {}

    logger.info("Fetched LunarCrush ranking OK (%s coins)" % (len(lccoins)))

    return lccoins


def get_coinmarketcap_data(logger, cmc_apikey, start_number, limit):
    """Get the data from CoinMarketCap."""

    cmcdict = {}

    # Construct query for CoinMarketCap data
    parms = {
        "start": start_number,
        "limit": limit,
        "convert": "BTC",
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
        )
        result.raise_for_status()
        data = result.json()

        if "data" in data.keys():
            for i, cmc in enumerate(data["data"], start=1):
                cmc["rank"] = i
                logger.debug(
                    f"rank:{cmc['rank']:3d}  cmc_rank:{cmc['cmc_rank']:3d}  s:{cmc['symbol']:8}  "
                    f"'{cmc['name']:25}' volume_24h:{cmc['quote']['BTC']['volume_24h']:12.2f}  "
                    f"volume_change_24h:{cmc['quote']['BTC']['volume_change_24h']:5.2f}  "
                    f"market_cap:{cmc['quote']['BTC']['market_cap']:12.2f}"
                )
            cmcdict = data["data"]

    except requests.exceptions.HTTPError as err:
        logger.error("Fetching CoinMarketCap data failed with error: %s" % err)
        return {}

    logger.info("Fetched CoinMarketCap data OK (%s coins)" % (len(cmcdict)))

    return cmcdict


def check_deal(cursor, dealid):
    """Check if deal was already logged."""

    return cursor.execute(f"SELECT * FROM deals WHERE dealid = {dealid}").fetchone()


def format_pair(logger, marketcode, base, coin):
    """Check if deal was already logged."""

    # Construct pair based on bot settings (BTC stays BTC, but USDT can become BUSD)
    if marketcode == "binance_futures":
        pair = f"{base}_{coin}{base}"
    elif marketcode == "ftx_futures":
        pair = f"{base}_{coin}-PERP"
    else:
        pair = f"{base}_{coin}"

    logger.debug("New pair constructed: %s" % pair)

    return pair


def get_round_digits(pair):
    """Get the number of digits for the round function."""

    numberofdigits = 4

    if pair:
        base = pair.split("_")[0]

        if base in ("BTC", "BNB", "ETH"):
            numberofdigits = 8

    return numberofdigits


def remove_prefix(text, prefix):
    """Get the string without prefix, required for Python < 3.9."""

    if text.startswith(prefix):
        return text[len(prefix):]
    return text


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
        tablerows = data.find_all("tr")

        for row in tablerows:
            rowcolums = row.find_all("td")
            if len(rowcolums) > 0:
                rank = int(rowcolums[0].text)
                if rank < start_number:
                    continue

                pair = rowcolums[1].text
                logger.debug(f"rank:{rank:3d} pair:{pair:10}")
                pairs.append(pair)

                if rank == limit:
                    break

    except requests.exceptions.HTTPError as err:
        logger.error("Fetching 3c-tools bot-assist data failed with error: %s" % err)
        if result.status_code == 500:
            logger.error(f"Check if the list setting '{botassistlist}' is correct")

        return pairs

    logger.info("Fetched 3c-tools bot-assist data OK (%s pairs)" % (len(pairs)))

    return pairs


def get_shared_bot_data(logger, bot_id, bot_secret):
    """Get the shared bot data from the 3C website"""

    url = "https://3commas.io/bots/%s/shared_show?secret=%s" % (bot_id, bot_secret)

    data = {}
    try:
        page = requests.get(url, params={})
        #page.raise_for_status()

        print(page.content)
        #soup = BeautifulSoup(page.content, features="html.parser")
        #print(soup)
        #maincontent = soup.find("div", id="js-bot_info_container")
        #print(maincontent.prettify())

        #bodyblock = soup.find_all("div", class_="content-block__body")

        #for body in bodyblock:
        #    print(body.prettify())
        #    datatable = body.find("tbody")
        #    tablerows = datatable.find_all("tr")

        #    for row in tablerows:
        #        rowcolums = row.find_all("td")
        #        if len(rowcolums) == 2:
        #            data[rowcolums[0].text] = rowcolums[1].txt

    except requests.exceptions.HTTPError as err:
        logger.error("Fetching 3C shared bot data failed with error: %s" % err)
        if result.status_code == 404:
            logger.error(f"Check if the bot id '{bot_id}' is correct and still shared")

        return data

    logger.info("Fetched %s 3C shared bot data OK" % (bot_id))

    return data
