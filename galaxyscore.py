#!/usr/bin/env python3
import sys
import time
import json
import configparser
import requests
from py3cw.request import Py3CW

import logging
import queue
import threading
import apprise

class NotificationHandler:
    def __init__(self, logger, enabled=False, notify_urls=[]):
        if enabled and notify_urls:
            self.apobj = apprise.Apprise()
            urls = json.loads(notify_urls)
            for url in urls:
                self.apobj.add(url)
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
            logger.info("Notifications are enabled")
        else:
            self.enabled = False
            logger.info("Notifications are disabled")

    def start_worker(self):
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        while True:
            message, attachments = self.queue.get()
            if attachments:
                self.apobj.notify(body=message, attach=attachments)
            else:
                self.apobj.notify(body=message)
            self.queue.task_done()

    def send_notification(self, message, attachments=None):
        if self.enabled:
            self.queue.put((message, attachments or []))

class Logger:

    Logger = None

    def __init__(self, debug_enabled):
        # Logger setup
        self.Logger = logging.getLogger()
        if debug_enabled:
           self.Logger.setLevel(logging.DEBUG)
           self.Logger.propagate = True
        else:
           self.Logger.setLevel(logging.INFO)
           self.Logger.propagate = False
          
        formatter = logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
        # default is "logs/galaxyscore.log"
        fh = logging.FileHandler(f"logs/galaxyscore.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self.Logger.addHandler(fh)

        # logging to console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.Logger.addHandler(ch)

    def log(self, message, level="info"):

        if level == "info":
            self.Logger.info(message)
        elif level == "warning":
            self.Logger.warning(message)
        elif level == "error":
            self.Logger.error(message)
        elif level == "debug":
            self.Logger.debug(message)

    def info(self, message):
        self.log(message, "info")

    def warning(self, message):
        self.log(message, "warning")

    def error(self, message):
        self.log(message, "error")

    def debug(self, message):
        self.log(message, "debug")

def load_config(self):
    """Create default or load existing config file."""
    config = configparser.ConfigParser()
    if config.read("config.ini"):
        return config

    config["main"] = {"debug": False}
    config["galaxyscore"] = {
        "timeinterval": 3600,
        "numberofpairs": 10,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API secret",
        "lc-apikey": "Your LunarCrush API key",
        "botids": [ 12345, 67890 ],
        "notifications": False,
        "notify-urls": [ "notify-url1", "notify-url2" ],
    }
    with open("config.ini", "w") as configfile:
        config.write(configfile)
    return None

def init_3c_api(self):
    return Py3CW(
        key=self.config.get("galaxyscore", "3c-apikey"),
        secret=self.config.get("galaxyscore", "3c-apisecret"),
        request_options={
            "request_timeout": 10,
            "nr_of_retries": 3,
            "retry_status_codes": [502],
        },
    )

def get_binance_market(self):
    """Get all the valid pairs from Binance."""
    tickerList = []

    result = requests.get("https://api.binance.com/api/v3/ticker/price")
    if result:
        ticker = result.json()
        for entry in ticker:
            coin = entry["symbol"]
            self.logger.debug("Market data coin: %s" % coin)
            tickerList.append(coin)
        self.logger.info("Fetched Binance market data OK (%s pairs)" % len(tickerList))

        return tickerList
    else:
        self.logger.error("Fetching Binance market data failed with error: %s" % error)


def get_ftx_market(self):
    """Get all the valid pairs from FTX."""
    tickerList = []

    result = requests.get("https://ftx.com/api/markets")
    if result:
        ticker = result.json()
        for entry in ticker["result"]:
            if entry["type"] == "spot":
               coin = entry["name"].replace("/","")
               self.logger.debug("Market data coin: %s" % coin)
               tickerList.append(coin)
        self.logger.info("Fetched FTX market data OK (%s pairs)" % len(tickerList))

        return tickerList
    else:
        self.logger.error("Fetching FTX market data failed with error: %s" % error)

def get_galaxyscore(self):
    """Get the top x GalaxyScore from LunarCrush."""
    tmpList = list()
    url = "https://api.lunarcrush.com/v2?data=market&key={0}&limit=50&sort=gs&desc=true".format(self.config.get("galaxyscore", "lc-apikey"))
    try:
        result = requests.get(url)
        if result:
            topX = result.json()
            for entry in topX["data"]:
                coin = entry["s"]
                tmpList.append(coin)
            self.logger.info("Fetched LunarCrush Top X GalaxyScore OK (%s coins)" % len(tmpList))

            return tmpList
        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
            self.logger.error("Fetching LunarCrush Top X GalaxyScore failed with error: %s" % err)
            sys.exit()


def get_blacklist(self):
    """Get the pair blacklist from 3Commas."""
    error, data = self.api.request(entity="bots", action="pairs_black_list", action_id="")
    if data:
        self.logger.info("Fetched 3Commas pairs blacklist OK (%s pairs)" % len(data["pairs"]))
        return data["pairs"]
    else:
        self.logger.error("Fetching 3Commas pairs blacklist failed with error: %s" % error)
        sys.exit()


def update_bots_pairs(self, bot):
    """Update all specified bots with new pairs."""
    newpairslist = list()
    badpairslist = list()
    blackpairslist = list()

    exchange = bot["account_name"]

    self.logger.info("Finding the best pairs for %s exchange" % exchange)
    base = bot["pairs"][0].split("_")[0]
    self.logger.debug("Base coin for this bot: %s" % base)

    if exchange == "Binance":
        tickerlist = self.binancetickerlist
    elif exchange == "FTX":
        tickerlist = self.ftxtickerlist
    elif 'Paper Account' in exchange:
        tickerlist = self.binancetickerlist
    else:
        self.logger.error("Bot is using the %s exchange which is not implemented yet!" % exchange)
        sys.exit()

    for coin in self.galaxyscorelist:
        tick = coin + base
        pair = base + "_" + coin
        self.logger.debug("Market  pair: %s" % tick)
        self.logger.debug("3Commas pair: %s" % pair)

        if tick in tickerlist:
            if pair in self.blacklist:
                blackpairslist.append(pair)
            else:
                newpairslist.append(pair)
        else:
            badpairslist.append(pair)

        if len(newpairslist) == int(self.config.get("galaxyscore", "numberofpairs")):
            break

    if blackpairslist:
        self.logger.debug("These pairs are on your 3Commas blacklist and were skipped: %s" % blackpairslist)
    if badpairslist:
        self.logger.debug("There pairs are not valid on %s market and were skipped: %s" % (exchange, badpairslist))

    self.logger.debug("New     pairs: %s:" % newpairslist)
    self.logger.debug("Current pairs: %s" % bot["pairs"])

    if newpairslist == bot["pairs"]:
        self.logger.info("Bot '%s' is already using the best pairs, skipping bot update." % bot['name'])
        self.notificationhandler.send_notification("Bot '%s' is already using the best pairs, skipping bot update." % bot['name'])
        return
        
    if newpairslist:
        self.logger.info("Updating your 3Commas bot(s)")
        error, data = self.api.request(
            entity="bots",
            action="update",
            action_id=str(bot["id"]),
            payload={
                "name": str(bot["name"]),
                "pairs": newpairslist,
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
                "max_active_deals": int(bot["max_active_deals"]),
                "active_safety_orders_count": int(bot["active_safety_orders_count"]),
                "safety_order_step_percentage": float(
                    bot["safety_order_step_percentage"]
                ),
                "take_profit_type": bot["take_profit_type"],
                "strategy_list": bot["strategy_list"],
                "bot_id": int(bot["id"]),
            },
        )
        if data:
            self.logger.debug("Bot updated: %s" % data)
            self.logger.info("Bot '%s' updated with these pairs:" % bot["name"])
            self.logger.info(newpairslist)
            self.notificationhandler.send_notification("Bot '%s' updated with these pairs: %s" % (bot['name'], newpairslist))
        else:
            self.logger.error("Error occurred while updating bot '%s' error: %s" % (str(bot["name"]), error))
    else:
        self.logger.info("None of the GalaxyScore pairs found on %s exchange!" % exchange)

class Main:
    """Main class, start of application."""

    def __init__(self):
        self.binancetickerlist = list()
        self.ftxtickerlist = list()

        result = time.strftime("%A %H:%M:%S %d-%m-%Y")
        # Create or load configuration file
        self.config = load_config(self)
        if not self.config:
           self.logger = Logger(False)
           self.logger.info("3Commas GalaxyScore bot helper!")
           self.logger.info("Started at %s." % result)
           self.logger.info("Created example config file 'config.ini', edit it and restart the program.")
           sys.exit(0)
        else:
           # Init logging
           self.debug_enabled = self.config.getboolean("main", "debug")
           self.logger = Logger(self.debug_enabled)
           self.logger.info("3Commas GalaxyScore bot helper!")
           self.logger.info("Started at %s" % result)
           self.logger.info("Loaded configuration from 'config.ini'")

        # Init notification handler
        self.notificationhandler = NotificationHandler(self.logger, self.config.getboolean("galaxyscore", "notifications"), self.config.get("galaxyscore", "notify-urls"))

        self.api = init_3c_api(self)
        botids = json.loads(self.config.get("galaxyscore", "botids"))

        while True:

            # Get exchange markets
            self.binancetickerlist = get_binance_market(self)
            self.ftxtickerlist = get_ftx_market(self)

            # Get Top10 GalaxyScore coins
            self.galaxyscorelist = get_galaxyscore(self)

            # Update 3Commas black list
            self.blacklist = get_blacklist(self)

            # Walk through all bots specified
            for bot in botids:
                error, data = self.api.request(entity="bots", action="show", action_id=str(bot))
                try:
                    update_bots_pairs(self, data)
                except Exception as e:
                    self.logger.error("Error occurred while updating bot with id %s: %s " % (bot,e))
                    sys.exit()

            timeinterval = int(self.config.get("galaxyscore", "timeinterval"))

            if timeinterval > 0:
                localtime = time.time()
                nexttime = localtime + int(timeinterval)
                result = time.strftime("%H:%M:%S", time.localtime(nexttime))
                self.logger.info("Next update in %s Seconds at %s" % (timeinterval, result))
                self.notificationhandler.send_notification("Next update in %s Seconds at %s" % (timeinterval, result))
                time.sleep(timeinterval)
            else:
                break

# Start application
Main()
