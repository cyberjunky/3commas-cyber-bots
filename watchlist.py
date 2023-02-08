#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from telethon import TelegramClient, events

from helpers.logging import Logger, NotificationHandler
from helpers.threecommas import (
    init_threecommas_api,
    load_blacklist,
    prefetch_marketcodes
)
from helpers.watchlist import process_botlist


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "debug": False,
        "logrotate": 7,
        "usdt-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
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


async def handle_custom_event(event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received telegram message '%s'"
        % (event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    trigger = event.raw_text.splitlines()

    try:
        exchange = trigger[0].replace("\n", "")
        pair = trigger[1].replace("#", "").replace("\n", "")
        base = pair.split("_")[0].replace("#", "").replace("\n", "")
        coin = pair.split("_")[1].replace("\n", "")

        # Fix for future pair format
        if coin.endswith(base) and len(coin) > len(base):
            coin = coin.replace(base, "")

        trade = trigger[2].replace("\n", "")
        if trade == "LONG" and len(trigger) == 4 and trigger[3] == "CLOSE":
            trade = "CLOSE"
    except IndexError:
        logger.debug("Invalid trigger message format!")
        return

    logger.info(
        f"Received message on {exchange}% for {base}_{coin}"
    )

    if exchange.lower() not in ("binance", "ftx", "kucoin"):
        logger.debug(
            f"Exchange '{exchange}' is not yet supported."
        )
        return

    if trade not in ('LONG', 'CLOSE'):
        logger.debug(f"Trade type '{trade}' is not supported yet!")
        return
    if base == "USDT":
        botids = json.loads(config.get("settings", "usdt-botids"))
        if len(botids) == 0:
            logger.debug(
                "No valid usdt-botids configured for '%s', disabled" % base
            )
            return
    elif base == "BTC":
        botids = json.loads(config.get("settings", "btc-botids"))
        if len(botids) == 0:
            logger.debug("No valid btc-botids configured for '%s', disabled" % base)
            return
    else:
        logger.error(
            "Error the base of pair '%s' being '%s' is not supported yet!" % (pair, base)
        )
        return

    if len(botids) == 0:
        logger.debug(
            f"{base}_{coin}: no valid botids configured for base '{base}'."
        )
        return

    await client.loop.run_in_executor(
        None, process_botlist, logger, api, blacklistfile, blacklist, marketcodes, botids, coin, trade
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
    blacklistfile = f"{datadir}/{args.blacklist}"
else:
    blacklistfile = ""

# Create or load configuration file
config = load_config()
if not config:
    logger = Logger(datadir, program, None, 7, False, False)
    logger.info(
        f"Created example config file '{program}.ini', edit it and restart the program"
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
        program,
        config.getboolean("settings", "notifications"),
        config.get("settings", "notify-urls"),
    )

    # Initialise logging
    logger = Logger(
        datadir,
        program,
        notification,
        int(config.get("settings", "logrotate", fallback=7)),
        config.getboolean("settings", "debug"),
        config.getboolean("settings", "notifications"),
    )

# Initialize 3Commas API
api = init_threecommas_api(config)

# Prefetch marketcodes for all bots
botids = json.loads(config.get("settings", "usdt-botids")) + json.loads(config.get("settings", "btc-botids"))
marketcodes = prefetch_marketcodes(logger, api, botids)

# Prefetch blacklists
blacklist = load_blacklist(logger, api, blacklistfile)

# Watchlist telegram trigger
client = TelegramClient(
    f"{datadir}/{program}",
    config.get("settings", "tgram-api-id"),
    config.get("settings", "tgram-api-hash"),
).start(config.get("settings", "tgram-phone-number"))


@client.on(events.NewMessage(chats=config.get("settings", "tgram-channel")))
async def callback(event):
    """Receive Telegram message."""

    await handle_custom_event(event)

    notification.send_notification()


# Start telegram client
client.start()
logger.info(
    "Listening to telegram chat '%s' for triggers"
    % config.get("settings", "tgram-channel"),
    True,
)
client.run_until_disconnected()
