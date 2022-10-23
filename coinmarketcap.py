#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import copy
import json
from math import fabs
import os
import sqlite3
import sys
import time
from pathlib import Path
from helpers.database import get_next_process_time, set_next_process_time

from helpers.datasources import (
    get_coinmarketcap_data
)
from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    format_pair,
    populate_pair_lists,
    remove_excluded_pairs,
    unix_timestamp_to_string,
    wait_time_interval,
)
from helpers.threecommas import (
    get_threecommas_account_marketcode,
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
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "cmc-apikey": "Your CoinMarketCap API Key",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["cmc_default"] = {
        "botids": [12345, 67890],
        "start-number": 1,
        "end-number": 200,
        "timeinterval": 86400,
        "max-percent-compared-to": "USD",
        "max-percent-change-1h": 0.0,
        "max-percent-change-24h": 0.0,
        "max-percent-change-7d": 0.0,
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, cfg):
    """Upgrade config file if needed."""

    if cfg.has_option("settings", "numberofpairs"):
        logger.error(
            f"Upgrading config file '{datadir}/{program}.ini' for numberofpairs"
        )
        cfg.set("settings", "start-number", "1")
        cfg.set("settings", "end-number", cfg.get("settings", "numberofpairs"))
        cfg.remove_option("settings", "numberofpairs")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    if len(cfg.sections()) == 1:
        # Old configuration containing only one section (settings)
        logger.error(
            f"Upgrading config file '{datadir}/{program}.ini' to support multiple sections"
        )

        settings_startnumber = cfg.get("settings", "start-number")
        settings_endnumber = cfg.get("settings", "end-number")

        cfg[f"cmc_{settings_startnumber}-{settings_endnumber}"] = {
            "botids": cfg.get("settings", "botids"),
            "start-number": settings_startnumber,
            "end-number": settings_endnumber,
        }

        cfg.remove_option("settings", "botids")
        cfg.remove_option("settings", "start-number")
        cfg.remove_option("settings", "end-number")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    for cfgsection in cfg.sections():
        if cfgsection.startswith("cmc_"):
            if not cfg.has_option(cfgsection, "max-percent-change-1h"):
                cfg.set(cfgsection, "max-percent-compared-to", "USD")
                cfg.set(cfgsection, "max-percent-change-1h", "0.0")
                cfg.set(cfgsection, "max-percent-change-24h", "0.0")
                cfg.set(cfgsection, "max-percent-change-7d", "0.0")
                cfg.set(cfgsection, "timeinterval", cfg.get("settings", "timeinterval"))

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info(
                    "Upgraded the configuration file (max-percent-change)"
                )

    return cfg


def open_cmc_db():
    """Create or open database to store data."""

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
            "CREATE TABLE IF NOT EXISTS sections ("
            "sectionid STRING Primary Key, "
            "next_processing_timestamp INT"
            ")"
        )

        logger.info("Database tables created successfully")

    return dbconnection


def coinmarketcap_filter(cmcdata, cmc_id):
    """Filter data based on percent change"""

    filtereddata = copy.deepcopy(cmcdata)

    comparedto = config.get(cmc_id, "max-percent-compared-to")
    maxpercent1h = float(config.get(cmc_id, "max-percent-change-1h"))
    maxpercent24h = float(config.get(cmc_id, "max-percent-change-24h"))
    maxpercent7d = float(config.get(cmc_id, "max-percent-change-7d"))

    removedlist = []

    for entry in cmcdata:
        try:
            coin = entry["symbol"]

            coinpercent1h = fabs(float(entry["quote"][comparedto]["percent_change_1h"]))
            coinpercent24h = fabs(float(entry["quote"][comparedto]["percent_change_24h"]))
            coinpercent7d = fabs(float(entry["quote"][comparedto]["percent_change_7d"]))

            removecoin = False
            if maxpercent1h != 0.0 and coinpercent1h > maxpercent1h:
                removecoin = True

            if maxpercent24h != 0.0 and coinpercent24h > maxpercent24h:
                removecoin = True

            if maxpercent7d != 0.0 and coinpercent7d > maxpercent7d:
                removecoin = True

            if removecoin:
                filtereddata.remove(entry)
                removedlist.append(coin)

                logger.debug(
                    f"Removing coin {coin}. 1h: {coinpercent1h}/{maxpercent1h}, "
                    f"24h: {coinpercent24h}/{maxpercent24h}, 7d: {coinpercent7d}/{maxpercent7d}"
                )
            else:
                logger.debug(
                    f"Kept coin {coin}. 1h: {coinpercent1h}/{maxpercent1h}, "
                    f"24h: {coinpercent24h}/{maxpercent24h}, 7d: {coinpercent7d}/{maxpercent7d}"
                )
        except KeyError as err:
            logger.error(
                "Something went wrong while parsing CoinMarketCap data. KeyError for field: %s"
                % err
            )
            return cmcdata

    removedcount = len(removedlist)
    if removedcount > 0:
        logger.info(
            f"Excluded {removedcount} coins for {cmc_id} based on percent change: {removedlist}"
        )

    return filtereddata, removedcount


def coinmarketcap_pairs(thebot, cmcdata):
    """Find new pairs and update the bot."""

    # Gather bot settings
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]

    logger.info("Bot base currency: %s" % base)

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

    # Parse CoinMarketCap data
    # 0: actual data
    # 1: number of removed coins based on percent change filtering
    for entry in cmcdata[0]:
        try:
            coin = entry["symbol"]
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, base, coin)

            # Populate lists
            populate_pair_lists(
                pair, blacklist, blackpairs, badpairs, newpairs, tickerlist
            )

        except KeyError as err:
            logger.error(
                "Something went wrong while parsing CoinMarketCap data. KeyError for field: %s"
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
            "None of the by CoinMarketCap suggested pairs have been found on the %s (%s) exchange!"
            % (exchange, marketcode)
        )
        return

    # Update the bot with the new pairs
    set_threecommas_bot_pairs(logger, api, thebot, newpairs, False, False, False)

    # Send our own notification with more data
    if newpairs != thebot["pairs"]:
        logger.info(
            f"Bot '{thebot['name']}' with id '{thebot['id']}' updated with {len(newpairs)} "
            f"pairs ({newpairs[0]} ... {newpairs[-1]}). Excluded {cmcdata[1]} coins "
            f"based on percent change filtering.",
            True
        )


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

# Initialize or open the database
db = open_cmc_db()
cursor = db.cursor()

# Refresh coin pairs based on CoinMarketCap data
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    # Update the blacklist
    blacklist = load_blacklist(logger, api, blacklistfile)

    # Current time to determine which sections to process
    starttime = int(time.time())

    for section in config.sections():
        if section.startswith("cmc_"):
            sectiontimeinterval = int(config.get(section, "timeinterval"))
            nextprocesstime = get_next_process_time(db, "sections", "sectionid", section)

            # Only process the section if it's time for the next interval, or
            # time exceeds the check interval (clock has changed somehow)
            if starttime >= nextprocesstime or (
                    abs(nextprocesstime - starttime) > sectiontimeinterval
            ):
                # Bot configuration for section
                botids = json.loads(config.get(section, "botids"))

                # Download CoinMarketCap data
                startnumber = int(config.get(section, "start-number"))
                endnumber = 1 + (int(config.get(section, "end-number")) - startnumber)
                convert = config.get(section, "max-percent-compared-to")

                convertlist = ("BNB", "BTC", "ETH", "EUR", "USD")
                if convert not in convertlist:
                    logger.error(
                        f"Percent change ('{convert}') must be one of the following: "
                        f"{convertlist}"
                    )
                    continue

                data = get_coinmarketcap_data(
                    logger, config.get("settings", "cmc-apikey"), startnumber, endnumber, convert
                )

                # Check if CMC replied with an error
                if data[0] != -1:
                    logger.error(
                        f"Received error {data[0]}: {data[1]}. "
                        f"Stop processing and retry in 24h again."
                    )
                    timeint = 86400

                    # And exit loop so we can wait 24h before trying again
                    break

                # Get actual CMC data and process further
                coinmarketcap_data = data[2]

                if coinmarketcap_data:
                    # Filter data according to configuration
                    coinmarketcap_data = coinmarketcap_filter(coinmarketcap_data, section)

                    # Walk through all bots configured
                    for bot in botids:
                        error, data = api.request(
                            entity="bots",
                            action="show",
                            action_id=str(bot),
                        )
                        if data:
                            coinmarketcap_pairs(data, coinmarketcap_data)
                        else:
                            if error and "msg" in error:
                                logger.error("Error occurred updating bots: %s" % error["msg"])
                            else:
                                logger.error("Error occurred updating bots")

                    # Determine new time to process this section
                    newtime = starttime + sectiontimeinterval
                    set_next_process_time(db, "sections", "sectionid", section, newtime)
                else:
                    logger.error("Error occurred during fetch of CMC data")
            else:
                logger.debug(
                    f"Section {section} will be processed after "
                    f"{unix_timestamp_to_string(nextprocesstime, '%Y-%m-%d %H:%M:%S')}."
                )
        elif section != "settings":
            logger.warning(
                f"Section '{section}' not processed (prefix 'cmc_' missing)!",
                False
            )

    if not wait_time_interval(logger, notification, timeint, False):
        break
