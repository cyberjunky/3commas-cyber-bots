#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import logging
import os
import queue
import sys
import threading
import time
from logging.handlers import TimedRotatingFileHandler as _TimedRotatingFileHandler
from pathlib import Path

import apprise
from py3cw.request import Py3CW
from telethon import TelegramClient, events


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
        "debug": False,
        "logrotate": 7,
        "usdt-botid": 0,
        "btc-botid": 0,
        "accountmode": "paper",
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "tgram-phone-number": "Your Telegram Phone number",
        "tgram-channel": "Telegram Channel to watch",
        "tgram-api-id": "Your Telegram API ID",
        "tgram-api-hash": "Your Telegram API Hash",
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


def get_filebased_blacklist():
    """Get the pair blacklist from local file."""

    newblacklist = []
    try:
        with open(blacklistfile, "r") as file:
            newblacklist = file.readlines()
        if newblacklist:
            logger.info(
                "Reading local blacklist file '%s' OK (%s pairs)"
                % (blacklistfile, len(newblacklist))
            )
    except FileNotFoundError:
        logger.error(
            "Reading local blacklist file '%s' failed with error: File not found"
            % blacklistfile
        )

    return newblacklist


def get_threecommas_blacklist():
    """Get the pair blacklist from 3Commas."""

    newblacklist = list()
    error, data = api.request(
        entity="bots",
        action="pairs_black_list",
        additional_headers={"Forced-Mode": MODE},
    )
    if data:
        logger.info(
            "Fetched 3Commas pairs blacklist OK (%s pairs)" % len(data["pairs"])
        )
        newblacklist = data["pairs"]
    else:
        logger.error(
            "Fetching 3Commas pairs blacklist failed with error: %s" % error["msg"]
        )

    return newblacklist


def get_threecommas_market(market_code):
    """Get all the valid pairs for market_code from 3Commas account."""

    tickerlist = []
    error, data = api.request(
        entity="accounts",
        action="market_pairs",
        payload={"market_code": market_code},
        additional_headers={"Forced-Mode": MODE},
    )
    if data:
        tickerlist = data
        logger.info(
            "Fetched 3Commas market data for %s OK (%s pairs)"
            % (market_code, len(tickerlist))
        )
    else:
        logger.error(
            "Fetching 3Commas market data failed with error: %s" % error["msg"]
        )

    return tickerlist


def check_pair(thebot, triggerexchange, base, coin):
    """Check pair and trigger the bot."""

    # Refetch data to catch changes
    # Update pairs blacklist
    if len(blacklistfile):
        blacklist = get_filebased_blacklist()
    else:
        blacklist = get_threecommas_blacklist()

    logger.debug("Trigger base coin: %s" % base)

    # Store some bot settings
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    minvolume = thebot["min_volume_btc_24h"]

    logger.debug("Base coin for this bot: %s" % base)
    logger.debug("Exchange for this bot: %s" % exchange)
    logger.debug("Minimal 24h volume in BTC for this bot: %s" % minvolume)

    if "Paper Account" in exchange:
        logger.info(
            "Trigger is for '%s' exchange bot is on '%s'. Trading in Paper so skipping check."
            % (triggerexchange, exchange),
            True,
        )
    else:
        # Check if bot is connected to same exchange
        if exchange.upper() != triggerexchange.upper():
            logger.info(
                "Trigger is for '%s' exchange while bot is connected to '%s'. Skipping."
                % (triggerexchange.upper(), exchange.upper()),
                True,
            )
            return

    # Get market of 3Commas because it's slightly different then exchanges
    if "binance" in exchange.lower() or "paper account" in exchange.lower():
        tickerlist = get_threecommas_market("binance")
    elif "ftx" in exchange.lower():
        tickerlist = get_threecommas_market("ftx")
    else:
        logger.error(
            "Bot is using the '%s' exchange which is not implemented yet!" % exchange
        )
        return

    # Construct pair based on bot settings (BTC stays BTC, but USDT can become BUSD)
    pair = base + "_" + coin
    logger.debug("New pair constructed: %s" % pair)

    # Check if pair is on 3Commas blacklist
    if pair in blacklist:
        logger.debug(
            "This pair is on your 3Commas blacklist and was skipped: %s" % pair, True
        )
        return

    # Check if pair is on 3Commas market ticker
    if pair not in tickerlist:
        logger.debug(
            "This pair is not valid on the %s market according to 3Commas and was skipped: %s"
            % (exchange, pair),
            True,
        )
        return

    # We have valid pair for our bot and we can trigger a new deal
    logger.info("Triggering your 3Commas bot")
    trigger_bot(thebot, pair)


def trigger_bot(thebot, pair):
    """Trigger bot to start deal asap for pair."""
    error, data = api.request(
        entity="bots",
        action="start_new_deal",
        action_id=str(thebot["id"]),
        payload={"pair": pair},
        additional_headers={"Forced-Mode": MODE},
    )
    if data:
        logger.debug("Bot triggered: %s" % data)
        logger.info(
            "Bot '%s' with id '%s' triggered start_new_deal for: %s"
            % (thebot["name"], thebot["id"], pair),
            True,
        )
    else:
        logger.error(
            "Error occurred while triggering start_new_deal bot '%s' error: %s"
            % (thebot["name"], error["msg"]),
        )


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument("-d", "--datadir", help="data directory to use", type=str)
parser.add_argument("-b", "--blacklist", help="blacklist to use", type=str)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# pylint: disable-msg=C0103
if args.blacklist:
    blacklistfile = args.blacklist
else:
    blacklistfile = ""

# Create or load configuration file
config = load_config()
if not config:
    logger = Logger(None, 7, False, False)
    logger.info(f"3Commas bot helper {program}!")
    logger.info("Started at %s." % time.strftime("%A %H:%M:%S %d-%m-%Y"))
    logger.info(
        f"Created example config file '{program}.ini', edit it and restart the program."
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

# Watchlist telegram trigger
client = TelegramClient(
    program,
    config.get("settings", "tgram-api-id"),
    config.get("settings", "tgram-api-hash"),
).start(config.get("settings", "tgram-phone-number"))


@client.on(events.NewMessage(chats=config.get("settings", "tgram-channel")))
async def callback(event):
    """Parse Telegram message."""
    logger.info(
        "Received telegram message: '%s'" % event.message.text.replace("\n", " - "),
        True,
    )

    trigger = event.raw_text.splitlines()
    if trigger[0] == "BINANCE" or trigger[0] == "FTX" or trigger[0] == "KUCOIN":
        exchange = trigger[0].replace("\n", "")
        pair = trigger[1].replace("#", "").replace("\n", "")
        base = pair.split("_")[0].replace("#", "").replace("\n", "")
        coin = pair.split("_")[1].replace("\n", "")
        trade = trigger[2].replace("\n", "")

        logger.debug("Exchange: %s" % exchange)
        logger.debug("Pair: %s" % pair)
        logger.debug("Base: %s" % base)
        logger.debug("Coin: %s" % coin)
        logger.debug("Trade type: %s" % trade)

        if trade != "LONG":
            logger.debug(f"Trade type '{trade}' is not supported yet!")
            return
        if base == "USDT":
            botid = config.get("settings", "usdt-botid")
            if botid == 0:
                logger.debug(
                    "No valid botid defined for '%s' in config, disabled." % base
                )
                return
        elif base == "BTC":
            botid = config.get("settings", "btc-botid")
            if botid == 0:
                logger.debug(
                    "No valid botid defined for '%s' in config, disabled." % base
                )
                return
        else:
            logger.error("Error the base of pair '%s' is not supported yet!" % pair)
            return

        error, data = api.request(
            entity="bots",
            action="show",
            action_id=str(botid),
        )

        if data:
            await client.loop.run_in_executor(
                None, check_pair, data, exchange, base, coin
            )
        else:
            logger.error("Error occurred triggering bot: %s" % error["msg"])
    else:
        logger.info("Not a crypto trigger message, or exchange not yet supported.")


# Start telegram client
client.start()
logger.info(
    "Listening to telegram chat '%s' for triggers"
    % config.get("settings", "tgram-channel"),
    True,
)
client.run_until_disconnected()
