#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import wait_time_interval
from helpers.threecommas import (
    get_threecommas_account_marketcode,
    get_threecommas_market,
    init_threecommas_api,
    set_threecommas_bot_pairs,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 3600,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["allpairs_example"] = {
        "botids": [12345, 67890],
        "pair": "BTC_ALL",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def all_pairs(thebot, allpair):
    """Find new pairs and update the bot."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]

    logger.info("Bot base currency: %s" % base)
    logger.info("Configured pair: %s" % allpair)

    if base != allpair.split("_")[0]:
        logger.error("Bot uses other base than pair specified: %s" % base)
        return

    # Start from scratch
    newpairs = list()

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, thebot["account_id"])
    if not marketcode:
        return

    # Load tickerlist for this exchange
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    for coin in tickerlist:
        if coin.split("_")[0] == allpair.split("_")[0]:
            newpairs.append(coin)
    newpairs.sort()

    # Update the bot with the all pairs
    set_threecommas_bot_pairs(logger, api, thebot, newpairs)


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument(
    "-d", "--datadir", help="directory to use for config and logs files", type=str
)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# Create or load configuration file
config = load_config()
if not config:
    # Initialise temp logging
    logger = Logger(datadir, program, None, 7, False, False)
    logger.info(
        f"Created example config file '{datadir}/{program}.ini', edit it and restart the program"
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

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Refresh all pairs
while True:

    # Reload config files and data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    for section in config.sections():
        if section.startswith("allpairs_"):
            # Bot configuration for section
            botids = json.loads(config.get(section, "botids"))
            pair = config.get(section, "pair")

            # Walk through all bots configured
            for bot in botids:
                boterror, botdata = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(bot),
                )
                if botdata:
                    all_pairs(botdata, pair)
                elif boterror and "msg" in boterror:
                    logger.error("Error occurred updating bots: %s" % boterror["msg"])
                else:
                    logger.error("Error occurred updating bots")

    if not wait_time_interval(logger, notification, timeint):
        break
