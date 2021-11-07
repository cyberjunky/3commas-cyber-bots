#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import configparser
import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path
import math

import apprise
import requests
from py3cw.request import Py3CW
from telethon import TelegramClient, events
import sqlite3

class NotificationHandler:
    """Notification class."""

    def __init__(self, progname, enabled=False, notify_urls=None):
        if enabled and notify_urls:
            self.progname = progname
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
            msg = f"[3Commas bots helper {self.progname}]\n" + message
            self.queue.put((msg, attachments or []))


class Logger:
    """Logger class."""

    my_logger = None

    def __init__(self, progname, notificationhandler, debug_enabled, notify_enabled):
        """Logger init."""
        self.my_logger = logging.getLogger(program)
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
        # Log to file
        file_handle = logging.FileHandler(f"logs/{progname}.log")
        file_handle.setLevel(logging.DEBUG)
        file_handle.setFormatter(formatter)
        self.my_logger.addHandler(file_handle)

        # Log to console
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

    def warning(self, message, notify=True):
        """Warning level."""
        self.log(message, "warning")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)

    def error(self, message, notify=True):
        """Error level."""
        self.log(message, "error")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)

    def debug(self, message, notify=False):
        """Debug level."""
        self.log(message, "debug")
        if self.notify_enabled and notify:
            self.notificationhandler.send_notification(message)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{program}.ini"):
        return cfg

    if "watchlist" in program:
        cfg["settings"] = {
            "debug": False,
            "usdt-botid": 12345,
            "btc-botid": 67890,
            "accountmode": "paper",
            "3c-apikey": "Your 3Commas API Key",
            "3c-apisecret": "Your 3Commas API Secret",
            "tgram-phone-number": "Your Telegram Phone number",
            "tgram-channel": "Telegram Channel to watch",
            "tgram-api-id": "Your Telegram API ID",
            "tgram-api-hash": "Your Telegram API Hash",
            "notifications": False,
            "notify-urls": ["notify-url1", "notify-url2"],
        }
    elif "compound" in program:
        cfg["settings"] = {
            "timeinterval": 3600,
            "debug": False,
            "botids": [12345, 67890],
            "profittocompound": 1.0,
            "accountmode": "paper",
            "3c-apikey": "Your 3Commas API Key",
            "3c-apisecret": "Your 3Commas API Secret",
            "notifications": False,
            "notify-urls": ["notify-url1", "notify-url2"],
        }
    else:
        cfg["settings"] = {
            "timeinterval": 3600,
            "debug": False,
            "botids": [12345, 67890],
            "numberofpairs": 10,
            "accountmode": "paper",
            "3c-apikey": "Your 3Commas API Key",
            "3c-apisecret": "Your 3Commas API Secret",
            "lc-apikey": "Your LunarCrush API Key",
            "notifications": False,
            "notify-urls": ["notify-url1", "notify-url2"],
        }

    with open(f"{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None

def init_threecommas_api(cfg):
    """Init the 3commas API."""
    return Py3CW(
        key=cfg.get("settings", "3c-apikey"),
        secret=cfg.get("settings", "3c-apisecret"),
        request_options={
            "request_timeout": 10,
            "nr_of_retries": 3,
            "retry_status_codes": [502],
        },
    )

def get_threecommas_deals(botid):
    """Get all deals from 3Commas from a bot."""

    deals = None
    error, data = api.request(
        entity="deals",
        action="",
        payload={
                "scope": "finished",
                "bot_id": str(botid),
        },
        additional_headers={"Forced-Mode": MODE},
    )
    if error:
        logger.error(
            "Fetching 3Commas deals failed with error: %s" % error
        )
    else:
        logger.debug(
            "Fetched 3Commas deals '%s' OK" % data
        )

    return data

def check_deal(id):
    """Check if deal was already logged."""
    data = cursor.execute(f"SELECT * FROM deals WHERE dealid = {id}").fetchone()
    if data == None:
        return False

    return True

def get_bot_ratio(id):
    """Get bot bo/so percentages if already logged."""
    data = cursor.execute(f"SELECT * FROM bots WHERE botid = {id}").fetchone()
    if data == None:
        return None

    return data

def compound_bot(thebot):
    """Find profit from deals and calculate new SO and BO values."""
    deals = get_threecommas_deals(thebot["id"])

    if deals:
        dealscount = 0
        profitsum = 0.0
        for deal in deals:
            id = deal["id"]
            
            # Register deal in database
            exist = check_deal(id)
            if exist:
                logger.debug("Deal with id '%s' already processed, skipping." % id)
            else:
                # Deal not processed yet
                profit = float(deal['final_profit'])
                dealscount = dealscount +1
                profitsum = profitsum + profit

                db.execute(f"INSERT INTO deals (dealid) VALUES ({id})")

        # profit values to debug only
        dealscount = 1
        profitsum = 1.0

        logger.info("Finished deals: %s total profit: %s" % (dealscount, profitsum))
        db.commit()  

        if profitsum:
            # bot values to calculate with
            base_order_size = float(thebot["base_order_volume"])
            safety_order_size = float(thebot["safety_order_volume"])
            max_active_deals = thebot["max_active_deals"]
            max_safety_orders = thebot["max_safety_orders"]

            # bot values needed for updating bot only
            botid = thebot["id"]
            bot_martingale_volume_coefficient = thebot["martingale_volume_coefficient"]
            bot_safety_order_step_percentage = thebot["safety_order_step_percentage"]
            bot_pairs = thebot["pairs"]
            bot_name = thebot["name"]
            bot_safety_order_step_percentage = thebot["safety_order_step_percentage"]

            # bo/so ratio calculations
            bopercentage = 100 * float(base_order_size) / (float(base_order_size) + float(safety_order_size))
            sopercentage = 100 * float(safety_order_size) / (float(safety_order_size) + float(base_order_size))
            logger.info("Current BO percentage: %s" % bopercentage)
            logger.info("Current SO percentage: %s" % sopercentage)

            # check if data is already in database, else calc and store it
            percentage = get_bot_ratio(botid)
            if percentage:
                (id, bopercentage, sopercentage) = percentage
                logger.info("Using BO percentage from db: %s" % bopercentage)
                logger.info("Using SO percentage from db: %s" % sopercentage)
            else:
                # store in db for later use
                db.execute(f"INSERT INTO bots (botid, bopercentage, sopercentage) VALUES ({botid}, {bopercentage}, {sopercentage})")
                db.commit()
        
            # minimal needed profit calculations
            soprofitneeded = float(max_safety_orders) * 0.01 * max_active_deals
            logger.info("Minimal SO profit needed: %s" % soprofitneeded)

            boprofitneeded =  float(soprofitneeded) * bopercentage / 100
            logger.info("Minimal BO profit needed: %s" % boprofitneeded)

            minprofitneeded = float(boprofitneeded) + float(boprofitneeded)
            logger.info("Minimal profit needed to also update SO: %s" % minprofitneeded)


            if profitsum < minprofitneeded:
                # Only update the BO's
                boprofitsplit = profitsum / max_active_deals
                soprofitsplit = 0
            else:
                # Also update the SO's
                boprofitsplit = (profitsum * bopercentage) / 100 / max_active_deals
                soprofitsplit1 = (profitsum * sopercentage) / 100
                soprofitsplit2 = (soprofitsplit1 /max_active_deals)
                soprofitsplit = ( soprofitsplit2/ max_safety_orders)

            logger.info("BO compound: %s" % boprofitsplit)
            logger.info("SO compound: %s" % soprofitsplit)


            # compound the profits to base volume and safety volume   
            newbaseordervolume = base_order_size + boprofitsplit
            newsafetyordervolume = safety_order_size + soprofitsplit

            logger.info("New BO: %s" % newbaseordervolume)
            logger.info("New SO %s" % newsafetyordervolume)

            logger.info("Base order size increased from %s to %s" % (base_order_size, newbaseordervolume))
            logger.info("Safety order size increased from %s to %s" % (safety_order_size, newsafetyordervolume))

            logger.info("NO BOTS UPDATED YET ALPHA CODE!")

            # TODO Round values
            # Update bot settings
            #     # error, update_bot = api.request(
            #     #     entity="bots",
            #     #     action="update",
            #     #     action_id=str(thebot["id"]),
            #     #     payload={
            #     #         # "account_id": account_id,
            #     #         "bot_id": thebot["id"],
            #     #         "name": thebot["name"],
            #     #         "pairs": bot_pairs,
            #     #         "base_order_volume": adj_base_order_size - 1, # this is auto calculated value that we"re changing
            #     #         "safety_order_volume": adj_safety_order_size - 1, # this is auto calculated value that we"re changing
            #     #         "take_profit": bot_take_profit,
            #     #         "martingale_volume_coefficient": bot_martingale_volume_coefficient,
            #     #         "martingale_step_coefficient": bot_martingale_step_coefficient,
            #     #         "max_safety_orders": bot_max_safety_orders_count,
            #     #         "active_safety_orders_count": bot_active_safety_orders_count,
            #     #         "safety_order_step_percentage": bot_safety_order_step_percentage,
            #     #         "take_profit_type": bot_take_profit_type,
            #     #         "strategy_list": bot_strategy_list,
            #     #         "max_active_deals": str(bot_max_active_deals),
            #     #         }
            #     #     )
            #     # if error == {}:
            #     #     logger.info("Bot update completed!")
            #     # else:
            #     #     logger.info("Bot update NOT completed!")
        else:
            logger.info("No profit made, no BO/SO value update needed!")


def init_compound_db():
    """Create or open database to store bot and deals data."""
    try:
        dbname=f"{program}.sqlite3"
        dbpath=f"file:{dbname}?mode=rw"
        db = sqlite3.connect(dbpath, uri=True) 

        logger.info(f"Database '{dbname}' opened successfully")
    except sqlite3.OperationalError:
        db = sqlite3.connect(dbname)
        cursor = db.cursor()
        logger.info(f"Database '{dbname}' created successfully")

        cursor.execute("CREATE TABLE deals (dealid int Primary Key)")
        cursor.execute("CREATE TABLE bots (botid int Primary Key, bopercentage real, sopercentage real)")
        logger.info("Database tables created successfully")

    return db


# Start application
program = Path(__file__).stem

# Create or load configuration file
config = load_config()
if not config:
    logger = Logger(program, None, False, False)
    logger.info(f"3Commas bot helper {program}!")
    logger.info("Started at %s." % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(
        f"Created example config file '{program}.ini', edit it and restart the program."
    )
    sys.exit(0)
else:
    # Init notification handler
    notification = NotificationHandler(
        program,
        config.getboolean("settings", "notifications"),
        config.get("settings", "notify-urls"),
    )

    # Init logging
    logger = Logger(
        program,
        notification,
        config.getboolean("settings", "debug"),
        config.getboolean("settings", "notifications"),
    )
    logger.info(f"3Commas bot helper {program}")
    logger.info("Started at %s" % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(f"Loaded configuration from '{program}.ini'")

if config.get("settings", "accountmode") == "real":
    logger.info("Using REAL TRADING account")
    MODE = "real"
else:
    logger.info("Using PAPER TRADING account")
    MODE = "paper"

if notification.enabled:
    logger.info("Notifications are enabled")
else:
    logger.info("Notifications are disabled")

# Initialize 3Commas API
api = init_threecommas_api(config)
# Initialize or open database
db = init_compound_db()
cursor = db.cursor()

if "compound" in program:
    # Auto compound profit by tweaking SO/BO
    while True:

        config = load_config()
        logger.info(f"Loaded configuration from '{program}.ini'")
        botids = json.loads(config.get("settings", "botids"))

        # Walk through all bots specified
        for bot in botids:
            boterror, botdata = api.request(
                entity="bots",
                action="show",
                action_id=str(bot),
                additional_headers={"Forced-Mode": MODE},
            )
            if botdata:
                compound_bot(botdata)
            else:
                logger.error("Error occurred compounding bots: %s" % boterror["msg"])

        # pylint: disable=C0103
        timeint = int(config.get("settings", "timeinterval"))

        if timeint > 0:
            localtime = time.time()
            nexttime = localtime + int(timeint)
            timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
            logger.info("Next update in %s Seconds at %s" % (timeint, timeresult), True)
            time.sleep(timeint)
        else:
            break
