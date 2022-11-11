#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from helpers.database import get_next_process_time, set_next_process_time

from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    format_pair,
    populate_pair_lists,
    remove_excluded_pairs,
    unix_timestamp_to_string,
    wait_time_interval,
)
from helpers.threecommas import (
    control_threecommas_bots,
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
        "timeinterval": 3600,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["bu_default"] = {
        "botids": [12345, 67890],
        "timeinterval": 3600,
        "allowmaxdealchange": True,
        "allowbotstopstart": True,
        "base": "BTC",
        "cmc-rank": [1, 200],
        "altrank": [],
        "galaxyscore": [],
        "percent-change-1h": [],
        "percent-change-24h": [],
        "percent-change-7d": [],
        "volatility-24h": [],
        "description": "some description"
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    return cfg


def open_shared_db():
    """Open shared database"""

    try:
        shareddbname = "marketdata.sqlite3"
        shareddbpath = f"file:{sharedir}/{shareddbname}?mode=rw"
        shareddbconnection = sqlite3.connect(shareddbpath, uri=True)
        shareddbconnection.row_factory = sqlite3.Row

        logger.info(f"Shared database '{sharedir}/{shareddbname}' opened successfully")

    except sqlite3.OperationalError:
        logger.info(f"Shared database '{sharedir}/{shareddbname}' couldn't be opened")

    return shareddbconnection


def open_bu_db():
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
            "CREATE TABLE IF NOT EXISTS bots ("
            "botid INT Primary Key, "
            "max_deals INT"
            ")"
        )

        dbcursor.execute(
            "CREATE TABLE IF NOT EXISTS sections ("
            "sectionid STRING Primary Key, "
            "next_processing_timestamp INT"
            ")"
        )

        logger.info("Database tables created successfully")

    return dbconnection


def store_bot_maxdeals(bot_id, max_deals):
    """Store the max deals of the given bot in the database"""

    logger.debug(
        f"Store max active deals {max_deals} for bot {bot_id}"
    )

    db.execute(
        f"INSERT OR REPLACE INTO bots ("
        f"botid, "
        f"max_deals "
        f") VALUES ("
        f"{bot_id}, {max_deals}"
        f")"
    )

    db.commit()


def get_bot_maxdeals(bot_id):
    """Get the max deals of the given bot from the database"""

    data = cursor.execute(
        f"SELECT max_deals FROM bots WHERE botid = {bot_id}"
    ).fetchone()

    maxdeals = 0
    if data:
        maxdeals = data[0]

    logger.debug(
        f"Database has {maxdeals} max active deals stored for bot {bot_id}"
    )

    return maxdeals


def process_bu_section(section_id):
    """Process the section from the configuration"""

    botsupdated = False

    # Bot configuration for section
    botids = json.loads(config.get(section_id, "botids"))

    base = config.get(section_id, "base")
    baselist = ("BNB", "BTC", "ETH", "EUR", "USD")
    if base not in baselist:
        logger.error(
            f"Percent change ('{base}') must be one of the following: "
            f"{baselist}"
        )
        return botsupdated

    filteroptions = {}
    filteroptions["cmcrank"] = json.loads(config.get(section_id, "cmc-rank"))
    filteroptions["altrank"] = json.loads(config.get(section_id, "altrank"))
    filteroptions["galaxyscore"] = json.loads(config.get(section_id, "galaxyscore"))

    pricefilter = {}
    pricefilter["change_1h"] = json.loads(config.get(section_id, "percent-change-1h"))
    pricefilter["change_24h"] = json.loads(config.get(section_id, "percent-change-24h"))
    pricefilter["change_7d"] = json.loads(config.get(section_id, "percent-change-7d"))
    pricefilter["volatility_24h"] = json.loads(config.get(section_id, "volatility-24h"))

    filteroptions["change"] = pricefilter

    # Coindata contains:
    # 0: total number of coins available
    # 1: list of coins after filtering
    coindata = get_coins_from_market_data(base, filteroptions)

    logger.debug(
        f"Fetched {len(coindata[1])} coins from the marketdata database."
    )

    # Walk through all bots configured
    for bot in botids:
        error, data = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )
        if data:
            botsupdated |= update_bot_pairs(section_id, base, data, coindata)
        else:
            botsupdated = False

            if error and "msg" in error:
                logger.error("Error occurred updating bots: %s" % error["msg"])
            else:
                logger.error("Error occurred updating bots")

    return botsupdated


def update_bot_pairs(section_id, base, botdata, coindata):
    """Find new pairs and update the bot."""

    botupdated = False

    # Gather bot settings
    botbase = botdata["pairs"][0].split("_")[0]
    if botbase in ("BTC", "ETH", "BNB"):
        if botbase != base:
            logger.error(
                f"Bot base currency {botbase} and filter currency {base} do not match. "
                f"Only conversion between fiat or stable coins allowed! "
                f"Bot '{botdata['name']}' with id '{botdata['id']}' not updated."
            )
            return botupdated

    # Start from scratch
    newpairs = list()
    badpairs = list()
    blackpairs = list()

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, botdata["account_id"])
    if not marketcode:
        return botupdated

    # Load tickerlist for this exchange
    exchange = botdata["account_name"]
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info(
        f"Bot base pair: {botbase}. Exchange: {exchange} ({marketcode})"
    )

    # Process list of coins
    for coin in coindata[1]:
        try:
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, botbase, coin[0])

            # Populate lists
            populate_pair_lists(
                pair, blacklist, blackpairs, badpairs, newpairs, tickerlist
            )

        except KeyError as err:
            logger.error(
                "Something went wrong while parsing coin data. KeyError for field: %s"
                % err
            )
            return botupdated

    logger.debug(
        f"Skipped blacklisted pairs: {blackpairs}. "
        f"Skipped pairs not on {marketcode}: {badpairs}."
    )

    # If sharedir is set, other scripts could provide a file with pairs to exclude
    if sharedir is not None:
        remove_excluded_pairs(logger, sharedir, botdata['id'], marketcode, base, newpairs)

    # Lower the number of max deals if not enough new pairs and change allowed and
    # change back to original if possible
    paircount = len(newpairs)
    newmaxdeals = False
    allowmaxdealchange = config.getboolean(section_id, "allowmaxdealchange")
    allowbotstopstart = config.getboolean(section_id, "allowbotstopstart")

    if allowmaxdealchange:
        newmaxdeals = determine_bot_maxactivedeals(botdata, paircount)

    if allowbotstopstart:
        handle_bot_stopstart(botdata, paircount)

    # Update the bot with the new pairs
    if newpairs:
        botupdated = set_threecommas_bot_pairs(logger, api, botdata, newpairs, newmaxdeals, False, False)

        if newmaxdeals:
            logger.info(
                f"Bot '{botdata['name']}' with id '{botdata['id']}' changed max "
                f"active deals to {newmaxdeals}.",
                True
            )

        # Send our own notification with more data
        if newpairs != botdata["pairs"]:
            excludedcount = abs(coindata[0][0] - len(coindata[1]))
            logger.info(
                f"Bot '{botdata['name']}' with id '{botdata['id']}' updated with {paircount} "
                f"pairs ({newpairs[0]} ... {newpairs[-1]}). Excluded coins: {excludedcount} (filter), "
                f"{len(blackpairs)} (blacklist), {len(badpairs)} (not on exchange)",
                True
            )
    else:
        # There are no pairs available, which is a normal use-case
        botupdated = True

        logger.info(
            f"None of the pairs have been found on the {exchange} ({marketcode}) exchange!",
            True
        )

    return botupdated


def determine_bot_maxactivedeals(botdata, paircount):
    """Determine the max active deals for the bot"""

    newmaxdeals = False

    # Get stored value from the database. This could be zero, meaning there is
    # no number of active deals stored yet
    originalmaxdeals = get_bot_maxdeals(botdata["id"])

    logger.debug(
        f"{botdata['id']}: original {originalmaxdeals}, paircount {paircount}, max active deals {botdata['max_active_deals']}"
    )

    if paircount < botdata["max_active_deals"]:
        # Lower number of pairs; limit max active deals
        newmaxdeals = paircount

        # Store current max deals, so we can restore later
        # Only if it's not stored yet (current value is zero) because during updates
        # this number could decrease more
        if originalmaxdeals == 0:
            store_bot_maxdeals(botdata["id"], botdata["max_active_deals"])
    elif originalmaxdeals > 0:
        if (
            paircount > botdata["max_active_deals"]
            and paircount < originalmaxdeals
        ):
            # Higher number of pairs below original; limit max active deals
            newmaxdeals = paircount
        elif (
            paircount > botdata["max_active_deals"]
            and botdata["max_active_deals"] != originalmaxdeals
        ):
            # Increased number of pairs above original; set original max active deals
            newmaxdeals = originalmaxdeals

            # Reset stored value so it can be stored again in the future
            store_bot_maxdeals(botdata["id"], 0)
        elif (
            botdata["max_active_deals"] == originalmaxdeals
        ):
            # Reset stored value so it can be stored again in the future
            store_bot_maxdeals(botdata["id"], 0)

    return newmaxdeals


def handle_bot_stopstart(botdata, paircount):
    """Determine and handle bot stop and start"""

    if paircount == 0 and botdata["is_enabled"]:
        # No pairs and bot is running (zero pairs not allowed), so stop it...
        control_threecommas_bots(logger, api, botdata, "disable")
    elif paircount > 0 and not botdata["is_enabled"]:
        # Valid pairs and bot is not running, so start it...
        control_threecommas_bots(logger, api, botdata, "enable")


def get_coins_from_market_data(base, filteroptions):
    """Get pairs based on the specified filtering"""

    #SELECT pairs.coin, rankings.coinmarketcap, prices.change_1h from pairs INNER JOIN rankings ON pairs.coin = rankings.coin INNER JOIN prices ON pairs.coin = prices.coin WHERE pairs.base = 'BTC' AND rankings.coinmarketcap BETWEEN 1 AND 6

    # Query for the total count of coins
    countquery = f"SELECT COUNT(pairs.coin) FROM pairs WHERE base = '{base}'"

    # Base query and joining of all tables
    query = "SELECT pairs.coin FROM pairs "
    query += "INNER JOIN rankings ON pairs.base = rankings.base AND pairs.coin = rankings.coin "
    query += "INNER JOIN prices ON pairs.base = prices.base AND pairs.coin = prices.coin "

    # Specify the base
    query += f"WHERE pairs.base = '{base}' "

    # Specify cmc-rank
    if filteroptions["cmcrank"]:
        query += f"AND rankings.coinmarketcap BETWEEN {filteroptions['cmcrank'][0]} AND {filteroptions['cmcrank'][-1]} "

    # Specify altrank
    if filteroptions["altrank"]:
        query += f"AND rankings.altrank BETWEEN {filteroptions['altrank'][0]} AND {filteroptions['altrank'][-1]} "

    # Specify galaxyscore
    if filteroptions["galaxyscore"]:
        query += f"AND rankings.galaxyscore BETWEEN {filteroptions['galaxyscore'][0]} AND {filteroptions['galaxyscore'][-1]} "

    # Specify percent change
    if filteroptions["change"]:
        if filteroptions["change"]["change_1h"]:
            query += f"AND prices.change_1h BETWEEN {filteroptions['change']['change_1h'][0]} AND {filteroptions['change']['change_1h'][-1]} "

        if filteroptions["change"]["change_24h"]:
            query += f"AND prices.change_24h BETWEEN {filteroptions['change']['change_24h'][0]} AND {filteroptions['change']['change_24h'][-1]} "

        if filteroptions["change"]["change_7d"]:
            query += f"AND prices.change_7d BETWEEN {filteroptions['change']['change_7d'][0]} AND {filteroptions['change']['change_7d'][-1]} "

        if filteroptions["change"]["volatility_24h"]:
            query += f"AND prices.volatility_24h BETWEEN {filteroptions['change']['volatility_24h'][0]} AND {filteroptions['change']['volatility_24h'][-1]} "

    logger.debug(
        f"Build query for fetch of coins: {query}"
    )

    return sharedcursor.execute(countquery).fetchone(), sharedcursor.execute(query).fetchall()


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
    print("This script requires the sharedir to be used (-s option)!")
    sys.exit(0)

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
    config = upgrade_config(config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Initialize or open the database
db = open_bu_db()
cursor = db.cursor()

# Open the shared database
shareddb = open_shared_db()
sharedcursor = shareddb.cursor()

# Refresh coin pairs in 3C bots based on the market data
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
        if section.startswith("bu_"):
            sectiontimeinterval = int(config.get(section, "timeinterval"))
            nextprocesstime = get_next_process_time(db, "sections", "sectionid", section)

            # Only process the section if it's time for the next interval, or
            # time exceeds the check interval (clock has changed somehow)
            if starttime >= nextprocesstime or (
                    abs(nextprocesstime - starttime) > sectiontimeinterval
            ):
                if not process_bu_section(section):
                    # Update failed somewhere, retry soon
                    sectiontimeinterval = 60

                    logger.error(
                        f"Update for section {section} failed. Retry possible after 60 seconds."
                    )

                # Determine new time to process this section
                newtime = starttime + sectiontimeinterval
                set_next_process_time(db, "sections", "sectionid", section, newtime)
            else:
                logger.debug(
                    f"Section {section} will be processed after "
                    f"{unix_timestamp_to_string(nextprocesstime, '%Y-%m-%d %H:%M:%S')}."
                )
        elif section != "settings":
            logger.warning(
                f"Section '{section}' not processed (prefix 'bu_' missing)!",
                False
            )

    if not wait_time_interval(logger, notification, timeint, False):
        break
