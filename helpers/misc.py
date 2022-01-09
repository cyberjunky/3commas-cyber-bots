"""Cyberjunky's 3Commas bot helpers."""
import time

import requests


def wait_time_interval(logger, notification, time_interval):
    """Wait for time interval."""

    if time_interval > 0:
        localtime = time.time()
        nexttime = localtime + int(time_interval)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info(
            "Next update in %s Seconds at %s" % (time_interval, timeresult), True
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

    # Construct query for LunarCrush data
    if "altrank" in program:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "acr",
            "limit": 100,
            "key": lcapikey,
        }
    else:
        parms = {
            "data": "market",
            "type": "fast",
            "sort": "gs",
            "limit": 100,
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


def get_coinmarketcap_data(logger, config):
    """Get the data from CoinMarketCap."""

    cmcdict = {}

    startnumber = int(config.get("settings", "start-number"))
    endnumber = 1 + (int(config.get("settings", "end-number")) - startnumber)

    # Construct query for CoinMarketCap data
    parms = {
        "start": startnumber,
        "limit": endnumber,
        "convert": "BTC",
        "aux": "cmc_rank",
    }

    headrs = {
        "X-CMC_PRO_API_KEY": config.get("settings", "cmc-apikey"),
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
    logger.debug(f"CMC data: {cmcdict}")

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
