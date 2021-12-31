"""Cyberjunky's 3Commas bot helpers."""
import requests


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


def get_lunarcrush_data(logger, program, lcapikey, usdtbtcprice):
    """Get the top x GalaxyScore or AltRank coins from LunarCrush."""

    lccoins = {}
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
