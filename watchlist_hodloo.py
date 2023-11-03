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
from watchlist import process_botlist


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "3c-apikey-path": "Path to your own generated RSA private key, or empty",
        "tgram-phone-number": "Your Telegram Phone number",
        "tgram-api-id": "Your Telegram API ID",
        "tgram-api-hash": "Your Telegram API Hash",
        "notifications": False,
        "notify-urls": ["notify-url1"],
        "exchange": "Bittrex / Binance / Kucoin",
        "mode": "Telegram"
    }

    cfg["hodloo_5"] = {
        "bnb-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
        "busd-botids": [12345, 67890],
        "eth-botids": [12345, 67890],
        "eur-botids": [12345, 67890],
        "usdt-botids": [12345, 67890],
    }

    cfg["hodloo_10"] = {
        "bnb-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
        "busd-botids": [12345, 67890],
        "eth-botids": [12345, 67890],
        "eur-botids": [12345, 67890],
        "usdt-botids": [12345, 67890],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "3c-apikey-path"):
        cfg.set("settings", "3c-apikey-path", "")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded the configuration file (3c-apikey-path)")

    return cfg


async def handle_hodloo_event(category, event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received telegram message on %s: '%s'"
        % (category, event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    trigger = event.raw_text.splitlines()

    pair = trigger[0].replace("\n", "").replace("**", "")
    base = pair.split("/")[1]
    coin = pair.split("/")[0]

    logger.info(
        f"Received message on {category}% for {base}_{coin}"
    )

    if base.lower() not in ("bnb", "btc", "busd", "eth", "eur", "usdt"):
        logger.debug(
            f"{base}_{coin}: base '{base}' is not yet supported."
        )
        return

    botids = get_botids(category, base)

    if len(botids) == 0:
        logger.debug(
            f"{base}_{coin}: no valid botids configured for base '{base}'."
        )
        return

    await client.loop.run_in_executor(
        None, process_botlist, logger, api, blacklistfile, blacklist, marketcodes, botids, coin, "LONG"
    )


def get_botids(category, base):
    """Get list of botids from configuration based on category and base"""

    return json.loads(config.get(f"hodloo_{category}", f"{base.lower()}-botids"))


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

    # Upgrade config file if needed
    config = upgrade_config(config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Which Exchange to use?
exchange = config.get("settings", "exchange")
if exchange not in ("Bittrex", "Binance", "Kucoin"):
    logger.error(
        f"Exchange {exchange} not supported. Must be 'Bittrex', 'Binance' or 'Kucoin'!"
    )
    sys.exit(0)

# Which Mode to use?
mode = config.get("settings", "mode")
if mode not in ("Telegram", "Websocket"):
    logger.error(
        f"Mode {mode} not supported. Must be 'Telegram' or 'Websocket'!"
    )
    sys.exit(0)

# Initialize 3Commas API
api = init_threecommas_api(logger, config)
if not api:
    sys.exit(0)

# Prefetch marketcodes for all bots
botids = list()
for category in ("5", "10"):
    for base in ("bnb", "btc", "busd", "eth", "eur", "usdt"):
        botids += get_botids(category, base)
marketcodes = prefetch_marketcodes(logger, api, botids)

# Prefetch blacklists
blacklist = load_blacklist(logger, api, blacklistfile)

if mode == "Telegram":
    # Watchlist telegram trigger
    client = TelegramClient(
        f"{datadir}/{program}",
        config.get("settings", "tgram-api-id"),
        config.get("settings", "tgram-api-hash"),
    ).start(config.get("settings", "tgram-phone-number"))

    @client.on(events.NewMessage(chats=f"Hodloo {exchange} 5%"))
    async def callback_5(event):
        """Receive Telegram message."""

        await handle_hodloo_event("5", event)

        notification.send_notification()

    @client.on(events.NewMessage(chats=f"Hodloo {exchange} 10%"))
    async def callback_10(event):
        """Receive Telegram message."""

        await handle_hodloo_event("10", event)

        notification.send_notification()

    # Start telegram client
    client.start()
    logger.info(
        f"Listening to telegram chat 'Hodloo {exchange} 5%' and "
        f"'Hodloo {exchange} 10%' for triggers",
        True,
    )
    notification.send_notification()

    client.run_until_disconnected()
# No else case, mode is already checked before this statement
