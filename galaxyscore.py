#!/usr/bin/env python3
import sys
import time

import requests
from py3cw.request import Py3CW

import config

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


def get_binance_ticker():
    """Get the valid symbols from Binance."""
    tickerList = []

    result = requests.get("https://api.binance.com/api/v3/ticker/price")
    if result:
        print("Fetching ticker prices OK")
        ticker = result.json()
        for entry in ticker:
            coin = entry["symbol"]
#            print(coin)
            tickerList.append(coin)

        return tickerList
    else:
        print("Fetching ticker prices failed")


def get_galaxyscore():
    """Get the top 10 GalaxyScore from LunarCrush."""
    tmpList = list()
    url = "https://api.lunarcrush.com/v2?data=market&key={0}&limit=10&sort=gs&desc=true".format(config.LunarCrushApiKey)

    result = requests.get(url)
    if result:
        print("Fetching Top 10 GalaxyScore OK")
        top10 = result.json()
        for entry in top10["data"]:
            coin = entry["s"]
            tmpList.append(coin)

        return tmpList
    else:
        print("Fetching Top 10 GalaxyScore failed")
        sys.exit()


def get_blacklist():
    """Get the pair blacklist from 3Commas."""
    error, data = p3cw.request(entity="bots", action="pairs_black_list", action_id="")
    if not error:
        return data["pairs"]
    else:
        print(error)
        sys.exit()


def update_bots_pairs(bot):
    """Update all specified bots with new pairs."""
    newpairsList = list()

    base = bot["pairs"][0].split("_")[0]
#    print(base)

    for coin in galaxyScoreList:
        tick = coin + base
        pair = base + "_" + coin
#        print(tick)
#        print(pair)
        if tick in tickerList:
            if pair in blackList:
                print("%s is on blacklist, skipping." % pair)
            else:
                newpairsList.append(pair)

#    print(newpairsList)
#    print(bot["pairs"])

    if newpairsList == bot["pairs"]:
        print("Bot is already using same pairs, skipping.")
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
            print(error)
            sys.exit()
        else:
            print(data)
            print("Bot named '%s' with id %s updated to use pairs %s" % (str(bot["name"]), str(bot["id"]), newpairsList))
    else:
        print("No new pairs with market data!")


while True:
    result = time.strftime("%A %H:%M:%S %d-%m-%Y")
    print("3Commas GalaxyScore bot. Started at %s" % result)

    # Update binance ticker/market
    tickerList = get_binance_ticker()
    print("%d symbols loaded from Binance ticker" % len(tickerList))

    # Get Top10 GalaxyScore coins
    galaxyScoreList = get_galaxyscore()
    print(galaxyScoreList)

    # Update 3Commas black list
    blackList = get_blacklist()
    print("%d symbols loaded from 3Commas blacklist" % len(blackList))

    # Walk through all bots specified
    for bot in botIds:
        error, data = p3cw.request(entity="bots", action="show", action_id=str(bot))
        try:
            print("Updating 3Commas bot(s)")
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
