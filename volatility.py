#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from helpers.datasources import (
    get_lunarcrush_data
)
from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    format_pair,
    populate_pair_lists,
    remove_excluded_pairs,
    wait_time_interval,
)
from helpers.threecommas import (
    get_threecommas_account_marketcode,
    get_threecommas_btcusd,
    get_threecommas_market,
    init_threecommas_api,
    load_blacklist,
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
        "botids": [12345, 67890],
        "numberofpairs": 10,
        "maxaltrankscore": 1500,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "lc-apikey": "Your LunarCrush API Key",
        "lc-fetchlimit": 150,
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, cfg):
    """Upgrade config file if needed."""

    try:
        cfg.get("settings", "lc-fetchlimit")
    except configparser.NoOptionError:
        logger.error(f"Upgrading config file '{datadir}/{program}.ini'")
        cfg.set("settings", "lc-fetchlimit", "150")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    return cfg


def lunarcrush_pairs(thebot):
    """Find new pairs and update the bot."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    minvolume = float(thebot["min_volume_btc_24h"])
    if not minvolume:
        minvolume = 0.0

    logger.info("Bot base currency: %s" % base)
    logger.info("Bot minimal 24h BTC volume: %s" % minvolume)

    # Start from scratch
    newpairs = list()
    badpairs = list()
    blackpairs = list()

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, thebot["account_id"])
    if not marketcode:
        return

    # Load tickerlist for this exchange
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    # Fetch and parse LunaCrush data
    for entry in lunarcrush:
        try:
            coin = entry["s"]
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, base, coin)

            acrscore = float(entry["acr"])
            volbtc = float(entry["volbtc"])
            if volbtc is None:
                logger.debug("No valid 24h BTC volume for quote '%s', skipping" % coin)
                continue

            # Check if coin has minimum 24h volume as set in bot
            if volbtc < minvolume:
                logger.debug(
                    "Quote currency '%s' does not have enough 24h BTC volume (%s), skipping"
                    % (coin, str(volbtc))
                )
                continue

            # Check if coin has minimum AltRank score
            if acrscore > maxacrscore:
                logger.debug(
                    "Quote currency '%s' is not in AltRank score top %s (%s), skipping"
                    % (coin, maxacrscore, acrscore)
                )
                continue

            # Populate lists
            populate_pair_lists(
                pair, blacklist, blackpairs, badpairs, newpairs, tickerlist
            )

            # Did we get enough pairs already?
            if numberofpairs:
                if len(newpairs) == numberofpairs:
                    break
            else:
                if len(newpairs) == int(thebot["max_active_deals"]):
                    break

        except KeyError as err:
            logger.error(
                "Something went wrong while parsing LunarCrush data. KeyError for field: %s"
                % err
            )
            return

    logger.debug("These pairs are blacklisted and were skipped: %s" % blackpairs)

    logger.debug(
        "These pairs are invalid on '%s' and were skipped: %s" % (marketcode, badpairs)
    )

    # If sharedir is set, other scripts could provide a file with pairs to exclude
    if sharedir is not None:
        remove_excluded_pairs(logger, sharedir, thebot['id'], marketcode, base, newpairs)

    if not newpairs:
        logger.info(
            "None of the LunarCrush pairs are present on the %s (%s) exchange!"
            % (exchange, marketcode)
        )
        return

    # Update the bot with the new pairs
    set_threecommas_bot_pairs(logger, api, thebot, newpairs, False)


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument(
    "-d", "--datadir", help="directory to use for config and logs files", type=str
)
parser.add_argument(
    "-s", "--sharedir", help="directory to use for shared files", type=str
)
parser.add_argument(
    "-b", "--blacklist", help="local blacklist to use instead of 3Commas's", type=str
)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# pylint: disable-msg=C0103
if args.sharedir:
    sharedir = args.sharedir
else:
    sharedir = None

# pylint: disable-msg=C0103
if args.blacklist:
    blacklistfile = f"{datadir}/{args.blacklist}"
else:
    blacklistfile = None

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

    # Upgrade config file if needed
    config = upgrade_config(logger, config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Lunacrush GalayScore or AltRank pairs
while True:

    # Reload config files and data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    numberofpairs = int(config.get("settings", "numberofpairs"))
    maxacrscore = int(config.get("settings", "maxaltrankscore", fallback=100))
    botids = json.loads(config.get("settings", "botids"))
    timeint = int(config.get("settings", "timeinterval"))
    lcapikey = config.get("settings", "lc-apikey")

    # Update the blacklist
    blacklist = load_blacklist(logger, api, blacklistfile)

    # Download LunarCrush data
    usdtbtcprice = get_threecommas_btcusd(logger, api)
    lunarcrush = get_lunarcrush_data(logger, program, config, usdtbtcprice)

    # Walk through all bots configured
    for bot in botids:
        error, data = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )

        if data:
            lunarcrush_pairs(data)
        else:
            if error and "msg" in error:
                logger.error("Error occurred updating bots: %s" % error["msg"])
            else:
                logger.error("Error occurred updating bots")

    if not wait_time_interval(logger, notification, timeint):
        break
