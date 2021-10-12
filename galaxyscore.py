#!/usr/bin/env python3
import sys
import time

import requests
from py3cw.request import Py3CW

import config

import logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger()

botIds = config.BotIds
galaxyScoreList = list()
tickerList = list()
blackList = list()

p3cw = Py3CW(
    key=config.ApiKeys["apiKey"],
    secret=config.ApiKeys["apiSecret"],
    request_options={
        "request_timeout": 10,
        "nr_of_retries": 1,
        "retry_status_codes": [502],
    },
)


def get_binance_market():
    """Get all the valid pairs from Binance."""
    tickerList = []

    result = requests.get("https://api.binance.com/api/v3/ticker/price")
    if result:
        print("Fetched Binance market data OK")
        ticker = result.json()
        for entry in ticker:
            coin = entry["symbol"]
            logger.debug("Market data coin: %s" % coin)
            tickerList.append(coin)

        return tickerList
    else:
        print("Fetching Binance market data failed with error; %s" % error)


def get_galaxyscore():
    """Get the top 10 GalaxyScore from LunarCrush."""
    tmpList = list()
    url = "https://api.lunarcrush.com/v2?data=market&key={0}&limit=10&sort=gs&desc=true".format(config.LunarCrushApiKey)

    result = requests.get(url)
    if result:
        print("Fetched LunarCrush Top 10 GalaxyScore OK")
        top10 = result.json()
        for entry in top10["data"]:
            coin = entry["s"]
            tmpList.append(coin)

        return tmpList
    else:
        print("Fetching LunarCrush Top 10 GalaxyScore failed with error: %s" % error)
        sys.exit()


def get_blacklist():
    """Get the pair blacklist from 3Commas."""
    error, data = p3cw.request(entity="bots", action="pairs_black_list", action_id="")
    if result:
        print("Fetched 3Commas pairs blacklist OK")
        return data["pairs"]
    else:
        print("Fetching 3Commas pairs blacklist failed with error: %s" % error)
        sys.exit()


def update_bots_pairs(bot):
    """Update all specified bots with new pairs."""
    newpairsList = list()

    base = bot["pairs"][0].split("_")[0]
    logger.debug(base)

    for coin in galaxyScoreList:
        tick = coin + base
        pair = base + "_" + coin
        logger.debug("Binance pair: %s" % tick)
        logger.debug("3Commas pair: %s" % pair)
        if tick in tickerList:
            if pair in blackList:
                print("%s pair is on your 3Commas blacklist, skipping." % pair)
            else:
                newpairsList.append(pair)

    logger.debug("New     pairs: %s:" % newpairsList)
    logger.debug("Current pairs: %s" % bot["pairs"])

    if newpairsList == bot["pairs"]:
        print("Bot '%s' is already using the same pairs, skipping update." % bot['name'])
        return
        
    if newpairsList:
        error, data = p3cw.request(
            entity="bots",
            action="update",
            action_id=str(bot["id"]),
            payload={
                "name": str(bot["name"]),
                "pairs": newpairsList,
                "base_order_volume": float(bot["base_order_volume"]),
                "take_profit": float(bot["take_profit"]),
                "safety_order_volume": float(bot["safety_order_volume"]),
                "martingale_volume_coefficient": float(
                    bot["martingale_volume_coefficient"]
                ),
                "martingale_step_coefficient": float(
                    bot["martingale_step_coefficient"]
                ),
                "max_safety_orders": int(bot["max_safety_orders"]),
                "active_safety_orders_count": int(bot["active_safety_orders_count"]),
                "safety_order_step_percentage": float(
                    bot["safety_order_step_percentage"]
                ),
                "take_profit_type": bot["take_profit_type"],
                "strategy_list": bot["strategy_list"],
                "bot_id": int(bot["id"]),
            },
        )
        if error:
            logger.error("Error occurred while updating bot '%s' error: %s" % (bot['name'], error))
            sys.exit()
        else:
            logger.debug("Bot updated with these settings: %s" % data)
            print("Bot named '%s' with id %s updated to use pairs %s" % (str(bot["name"]), str(bot["id"]), newpairsList))
    else:
        print("No new pairs with market data found!")


while True:
    result = time.strftime("%A %H:%M:%S %d-%m-%Y")
    print("3Commas GalaxyScore bot. Started at %s" % result)

    # Update binance markets
    tickerList = get_binance_market()
    print("%d symbols loaded from Binance market" % len(tickerList))

    # Get Top10 GalaxyScore coins
    galaxyScoreList = get_galaxyscore()
    logger.debug("GalaxyScores candidates found: %s" % galaxyScoreList)

    # Update 3Commas black list
    blackList = get_blacklist()
    print("%d symbols loaded from 3Commas blacklist" % len(blackList))

    # Walk through all bots specified
    for bot in botIds:
        error, data = p3cw.request(entity="bots", action="show", action_id=str(bot))
        try:
            print("Updating the 3Commas bot(s)")
            update_bots_pairs(data)
        except Exception as e:
            print("Error occurred while updating bot: %s " % e)
            sys.exit()

    if config.timeInterval > 0:
        localtime = time.time()
        nexttime = localtime + int(config.timeInterval)
        result = time.strftime("%A %H:%M:%S %d-%m-%Y", time.localtime(nexttime))
        print("Next bot(s) update in %s seconds at %s." % (config.timeInterval, result))
        time.sleep(config.timeInterval)
    else:
        break
