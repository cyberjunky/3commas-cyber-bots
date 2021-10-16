#!/usr/bin/env python3
"""3Commas helper bot."""
import configparser
import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

import apprise
import requests
from py3cw.request import Py3CW


class NotificationHandler:
    """Notification class."""

    def __init__(self, botname, enabled=False, notify_urls=[]):
        self.botname = botname
        if enabled and notify_urls:
            self.apobj = apprise.Apprise()
            urls = json.loads(notify_urls)
            for url in urls:
                self.apobj.add(url)
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
        else:
            self.enabled = False

    def start_worker(self):
        """Start notification worker."""
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        """Process the queue."""
        while True:
            message, attachments = self.queue.get()
            if attachments:
                self.apobj.notify(body=message, attach=attachments)
            else:
                self.apobj.notify(body=message)
            self.queue.task_done()

    def send_notification(self, message, attachments=None):
        """Send a notification if enabled."""
        if self.enabled:
            msg = f"[3Commas {self.botname} bot helper]\n" + message
            self.queue.put((msg, attachments or []))


class Logger:
    """Logger class."""

    my_logger = None

    def __init__(self, botname, notificationhandler, debug_enabled, notify_enabled):
        """Logger init."""
        self.my_logger = logging.getLogger(botname)
        self.notify_enabled = notify_enabled
        self.notificationhandler = notificationhandler
        if debug_enabled:
            self.my_logger.setLevel(logging.DEBUG)
            self.my_logger.propagate = True
        else:
            self.my_logger.setLevel(logging.INFO)
            self.my_logger.propagate = False

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        # Create directory if not exists
        if not os.path.exists("logs"):
            os.makedirs("logs")
        # Logging to file
        file_handle = logging.FileHandler(f"logs/{botname}.log")
        file_handle.setLevel(logging.DEBUG)
        file_handle.setFormatter(formatter)
        self.my_logger.addHandler(file_handle)

        # Logging to console
        console_handle = logging.StreamHandler()
        console_handle.setLevel(logging.INFO)
        console_handle.setFormatter(formatter)
        self.my_logger.addHandler(console_handle)

    def log(self, message, level="info"):
        """Call the log levels."""
        if level == "info":
            self.my_logger.info(message)
        elif level == "warning":
            self.my_logger.warning(message)
        elif level == "error":
            self.my_logger.error(message)
        elif level == "debug":
            self.my_logger.debug(message)

    def info(self, message, notify=False):
        """Info level."""
        self.log(message, "info")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)

    def warning(self, message, notify=False):
        """Warning level."""
        self.log(message, "warning")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)

    def error(self, message, notify=False):
        """Error level."""
        self.log(message, "error")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)

    def debug(self, message, notify=False):
        """Debug level."""
        self.log(message, "debug")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)


def load_config(self):
    """Create default or load existing config file."""
    config = configparser.ConfigParser()
    if config.read(f"{self.botname}.ini"):
        return config

    config["settings"] = {
        "timeinterval": 3600,
        "debug": False,
        "botids": [12345, 67890],
        "numberofpairs": 10,
        "accountmode": "paper",
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API secret",
        "lc-apikey": "Your LunarCrush API key",
        "notifications": False,
        "notify-urls": ["notify-url1", "notify-url2"],
    }
    with open(f"{self.botname}.ini", "w") as configfile:
        config.write(configfile)
    return None


def init_threecommas_api(self):
    """Init the 3commas API."""
    return Py3CW(
        key=self.config.get("settings", "3c-apikey"),
        secret=self.config.get("settings", "3c-apisecret"),
        request_options={
            "request_timeout": 10,
            "nr_of_retries": 3,
            "retry_status_codes": [502],
        },
    )


def get_threecommas_market(self, market_code):
    """Get all the valid pairs for market_code from 3Commas account."""

    tickerlist = []
    error, data = self.api.request(
        entity="accounts",
        action="market_pairs",
        payload={"market_code": market_code},
        additional_headers={"Forced-Mode": self.accountmode},
    )
    if data:
        tickerlist = data
        self.logger.info(
            "Fetched 3Commas market data for %s OK (%s pairs)"
            % (market_code, len(tickerlist))
        )
    else:
        self.logger.error("Fetching 3Commas market data failed with error: %s" % error["msg"])

    return tickerlist


def get_threecommas_btcusd(self):
    """Get current USDT_BTC value to calculate BTC volume24h in USDT."""

    price = 60000
    error, data = self.api.request(
        entity="accounts",
        action="currency_rates",
        payload={"market_code": "binance", "pair": "USDT_BTC"},
        additional_headers={"Forced-Mode": self.accountmode},
    )
    if data:
        self.logger.info("Fetched 3Commas BTC price in USDT %s OK" % data["last"])
        price = data["last"]
    else:
        self.logger.error(
            "Fetching 3Commas BTC price in USDT failed with error: %s" % error['msg']
        )

    return price


def get_threecommas_blacklist(self):
    """Get the pair blacklist from 3Commas."""

    blacklist = list()
    error, data = self.api.request(
        entity="bots", action="pairs_black_list", action_id=""
    )
    if data:
        self.logger.info(
            "Fetched 3Commas pairs blacklist OK (%s pairs)" % len(data["pairs"])
        )
        blacklist = data["pairs"]
    else:
        self.logger.error("Fetching 3Commas pairs blacklist failed with error: %s" % error["msg"])

    return blacklist


def get_lunarcrush_data(self):
    """Get the top x GalaxyScore or AltRank from LunarCrush."""

    scoredict = {}

    # Select correct Top X type
    if self.botname == "altrank":
        ranktype = "ar"
    else:
        ranktype = "gs"

    url = "https://api.lunarcrush.com/v2?data=market&key={0}&limit=50&sort={1}&desc=true&type=fast".format(
        self.config.get("settings", "lc-apikey"), ranktype
    )
    try:
        result = requests.get(url)
        if result:
            data = result.json()
            for entry in data["data"]:
                coin = entry["s"]
                if ranktype == "ar":
                    score = float(entry["acr"])
                else:
                    score = float(entry["gs"])
                volume = float(entry["v"]) / float(self.usdtbtc)
                scoredict[coin] = volume
                self.logger.debug(
                    "Coin: %s score: %s volume USD: %s volume BTC: %s value USDTBTC: %s"
                    % (coin, score, entry["v"], str(volume), str(self.usdtbtc))
                )
            self.logger.info(
                "Fetched LunarCrush Top X %s OK (%s coins)" % (ranktype, len(scoredict))
            )

        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
        self.logger.error(
            "Fetching LunarCrush Top X %s failed with error: %s" % (ranktype, err)
        )

    return scoredict


def find_pairs(self, bot):
    """Determine new pairs and update the bot."""
    newpairslist = list()
    badpairslist = list()
    blackpairslist = list()

    base = bot["pairs"][0].split("_")[0]
    exchange = bot["account_name"]
    minvolume = bot["min_volume_btc_24h"]
    self.logger.debug("Base coin for this bot: %s" % base)
    self.logger.debug("Exchange for this bot: %s" % exchange)
    self.logger.debug("Minimal 24h volume in BTC for this bot: %s" % minvolume)
    self.logger.info("Finding the best pairs for %s exchange" % exchange)

    if (
        exchange == "Binance"
        or "Paper Account" in exchange
        or self.accountmode == "paper"
    ):
        tickerlist = get_threecommas_market(self, "binance")
    elif exchange == "FTX":
        tickerlist = get_threecommas_market(self, "ftx")
    else:
        self.logger.error(
            "Bot is using the %s exchange which is not implemented yet!" % exchange
        )
        sys.exit()

    for coin in self.lunacrush.keys():
        pair = base + "_" + coin

        # Check if coin has minimum 24h volume
        if float(self.lunacrush[coin]) < float(minvolume):
            self.logger.debug(
                "%s has to low volume %s" % (coin, str(self.lunacrush[coin]))
            )
        else:
            self.logger.debug(
                "%s has enough volume %s" % (coin, str(self.lunacrush[coin]))
            )

        # Check if pair is on 3Commas blacklist
        if pair in tickerlist:
            if pair in self.blacklist:
                blackpairslist.append(pair)
            else:
                newpairslist.append(pair)
        else:
            badpairslist.append(pair)

        # Did we get enough pairs already?
        if len(newpairslist) == int(self.config.get("settings", "numberofpairs")):
            break

    self.logger.debug(
        "These pairs are on your 3Commas blacklist and were skipped: %s"
        % blackpairslist
    )
    self.logger.debug(
        "There pairs are not valid on the %s market according to 3Commas and were skipped: %s"
        % (exchange, badpairslist)
    )

    self.logger.debug("New     pairs: %s" % newpairslist)
    self.logger.debug("Current pairs: %s" % bot["pairs"])

    # Do we already use these pairs?
    if newpairslist == bot["pairs"]:
        self.logger.info(
            "Bot '%s' with id '%s' is already using the best pairs"
            % (bot["name"], bot["id"]), True
        )

    # We have new pairs for our bot update it
    if newpairslist:
        self.logger.info("Updating your 3Commas bot(s)")
        update_bot(self, bot, newpairslist)
    else:
        self.logger.info(
            "None of the by LunarCrush suggested pairs found on %s exchange!" % exchange
        )


def update_bot(self, bot, newpairs):
    """Update bot with new pairs."""
    error, data = self.api.request(
        entity="bots",
        action="update",
        action_id=str(bot["id"]),
        additional_headers={"Forced-Mode": self.accountmode},
        payload={
            "name": str(bot["name"]),
            "pairs": newpairs,
            "base_order_volume": float(bot["base_order_volume"]),
            "take_profit": float(bot["take_profit"]),
            "safety_order_volume": float(bot["safety_order_volume"]),
            "martingale_volume_coefficient": float(
                bot["martingale_volume_coefficient"]
            ),
            "martingale_step_coefficient": float(bot["martingale_step_coefficient"]),
            "max_safety_orders": int(bot["max_safety_orders"]),
            "max_active_deals": int(bot["max_active_deals"]),
            "active_safety_orders_count": int(bot["active_safety_orders_count"]),
            "safety_order_step_percentage": float(bot["safety_order_step_percentage"]),
            "take_profit_type": bot["take_profit_type"],
            "strategy_list": bot["strategy_list"],
            "bot_id": int(bot["id"]),
        },
    )
    if data:
        self.logger.debug("Bot updated: %s" % data)
        self.logger.info(
            "Bot '%s' with id '%s' updated with these pairs:\n%s"
            % (bot["name"], bot["id"], newpairs),
            True,
        )
    else:
        self.logger.error(
            "Error occurred while updating bot '%s' error: %s" % (bot["name"], error["msg"]),
            True,
        )


class Main:
    """Main class, start of application."""

    def __init__(self):
        self.botname = Path(__file__).stem
        result = time.strftime("%A %H:%M:%S %d-%m-%Y")

        self.blacklist = list()
        self.lunacrush = {}
        self.usdtbtc = 0.0

        # Create or load configuration file
        self.config = load_config(self)
        if not self.config:
            self.logger = Logger(self.botname, None, False, False)
            self.logger.info(f"3Commas {self.botname} bot helper!")
            self.logger.info("Started at %s." % result)
            self.logger.info(
                f"Created example config file '{self.botname}.ini', edit it and restart the program."
            )
            sys.exit(0)
        else:
            # Init notification handler
            self.notificationhandler = NotificationHandler(
                self.botname,
                self.config.getboolean("settings", "notifications"),
                self.config.get("settings", "notify-urls"),
            )

            # Init logging
            self.logger = Logger(
                self.botname,
                self.notificationhandler,
                self.config.getboolean("settings", "debug"),
                self.config.getboolean("settings", "notifications"),
            )
            self.logger.info(f"3Commas {self.botname} bot helper!")
            self.logger.info("Started at %s" % result)
            self.logger.info(f"Loaded configuration from '{self.botname}.ini'")

        if self.config.get("settings", "accountmode") == "real":
            self.logger.info("Using REAL TRADING account mode")
            self.accountmode = "real"
        else:
            self.logger.info("Using PAPER TRADING account mode")
            self.accountmode = "paper"

        if self.notificationhandler.enabled:
            self.logger.info("Notifications are enabled")
        else:
            self.logger.info("Notifications are disabled")

        self.api = init_threecommas_api(self)
        self.botids = json.loads(self.config.get("settings", "botids"))

    def start(self):
        """Run main loop at interval."""
        while True:

            # Update 3Commas data
            self.blacklist = get_threecommas_blacklist(self)

            # Get price of BTC
            self.usdtbtc = get_threecommas_btcusd(self)
            self.logger.debug("Current price of BTC is %s USDT" % self.usdtbtc)

            # Update LunaCrush data
            self.lunacrush = get_lunarcrush_data(self)

            # Walk through all bots specified
            for bot in self.botids:
                error, data = self.api.request(
                    entity="bots", action="show", action_id=str(bot)
                )
                if data:
                    find_pairs(self, data)
                else:
                    self.logger.error("Error occurred updating bots: %s" % error["msg"])

            timeinterval = int(self.config.get("settings", "timeinterval"))

            if timeinterval > 0:
                localtime = time.time()
                nexttime = localtime + int(timeinterval)
                result = time.strftime("%H:%M:%S", time.localtime(nexttime))
                self.logger.info(
                    "Next update in %s Seconds at %s" % (timeinterval, result), True
                )
                time.sleep(timeinterval)
            else:
                break


# Start application loop
loop = Main()
loop.start()
