"""Cyberjunky's 3Commas bot helpers."""
import datetime
import time
import json
import requests
from bs4 import BeautifulSoup

from constants.pair import PAIREXCLUDE_EXT


def wait_time_interval(logger, notification, time_interval, notify=True):
    """Wait for time interval."""

    if time_interval>0:
        localtime = time.time()
        nexttime = localtime + int(time_interval)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info(
            "Next update in %s at %s" % (str(datetime.timedelta(seconds=time_interval)), timeresult), notify
        )
        notification.send_notification()
        time.sleep(time_interval)
        return True

    notification.send_notification()
    time.sleep(2)

    return False


def populate_pair_lists(pair, blacklist, blackpairs, badpairs, newpairs, tickerlist):
    """Create pair lists."""

    # Check if pair is in tickerlist and on 3Commas blacklist
    if pair in tickerlist:
        if pair in blacklist:
            blackpairs.append(pair)
        else:
            newpairs.append(pair)
    else:
        badpairs.append(pair)


def get_lunarcrush_data(logger, program, config, usdtbtcprice):
    """Get the top x GalaxyScore, AltRank or Volatile coins from LunarCrush."""

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
    elif "galaxyscore" in program:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "gs",
            "limit": lcfetchlimit,
            "key": lcapikey,
            "desc": True,
        }
    elif "volatility" in program:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "vt",
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


def get_coinmarketcap_data(logger, cmc_apikey, start_number, limit, convert):
    """Get the data from CoinMarketCap."""

    cmcdict = {}
    errorcode = -1
    errormessage = ""

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
            errorcode = data['status']['error_code']
            errormessage = data['status']['error_message']
    except requests.exceptions.HTTPError as err:
        logger.error("Fetching CoinMarketCap data failed with error: %s" % err)
        return {}

    logger.info("Fetched CoinMarketCap data OK (%s coins)" % (len(cmcdict)))

    return errorcode, errormessage, cmcdict


def check_deal(cursor, dealid):
    """Check if deal was already logged."""

    return cursor.execute(f"SELECT * FROM deals WHERE dealid = {dealid}").fetchone()


def format_pair(marketcode, base, coin):
    """Format pair depending on exchange."""

    # Construct pair based on bot settings (BTC stays BTC, but USDT can become BUSD)
    if marketcode == "binance_futures":
        pair = f"{base}_{coin}{base}"
    elif marketcode == "ftx_futures":
        pair = f"{base}_{coin}-PERP"
    else:
        pair = f"{base}_{coin}"

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

        columncount = 0
        columndict = {}

        # Build list of columns we are interested in
        tablecolumns = data.find_all("th")
        for column in tablecolumns:
            if column.text not in ("#", "symbol"):
                columndict[columncount] = column.text

            columncount += 1

        tablerows = data.find_all("tr")
        for row in tablerows:
            rowcolums = row.find_all("td")
            if len(rowcolums)>0:
                rank = int(rowcolums[0].text)
                if rank<start_number:
                    continue

                pairdata = {}

                # Iterate over the available columns and collect the data
                for key, value in columndict.items():
                    if value == "24h volume":
                        pairdata[value] = float(
                            rowcolums[key].text.replace(" BTC", "").replace(",", "")
                        )
                    else:
                        pairdata[value] = rowcolums[key].text.replace("\n", "").replace("%", "")

                logger.debug(f"Rank {rank}: {pairdata}")
                pairs.append(pairdata)

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

    url = "https://app.3commas.io/wapi/bots/%s/get_bot_data?secret=%s" % (bot_id, bot_secret)

    data = {}
    try:
        page = requests.get(url)
        if page:
            data = page.json()

    except json.decoder.JSONDecodeError as err:
        logger.error(f"Shared bot data ({bot_id}) is not valid json")
    except requests.exceptions.HTTPError as err:
        logger.error("Fetching 3C shared bot data failed with error: %s" % err)

    logger.info("Fetched %s 3C shared bot data OK" % (bot_id))

    return data


def remove_excluded_pairs(logger, share_dir, bot_id, marketcode, base, newpairs):
    """Remove pairs which are excluded by other script(s)."""

    excludedcoins = load_bot_excluded_coins(logger, share_dir, bot_id, PAIREXCLUDE_EXT)
    if excludedcoins:
        logger.info(
            f"Removing the following coin(s) for bot {bot_id}: {excludedcoins}"
        )

        for coin in excludedcoins:
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, base, coin)
            if newpairs.count(pair)>0:
                newpairs.remove(pair)


def load_bot_excluded_coins(logger, share_dir, bot_id, extension):
    """Load excluded coins from file, for the specified bot"""

    excludedlist = []
    excludefilename = f"{share_dir}/{bot_id}.{extension}"

    try:
        with open(excludefilename, "r") as file:
            excludedlist = file.read().splitlines()
        if excludedlist:
            logger.info(
                "Reading exclude file '%s' OK (%s coins)"
                % (excludefilename, len(excludedlist))
            )
    except FileNotFoundError:
        logger.info(
            "Exclude file (%s) not found for bot '%s'; no coins to exclude."
            % (excludefilename, bot_id)
        )

    return excludedlist


def unix_timestamp_to_string(timestamp, date_time_format):
    """Convert the given timestamp to a readable date/time in the specified format"""

    return datetime.datetime.fromtimestamp(timestamp).strftime(date_time_format)


def calculate_deal_funds(start_bo, start_so, max_so, martingale_volume_coefficient, count_from=1, count_funds_for=1):
    """Calculate the max fund usage of a deal based on the bot settings"""

    # Always add start_base_order_size
    totalusedperdeal = start_bo

    # Funds required for the specified next number of SO
    nextsofunds = 0.0
    nextsofundscounter = 0

    isafetyorder = 1
    while isafetyorder<=max_so:
        # For the first Safety Order, just use the startso
        if isafetyorder == 1:
            total_safety_order_volume = start_so

        # After the first SO, multiply the previous SO with the safety order volume scale
        if isafetyorder>1:
            total_safety_order_volume *= martingale_volume_coefficient

        # Only calculated the funds if current SO is higher than the `count_from`. This
        # could be used to calculate the funds for an already started deal with
        # completed Safety Orders.
        if isafetyorder>=count_from:
            totalusedperdeal += total_safety_order_volume

            if nextsofundscounter<count_funds_for:
                nextsofunds += total_safety_order_volume
                nextsofundscounter += 1

        isafetyorder += 1

    return totalusedperdeal, nextsofunds


def futures_pair(pair):
    pair = "USDT_" + pair.upper() + "USDT"
    return pair


def spot_pair(pair):
    pair = "USDT_" + pair.upper()
    return pair


def back_to_binance(pair):
    """Convert a binance/tradingview formatted pair to threecommas format."""
    a = pair.split("_")
    pair = a[1] + a[0]
    return pair


def binance_pair(pair):
    pair = pair.upper() + "USDT"
    return pair
