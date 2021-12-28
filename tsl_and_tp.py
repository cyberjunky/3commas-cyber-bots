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

    def __init__(self, notificationhandler, logstokeep, debug_enabled, notify_enabled):
        """Logger init."""
        self.my_logger = logging.getLogger()
        self.notify_enabled = notify_enabled
        self.notificationhandler = notificationhandler
        if debug_enabled:
            self.my_logger.setLevel(logging.DEBUG)
            self.my_logger.propagate = False
        else:
            self.my_logger.setLevel(logging.INFO)
            self.my_logger.propagate = False

        date_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "%(asctime)s - %(filename)s - %(levelname)s - %(message)s", date_fmt
        )
        console_formatter = logging.Formatter(
            "%(asctime)s - %(filename)s - %(message)s", date_fmt
        )
        # Create directory if not exists
        if not os.path.exists(f"{datadir}/logs"):
            os.makedirs(f"{datadir}/logs")

        # Log to file and rotate if needed
        file_handle = TimedRotatingFileHandler(
            filename=f"{datadir}/logs/{program}.log", backupCount=logstokeep
        )
        file_handle.setFormatter(formatter)
        self.my_logger.addHandler(file_handle)

        # Log to console
        console_handle = logging.StreamHandler()
        console_handle.setLevel(logging.INFO)
        console_handle.setFormatter(console_formatter)
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
        "timezone": "Europe/Amsterdam",
        "check-interval": 120,
        "monitor-interval": 60,
        "debug": False,
        "logrotate": 7,
        "botids": [12345, 67890],
        "activation-percentage": 3,
        "initial-stoploss-percentage": 1.0,
        "tp-increment-factor": 0.5,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
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


def check_deal(dealid):
    """Check if deal was already logged."""
    data = cursor.execute(f"SELECT * FROM deals WHERE dealid = {dealid}").fetchone()
    if data is None:
        return None

    return data


def update_deal(thebot, deal, new_stoploss, new_take_profit):
    """Update bot with new SL."""
    bot_name = thebot["name"]
    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload={
            "deal_id": thebot["id"],
            "stop_loss_percentage": new_stoploss,
            "take_profit": new_take_profit,
        },
    )
    if data:
        logger.info(
            f"Changing SL for deal {deal_id}/{deal['pair']} on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}%. "
            f"Changed TP from {deal['take_profit']}% to {new_take_profit}",
            True,
        )
    else:
        logger.error(
            "Error occurred updating bot with new SL/TP values: %s" % error["msg"]
        )


def process_deals(thebot):
    """Check deals from bot and compare SL agains the database."""

    deals = thebot["active_deals"]
    monitored_deals = 0

    if deals:
        botid = thebot['id']
        current_deals = ""

        for deal in deals:
            deal_id = deal["id"]

            if current_deals:
                current_deals += ","
            current_deals += str(deal_id)

            actual_profit_percentage = float(deal["actual_profit_percentage"])
            existing_deal = check_deal(deal_id)

            if not existing_deal and actual_profit_percentage >= activation_percentage:
                monitored_deals = +1

                # New deal which requires TSL
                activation_diff = actual_profit_percentage - activation_percentage
                new_stoploss = 0.0 - round(initial_stoploss_percentage + (activation_diff), 2)

                # Increase TP using diff multiplied with the configured factor
                new_take_profit = round(float(deal["take_profit"]) + (activation_diff * tp_increment_factor), 2)

                update_deal(thebot, deal, new_stoploss, new_take_profit)

                db.execute(
                    f"INSERT INTO deals (dealid, botid, last_profit_percentage, last_stop_loss_percentage) "
                    f"VALUES ({deal_id}, {botid}, {actual_profit_percentage}, {new_stoploss})"
                )
                logger.info(
                    f"New deal found {deal_id}/{deal['pair']} on bot \"{thebot['name']}\"; "
                    f"current profit {actual_profit_percentage}, stoploss set to {new_stoploss} and tp to {new_take_profit}"
                )
            elif existing_deal:
                monitored_deals = +1
                last_profit_percentage = float(existing_deal["last_profit_percentage"])

                if actual_profit_percentage > last_profit_percentage:
                    monitored_deals = +1

                    # Existing deal with TSL and profit increased, so move TSL
                    actual_stoploss = float(deal["stop_loss_percentage"])
                    actual_take_profit = float(deal["take_profit"])
                    profit_diff = actual_profit_percentage - last_profit_percentage

                    logger.info(
                        f"Deal {deal_id} profit increase of {profit_diff}%. Keep on monitoring."
                    )

                    new_stoploss = round(actual_stoploss - profit_diff, 2)
                    new_take_profit = round(actual_take_profit + (profit_diff * tp_increment_factor), 2)

                    update_deal(thebot, deal, new_stoploss, new_take_profit)

                    db.execute(
                        f"UPDATE deals SET last_profit_percentage = {actual_profit_percentage}, "
                        f"last_stop_loss_percentage = {new_stoploss} "
                        f"WHERE dealid = {deal_id}"
                    )
                else:
                    logger.info(
                        f"Deal {deal_id} no profit increase (current: {actual_profit_percentage}%, "
                        f"last: {last_profit_percentage}%. Keep on monitoring."
                    )

        logger.info(
            f"Finished processing {len(deals)} deals for bot \"{thebot['name']}\""
        )

        # Housekeeping, clean things up and prevent endless growing database
        if current_deals:
            logger.info(f"Deleting old deals from bot {botid} except {current_deals}")
            db.execute(
                f"DELETE FROM deals WHERE botid = {botid} AND dealid NOT IN ({current_deals})"
            )

        db.commit()

        logger.info(
            f"Bot {botid} has {len(deals)} of which {monitored_deals} deal(s) require monitoring."
        )
    # No else, no deals for this bot

    return monitored_deals


def init_tsl_db():
    """Create or open database to store bot and deals data."""
    try:
        dbname = f"{program}.sqlite3"
        dbpath = f"file:{datadir}/{dbname}?mode=rw"
        dbconnection = sqlite3.connect(dbpath, uri=True)
        dbconnection.row_factory = sqlite3.Row

        logger.info(f"Database '{datadir}/{dbname}' opened successfully")

    except sqlite3.OperationalError:
        dbconnection = sqlite3.connect(f"{datadir}/{dbname}")
        dbconnection.row_factory = sqlite3.Row
        dbcursor = dbconnection.cursor()
        logger.info(f"Database '{datadir}/{dbname}' created successfully")

        dbcursor.execute(
            "CREATE TABLE deals (dealid INT Primary Key, botid INT, last_profit_percentage FLOAT, last_stop_loss_percentage FLOAT)"
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
    logger = Logger(None, 7, False, False)
    logger.info(f"3Commas bot helper {program}")
    logger.info("Started at %s." % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(
        f"Created example config file '{datadir}/{program}.ini', edit it and restart the program."
    )
    sys.exit(0)
else:
    # Handle timezone
    if hasattr(time, "tzset"):
        os.environ["TZ"] = config.get(
            "settings", "timezone", fallback="Europe/Amsterdam"
        )
        time.tzset()

    # Init notification handler
    notification = NotificationHandler(
        config.getboolean("settings", "notifications"),
        config.get("settings", "notify-urls"),
    )

    # Init logging
    logger = Logger(
        notification,
        int(config.get("settings", "logrotate", fallback=7)),
        config.getboolean("settings", "debug"),
        config.getboolean("settings", "notifications"),
    )
    logger.info(f"3Commas bot helper {program}")
    logger.info("Started at %s" % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

if notification.enabled:
    logger.info("Notifications are enabled")
else:
    logger.info("Notifications are disabled")

# Initialize 3Commas API
api = init_threecommas_api(config)
# Initialize or open database
db = init_tsl_db()
cursor = db.cursor()

# TSL %
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # User settings
    botids = json.loads(config.get("settings", "botids"))
    check_interval = int(config.get("settings", "check-interval"))
    monitor_interval = int(config.get("settings", "monitor-interval"))
    activation_percentage = float(json.loads(config.get("settings", "activation-percentage")))
    initial_stoploss_percentage = float(json.loads(config.get("settings", "initial-stoploss-percentage")))
    tp_increment_factor = float(json.loads(config.get("settings", "tp-increment-factor")))

    deals_to_monitor = 0

    # Walk through all bots specified
    for bot in botids:
        boterror, botdata = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )
        if botdata:
            deals_to_monitor += process_deals(botdata)
        else:
            logger.error("Error occurred incrementing deals: %s" % boterror["msg"])
    
    time_interval = check_interval if deals_to_monitor == 0 else monitor_interval
    if time_interval > 0:
        localtime = time.time()
        nexttime = localtime + int(time_interval)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info("Next update in %s Seconds at %s" % (time_interval, timeresult), True)
        time.sleep(time_interval)
    else:
        break