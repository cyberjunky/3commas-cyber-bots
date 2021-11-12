#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import logging
import os
import queue
import sqlite3
import sys
import threading
import time
from logging.handlers import TimedRotatingFileHandler as _TimedRotatingFileHandler
from pathlib import Path

import apprise
from py3cw.request import Py3CW


class NotificationHandler:
    """Notification class."""

    def __init__(self, enabled=False, notify_urls=None):
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
            msg = f"[3Commas bots helper {program}]\n" + message
            self.queue.put((msg, attachments or []))


class TimedRotatingFileHandler(_TimedRotatingFileHandler):
    """Override original code to fix bug with not deleting old logfiles."""

    def __init__(self, filename="", when="midnight", interval=1, backupCount=7):
        super().__init__(
            filename=filename,
            when=when,
            interval=int(interval),
            backupCount=int(backupCount),
        )

    def getFilesToDelete(self):
        """Find all logfiles present."""
        dirname, basename = os.path.split(self.baseFilename)
        filenames = os.listdir(dirname)
        result = []
        prefix = basename + "."
        plen = len(prefix)
        for filename in filenames:
            if filename[:plen] == prefix:
                suffix = filename[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirname, filename))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[: len(result) - self.backupCount]
        return result

    def doRollover(self):
        """Delete old logfiles but keep latest backupCount amount."""
        super().doRollover()
        self.close()
        timetuple = time.localtime(time.time())
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timetuple)

        if os.path.exists(dfn):
            os.remove(dfn)

        os.rename(self.baseFilename, dfn)

        if self.backupCount > 0:
            for oldlog in self.getFilesToDelete():
                os.remove(oldlog)

        self.stream = open(self.baseFilename, "w")

        currenttime = int(time.time())
        newrolloverat = self.computeRollover(currenttime)
        while newrolloverat <= currenttime:
            newrolloverat = newrolloverat + self.interval

        self.rolloverAt = newrolloverat


class Logger:
    """Logger class."""

    my_logger = None

    def __init__(self, notificationhandler, debug_enabled, notify_enabled):
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
        file_handle = logging.FileHandler(f"{datadir}/logs/{program}.log")
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
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timeinterval": 3600,
        "debug": False,
        "logrotate": 7,
        "botids": [12345, 67890],
        "profittocompound": 1.0,
        "accountmode": "paper",
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1", "notify-url2"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
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
        logger.error("Fetching 3Commas deals failed with error: %s" % error)
    else:
        logger.debug("Fetched 3Commas deals '%s' OK" % data)

    return data


def check_deal(dealid):
    """Check if deal was already logged."""
    data = cursor.execute(f"SELECT * FROM deals WHERE dealid = {dealid}").fetchone()
    if data is None:
        return False

    return True


def get_bot_ratio(botid):
    """Get bot bo/so percentages if already logged."""
    data = cursor.execute(f"SELECT * FROM bots WHERE botid = {botid}").fetchone()
    if data is None:
        return None

    return data


def compound_bot(thebot):
    """Find profit from deals and calculate new SO and BO values."""
    deals = get_threecommas_deals(thebot["id"])
    bot_name = thebot["name"]

    if deals:
        dealscount = 0
        profitsum = 0.0
        for deal in deals:
            dealid = deal["id"]

            # Register deal in database
            exist = check_deal(dealid)
            if exist:
                logger.debug("Deal with id '%s' already processed, skipping." % dealid)
            else:
                # Deal not processed yet
                profit = float(deal["final_profit"])
                dealscount = dealscount + 1
                profitsum = profitsum + profit

                db.execute(f"INSERT INTO deals (dealid) VALUES ({dealid})")

        logger.info("Finished deals: %s total profit: %s" % (dealscount, profitsum))
        db.commit()

        if profitsum:
            # bot values to calculate with
            base_order_size = float(thebot["base_order_volume"])
            safety_order_size = float(thebot["safety_order_volume"])
            max_active_deals = thebot["max_active_deals"]
            max_safety_orders = thebot["max_safety_orders"]
            martingale_volume_coefficient = float(
                thebot["martingale_volume_coefficient"]
            )
            botid = thebot["id"]

            fundssoneeded = safety_order_size
            totalsofunds = safety_order_size
            if max_safety_orders > 1:
                for i in range(1, max_safety_orders):
                    fundssoneeded = fundssoneeded * float(martingale_volume_coefficient)
                    totalsofunds = totalsofunds + fundssoneeded

            totalorderfunds = totalsofunds + base_order_size
            logger.info("Current bot settings :")
            logger.info("Base order size      : %s" % base_order_size)
            logger.info("Safety order size    : %s" % safety_order_size)
            logger.info("Max active deals     : %s" % max_active_deals)
            logger.info("Max safety orders    : %s" % max_safety_orders)
            logger.info("SO volume scale      : %s" % martingale_volume_coefficient)
            logger.info("Total funds for BO   : %s" % base_order_size)
            logger.info("Total funds for SO(s): %s" % totalsofunds)
            logger.info("Total funds for order: %s" % totalorderfunds)

            # current order table
            logger.info("Current order table:")
            order_1 = safety_order_size
            logger.info(f"Order BO = {base_order_size}")
            order_x = base_order_size
            i = 0
            while i < max_safety_orders:
                order_x += order_1 * pow(martingale_volume_coefficient, i)
                logger.info(f"Order #{i+1} = {order_x}")
                i += 1

            # bo/so ratio calculations
            bopercentage = (
                100
                * float(base_order_size)
                / (float(base_order_size) + float(safety_order_size))
            )
            sopercentage = (
                100
                * float(safety_order_size)
                / (float(safety_order_size) + float(base_order_size))
            )
            logger.info("Current BO percentage: %s" % bopercentage)
            logger.info("Current SO percentage: %s" % sopercentage)

            # check if data is already in database if so use that, else store calculcated from above
            percentages = get_bot_ratio(botid)
            if percentages:
                (botid, bopercentage, sopercentage) = percentages
                logger.info("Using BO percentage from db: %s" % bopercentage)
                logger.info("Using SO percentage from db: %s" % sopercentage)
            else:
                # store in db for later use
                db.execute(
                    f"INSERT INTO bots (botid, bopercentage, sopercentage) VALUES ({botid}, {bopercentage}, {sopercentage})"
                )
                db.commit()

            # calculate compound values
            boprofitsplit = ((profitsum * bopercentage) / 100) / max_active_deals
            soprofitsplit = (
                ((profitsum * sopercentage) / 100)
                / max_active_deals
                / max_safety_orders
            )

            logger.info("BO compound value: %s" % boprofitsplit)
            logger.info("SO compound value: %s" % soprofitsplit)

            # compound the profits to base volume and safety volume
            newbaseordervolume = base_order_size + boprofitsplit
            newsafetyordervolume = safety_order_size + soprofitsplit

            logger.info(
                "Base order size increased from %s to %s"
                % (base_order_size, newbaseordervolume)
            )
            logger.info(
                "Safety order size increased from %s to %s"
                % (safety_order_size, newsafetyordervolume)
            )

            # new order table
            logger.info("Order table after compounding:")
            order_1 = newsafetyordervolume
            logger.info(f"Order BO = {newbaseordervolume}")
            order_x = newbaseordervolume
            i = 0
            while i < max_safety_orders:
                order_x += order_1 * pow(martingale_volume_coefficient, i)
                logger.info(f"Order #{i+1} = {order_x}")
                i += 1

            # update bot settings
            error, update_bot = api.request(
                entity="bots",
                action="update",
                action_id=str(thebot["id"]),
                payload={
                    "bot_id": thebot["id"],
                    "name": thebot["name"],
                    "pairs": thebot["pairs"],
                    "base_order_volume": newbaseordervolume,  # new base order volume
                    "safety_order_volume": newsafetyordervolume,  # new safety order volume
                    "take_profit": thebot["take_profit"],
                    "martingale_volume_coefficient": thebot[
                        "martingale_volume_coefficient"
                    ],
                    "martingale_step_coefficient": thebot[
                        "martingale_step_coefficient"
                    ],
                    "max_active_deals": max_active_deals,
                    "max_safety_orders": max_safety_orders,
                    "safety_order_step_percentage": thebot[
                        "safety_order_step_percentage"
                    ],
                    "take_profit_type": thebot["take_profit_type"],
                    "strategy_list": thebot["strategy_list"],
                    "active_safety_orders_count": thebot["active_safety_orders_count"],
                },
            )
            if error == {}:
                logger.info("Bot BO/SO update completed!")
                logger.info(
                    f"Compounded ${round(profitsum, 4)} in profit from {dealscount} deal(s) made by '{bot_name}'\nChanged BO from ${round(base_order_size, 4)} to ${round(newbaseordervolume, 4)}\nand SO from ${round(safety_order_size, 4)} to ${round(newsafetyordervolume, 4)}",
                    True,
                )
            else:
                logger.error(
                    "Error occurred updating bot with new BO/SO values: %s"
                    % error["msg"]
                )
        else:
            logger.info(
                f"{bot_name}\nNo (new) profit made, no BO/SO value updates needed!",
                True,
            )
    else:
        logger.info(f"{bot_name}\nNo (new) deals found for this bot!", True)


def init_compound_db():
    """Create or open database to store bot and deals data."""
    try:
        dbname = f"{program}.sqlite3"
        dbpath = f"file:{dbname}?mode=rw"
        dbconnection = sqlite3.connect(dbpath, uri=True)

        logger.info(f"Database '{dbname}' opened successfully")
    except sqlite3.OperationalError:
        dbconnection = sqlite3.connect(dbname)
        dbcursor = dbconnection.cursor()
        logger.info(f"Database '{dbname}' created successfully")

        dbcursor.execute("CREATE TABLE deals (dealid int Primary Key)")
        dbcursor.execute(
            "CREATE TABLE bots (botid int Primary Key, bopercentage real, sopercentage real)"
        )
        logger.info("Database tables created successfully")

    return dbconnection


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument("-d", "--datadir", help="data directory to use", type=str)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# Create or load configuration file
config = load_config()
if not config:
    logger = Logger(None, False, False)
    logger.info(f"3Commas bot helper {program}!")
    logger.info("Started at %s." % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(
        f"Created example config file '{datadir}/{program}.ini', edit it and restart the program."
    )
    sys.exit(0)
else:
    # Init notification handler
    notification = NotificationHandler(
        config.getboolean("settings", "notifications"),
        config.get("settings", "notify-urls"),
    )

    # Init logging
    logger = Logger(
        notification,
        config.getboolean("settings", "debug"),
        config.getboolean("settings", "notifications"),
    )
    logger.info(f"3Commas bot helper {program}")
    logger.info("Started at %s" % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

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
        logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")
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
