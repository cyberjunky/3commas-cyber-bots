#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
from math import fabs
import os
import sqlite3
import sys
import time
from pathlib import Path
from helpers.database import get_next_process_time, set_next_process_time

from helpers.datasources import (
    get_botassist_data,
    get_coinmarketcap_data
)
from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    unix_timestamp_to_string,
    wait_time_interval,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 900,
        "cleanup-treshold": 86400,
        "debug": False,
        "logrotate": 7,
        "cmc-apikey": "Your CoinMarketCap API Key",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["cmc_btc"] = {
        "start-number": 1,
        "end-number": 200,
        "timeinterval": 3600,
        "percent-change-compared-to": "BTC",
    }
    cfg["cmc_usd"] = {
        "start-number": 1,
        "end-number": 200,
        "timeinterval": 3600,
        "percent-change-compared-to": "USD",
    }
    cfg["volatility_usd"] = {
        "timeinterval": 3600,
        "lists": ["binance_spot_busd_highest_volatility_day",
                  "binance_spot_usdt_highest_volatility_day",
                  "coinbase_spot_usd_highest_volatility_day"
        ],
        "import-volume": True,
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    logger.info(
        "No configuration file upgrade required at this moment."
    )

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
        shareddbconnection = sqlite3.connect(f"{sharedir}/{shareddbname}")
        shareddbconnection.row_factory = sqlite3.Row
        shareddbcursor = shareddbconnection.cursor()
        logger.info(f"Shared database '{sharedir}/{shareddbname}' created successfully")

        shareddbcursor.execute(
            "CREATE TABLE IF NOT EXISTS pairs ("
            "base STRING, "
            "coin STRING, "
            "volume_24h_btc DEFAULT 0.0, "
            "last_updated INT, "
            "PRIMARY KEY(base, coin)"
            ")"
        )

        shareddbcursor.execute(
            "CREATE TABLE IF NOT EXISTS rankings ("
            "base STRING, "
            "coin STRING, "
            "coinmarketcap INT DEFAULT 0, "
            "altrank INT DEFAULT 0, "
            "galaxyscore FLOAT DEFAULT 0.0, "
            "PRIMARY KEY(base, coin)"
            ")"
        )

        shareddbcursor.execute(
            "CREATE TABLE IF NOT EXISTS prices ("
            "base STRING, "
            "coin STRING, "
            "change_1h FLOAT DEFAULT 0.0, "
            "change_24h FLOAT DEFAULT 0.0, "
            "change_7d FLOAT DEFAULT 0.0, "
            "volatility_24h FLOAT DEFAULT 0.0, "
            "PRIMARY KEY(base, coin)"
            ")"
        )

        logger.info("Shared database tables created successfully")

    return shareddbconnection


def open_mc_db():
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


def has_pair(base, coin):
    """Check if pair already exists in database."""

    return sharedcursor.execute(
            f"SELECT * FROM pairs WHERE base = '{base}' AND coin = '{coin}'"
        ).fetchone()


def add_pair(base, coin):
    """Add a new base_coin to the tables in the database"""

    logger.debug(
        f"Add pair {base}_{coin} to database."
    )

    shareddb.execute(
        f"INSERT INTO pairs ("
        f"base, "
        f"coin, "
        f"last_updated "
        f") VALUES ("
        f"'{base}', '{coin}', {int(time.time())}"
        f")"
    )
    shareddb.execute(
        f"INSERT INTO rankings ("
        f"base, "
        f"coin "
        f") VALUES ("
        f"'{base}', '{coin}'"
        f")"
    )
    shareddb.execute(
        f"INSERT INTO prices ("
        f"base, "
        f"coin "
        f") VALUES ("
        f"'{base}', '{coin}'"
        f")"
    )
    # shareddb.commit() left out on purpose


def remove_pair(base, coin):
    """Remove a base_coin from the tables in the database"""

    logger.debug(
        f"Remove pair {base}_{coin} from database."
    )

    shareddb.execute(
        f"DELETE FROM pairs "
        f"WHERE base = '{base}' AND coin = '{coin}'"
    )
    shareddb.execute(
        f"DELETE FROM rankings "
        f"WHERE base = '{base}' AND coin = '{coin}'"
    )
    shareddb.execute(
        f"DELETE FROM prices "
        f"WHERE base = '{base}' AND coin = '{coin}'"
    )
    # shareddb.commit() left out on purpose


def update_pair_last_updated(base, coin):
    """Update the pair's last updated value in database."""

    shareddb.execute(
        f"UPDATE pairs SET last_updated = {int(time.time())} "
        f"WHERE base = '{base}' AND coin = '{coin}'"
    )
    # shareddb.commit() left out on purpose


def update_values(table, base, coin, data):
    """Update one or more specific field(s) in a single table in the database"""

    query = f"UPDATE {table} SET "

    keyvalues = ""
    for key, value in data.items():
        if keyvalues:
            keyvalues += ", "

        keyvalues += f"{key} = {value}"

    query += keyvalues
    query += f" WHERE base = '{base}' AND coin = '{coin}'"

    logger.debug(
        f"Execute query '{query}' for pair {base}_{coin}."
    )

    shareddb.execute(query)
    # shareddb.commit() left out on purpose


def process_cmc_section(section_id):
    """Process the cmc section from the configuration"""

    # Download CoinMarketCap data
    startnumber = int(config.get(section_id, "start-number"))
    endnumber = 1 + (int(config.get(section_id, "end-number")) - startnumber)
    base = config.get(section_id, "percent-change-compared-to")

    baselist = ("BNB", "BTC", "ETH", "USD")
    if base not in baselist:
        logger.error(
            f"Percent change ('{base}') must be one of the following: "
            f"{baselist}"
        )
        return False

    data = get_coinmarketcap_data(
        logger, config.get("settings", "cmc-apikey"), startnumber, endnumber, base
    )

    # Check if CMC replied with an error
    # 0: errorcode
    # 1: errormessage
    # 2: cmc data
    if data[0] != -1:
        logger.error(
            f"Received error {data[0]}: {data[1]}. "
            f"Stop processing and retry in 24h again."
        )

        # And exit loop so we can wait 24h before trying again
        return False

    for entry in data[2]:
        try:
            coin = entry["symbol"]

            # The base could be as coin inside the list, and then skip it
            if base == coin:
                continue

            rank = entry["cmc_rank"]
            coinpercent1h = fabs(float(entry["quote"][base]["percent_change_1h"]))
            coinpercent24h = fabs(float(entry["quote"][base]["percent_change_24h"]))
            coinpercent7d = fabs(float(entry["quote"][base]["percent_change_7d"]))

            if not has_pair(base, coin):
                # Pair does not yet exist
                add_pair(base, coin)

            # Update rankings data
            rankdata = {}
            rankdata["coinmarketcap"] = rank
            update_values("rankings", base, coin, rankdata)

            # Update pricings data
            pricesdata = {}
            pricesdata["change_1h"] = coinpercent1h
            pricesdata["change_24h"] = coinpercent24h
            pricesdata["change_7d"] = coinpercent7d
            update_values("prices", base, coin, pricesdata)

            # Make sure to update the last_updated field to avoid deletion
            update_pair_last_updated(base, coin)

            # Commit everyting for this coin to the database
            shareddb.commit()
        except KeyError as err:
            logger.error(
                "Something went wrong while parsing CoinMarketCap data. KeyError for field: %s"
                % err
            )
            return False

    logger.info(
        f"CoinMarketCap; updated {len(data[2])} coins ({startnumber}-{endnumber}) "
        f"for base '{base}'.",
        True
    )

    # No exceptions or other cases happened, everything went Ok
    return True


def process_volatility_section(section_id):
    """Process the volatility section from the configuration"""

    # Ugly way to read the lists from the configuration
    # Because JSON is not properly saved by the ConfigParser, we need to parse
    # the data and construct the list
    lists = [word.replace("'", "").replace("[", "").replace("]","").strip()
        for word in config.get(section_id, "lists").split(",")]

    importvolume = config.getboolean(section_id, "import-volume")

    combinedlist = {}
    for listentry in lists:
        # Get the botassist data. Set start and end number to zero to
        # indicate we want to process all available data
        data = get_botassist_data(logger, listentry, 0, 0)
        for coindata in data:
            if coindata["symbol"] in combinedlist:
                # Coin already in list. Append new data to the value
                value = combinedlist[coindata["symbol"]]
                value[len(value)] = coindata
            else:
                # Coin not in list. Add new value with the new data
                value = {}
                value[0] = coindata
                combinedlist[coindata["symbol"]] = value

    aggregatedlist = aggregate_volatility_list(combinedlist)

    for coin, data in aggregatedlist.items():
        volatility = data["volatility"]
        volume = data["24h volume"]

        if not has_pair("USD", coin):
            # Pair does not yet exist
            add_pair("USD", coin)

        # Update pairs data
        if importvolume:
            volumedata = {}
            volumedata["volume_24h_btc"] = volume
            update_values("pairs", "USD", coin, volumedata)

        # Update pricings data
        pricesdata = {}
        pricesdata["volatility_24h"] = volatility
        update_values("prices", "USD", coin, pricesdata)

    # Commit all changes to the database
    shareddb.commit()

    # Cleanup old data
    if section_id in sectionstorage:
        cleanup_volatility_data(aggregatedlist, sectionstorage[section_id])

    # Store list for next processing interval
    sectionstorage[section_id] = aggregatedlist

    logger.info(
        f"BotAssistExplorer: updated for {len(aggregatedlist)} coins the "
        f"volatility and/or volume data based on {lists}.",
        True
    )

    # No exceptions or other cases happened, everything went Ok
    return True


def aggregate_volatility_list(datalist):
    """Aggregrate the volatility data to a single element for each pair"""

    flatlist = {}
    for coin, container in datalist.items():
        if len(container) == 1:
            flatlist[coin] = container[0]

            # Remove no longer required (and confusing) keys from the data
            del flatlist[coin]["pair"]
            del flatlist[coin]["symbol"]
        else:
            data = {}

            # Loop over the different values in the container
            for containervalue in container.values():
                # Loop over all the fields/values inside the container and add them to the first one
                for key, value in containervalue.items():
                    if isinstance(value, (float, int)):
                        if key in data:
                            data[key] += value
                        else:
                            data[key] = value

            # Loop over the summerized data and divide to get the average number
            for key, value in data.items():
                if isinstance(value, (float, int)):
                    data[key] /= len(container)

            flatlist[coin] = data

    return flatlist


def cleanup_volatility_data(current_data, previous_data):
    """Remove old or no longer current volatility data"""

    logger.debug(
        "Removing coins for which the volatility and/or volume data is outdated..."
    )

    coincount = 0
    for coin in previous_data.keys():
        if coin in current_data:
            # Coin is updated and actual
            continue

        if not has_pair("USD", coin):
            # Coin does not exist anymore
            continue

        # Coin not updated and does still exist. Reset old data
        volumedata = {}
        volumedata["volume_24h_btc"] = 0.0
        update_values("pairs", "USD", coin, volumedata)

        # Update pricings data
        pricesdata = {}
        pricesdata["volatility_24h"] = 0.0
        update_values("prices", "USD", coin, pricesdata)

        coincount += 1

    logger.debug(
        f"Removed {coincount} coins for which the volatility and/or volume data was outdated."
    )


def cleanup_database():
    """Cleanup the database and remove old / not updated data"""

    cleanuptime = int(time.time()) - int(config.get("settings", "cleanup-treshold"))

    logger.debug(
        f"Remove data older than "
        f"{unix_timestamp_to_string(cleanuptime, '%Y-%m-%d %H:%M:%S')}."
    )

    pairdata = sharedcursor.execute(
            f"SELECT base, coin FROM pairs WHERE last_updated < {cleanuptime}"
        ).fetchall()

    if pairdata:
        logger.info(f"Found {len(pairdata)} pairs to cleanup...")

        for entry in pairdata:
            remove_pair(entry[0], entry[1])

        # Commit everyting to the database
        shareddb.commit()
    else:
        logger.debug(
            "No pair data to cleanup."
        )


def reset_database_data():
    """Reset specific data in the database at startup"""

    logger.info(
        "Initialize volatility data..."
    )

    shareddb.execute(
        f"UPDATE pairs SET volume_24h_btc = {0.0}"
    )

    shareddb.execute(
        f"UPDATE prices SET volatility_24h = {0.0}"
    )

    shareddb.commit()


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


# Initialize or open the database
db = open_mc_db()
cursor = db.cursor()

# Initialize or open the shared database
shareddb = open_shared_db()
sharedcursor = shareddb.cursor()

# Storage of data for each section (if applicable)
sectionstorage = {}

# Reset some specific data (we don't know how old it is)
reset_database_data()
forceupdate = True

# Refresh market data based on several data sources
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    # Current time to determine which sections to process
    starttime = int(time.time())

    # House keeping
    cleanup_database()

    for section in config.sections():
        iscmcsection = section.startswith("cmc_")
        isvolatilitysection = section.startswith("volatility_")

        if iscmcsection or isvolatilitysection:
            sectiontimeinterval = int(config.get(section, "timeinterval"))
            nextprocesstime = get_next_process_time(db, "sections", "sectionid", section)

            # Only process the section if it's forced, or it's time for the next interval,
            # or time exceeds the check interval (clock has changed somehow)
            if forceupdate or starttime >= nextprocesstime or (
                    abs(nextprocesstime - starttime) > sectiontimeinterval
            ):
                sectionresult = False
                if iscmcsection:
                    sectionresult = process_cmc_section(section)
                elif isvolatilitysection:
                    sectionresult = process_volatility_section(section)

                # Determine new time to process this section. When processing failed
                # it will be retried in 24 hours
                newtime = starttime + sectiontimeinterval
                if not sectionresult:
                    newtime = starttime + (24 * 60 * 60)

                set_next_process_time(db, "sections", "sectionid", section, newtime)
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

    # Inital update executed, from here on rely on the section timeinterval
    forceupdate = False

    if not wait_time_interval(logger, notification, timeint, False):
        break
