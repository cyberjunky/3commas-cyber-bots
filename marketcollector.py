#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import os
import sqlite3
import sys
import time
from pathlib import Path
from helpers.database import (
    get_next_process_time,
    set_next_process_time
)
from helpers.datasources import (
    get_botassist_data,
    get_coingecko_data,
    get_coinmarketcap_data,
    get_lunarcrush_data
)
from helpers.logging import (
    Logger,
    NotificationHandler
)
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
        "cg-apikey": "Your CoinGecko API key (only required for paid plans), or empty",
        "index-provider": "CoinMarketCap / CoinGecko",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["cmc_btc"] = {
        "start-number": 1,
        "end-number": 200,
        "timeinterval": 3600,
        "percent-change-compared-to": "BTC",
    }
    cfg["cg_btc"] = {
        "start-number": 1,
        "end-number": 200,
        "timeinterval": 3600,
        "percent-change-compared-to": "BTC",
    }
    cfg["altrank_default"] = {
        "lc-apikey": 1,
        "lc-fetchlimit": 500,
    }
    cfg["galaxyscore_default"] = {
        "timeinterval": 3600,
        "lc-apikey": 1,
        "lc-fetchlimit": 500,
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
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "cg-apikey"):
        cfg.set(
            "settings", "cg-apikey",
            "Your CoinGecko API key (only required for paid plans), or empty"
        )

        cfg.set("settings", "index-provider", "CoinMarketCap / CoinGecko")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Updates settings to add cg-apikey")

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
            "change_14d FLOAT DEFAULT 0.0, "
            "change_30d FLOAT DEFAULT 0.0, "
            "change_200d FLOAT DEFAULT 0.0, "
            "change_1y FLOAT DEFAULT 0.0, "
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


def upgrade_mc_db(db_cursor):
    """Upgrade database if needed."""
    try:
        db_cursor.execute("ALTER TABLE prices ADD COLUMN change_14d FLOAT DEFAULT 0.0")
        db_cursor.execute("ALTER TABLE prices ADD COLUMN change_30d FLOAT DEFAULT 0.0")
        db_cursor.execute("ALTER TABLE prices ADD COLUMN change_200d FLOAT DEFAULT 0.0")
        db_cursor.execute("ALTER TABLE prices ADD COLUMN change_1y FLOAT DEFAULT 0.0")

        logger.info("Database schema upgraded")
    except sqlite3.OperationalError:
        logger.debug("Database schema is up-to-date")


def has_pair(base, coin):
    """Check if pair already exists in database."""

    ubase = base.upper()
    ucoin = coin.upper()

    query = "SELECT * FROM pairs WHERE "

    if ubase != "*":
        query += f"base = '{ubase}' AND "

    query += f"coin = '{ucoin}'"

    return sharedcursor.execute(query).fetchone()


def add_pair(base, coin):
    """Add a new base_coin to the tables in the database"""

    ubase = base.upper()
    ucoin = coin.upper()

    logger.debug(
        f"Add pair {ubase}_{ucoin} to database."
    )

    shareddb.execute(
        f"INSERT INTO pairs ("
        f"base, "
        f"coin, "
        f"last_updated "
        f") VALUES ("
        f"'{ubase}', '{ucoin}', {int(time.time())}"
        f")"
    )
    shareddb.execute(
        f"INSERT INTO rankings ("
        f"base, "
        f"coin "
        f") VALUES ("
        f"'{ubase}', '{ucoin}'"
        f")"
    )
    shareddb.execute(
        f"INSERT INTO prices ("
        f"base, "
        f"coin "
        f") VALUES ("
        f"'{ubase}', '{ucoin}'"
        f")"
    )
    # shareddb.commit() left out on purpose


def remove_pair(base, coin):
    """Remove a base_coin from the tables in the database"""

    ubase = base.upper()
    ucoin = coin.upper()

    logger.debug(
        f"Remove pair {ubase}_{ucoin} from database."
    )

    shareddb.execute(
        f"DELETE FROM pairs "
        f"WHERE base = '{ubase}' AND coin = '{ucoin}'"
    )
    shareddb.execute(
        f"DELETE FROM rankings "
        f"WHERE base = '{ubase}' AND coin = '{ucoin}'"
    )
    shareddb.execute(
        f"DELETE FROM prices "
        f"WHERE base = '{ubase}' AND coin = '{ucoin}'"
    )
    # shareddb.commit() left out on purpose


def update_pair_last_updated(base, coin):
    """Update the pair's last updated value in database."""

    ubase = base.upper()
    ucoin = coin.upper()

    shareddb.execute(
        f"UPDATE pairs SET last_updated = {int(time.time())} "
        f"WHERE base = '{ubase}' AND coin = '{ucoin}'"
    )
    # shareddb.commit() left out on purpose


def update_values(table, base, coin, data):
    """Update one or more specific field(s) in a single table in the database"""

    ubase = base.upper()
    ucoin = coin.upper()

    query = f"UPDATE {table} SET "

    keyvalues = ""
    for key, value in data.items():
        if keyvalues:
            keyvalues += ", "

        keyvalues += f"{key} = {value}"

    query += keyvalues
    query += " WHERE "

    if ubase != "*":
        query += f"base = '{ubase}' AND "

    query += f"coin = '{ucoin}'"

    logger.debug(
        f"Execute query '{query}' for pair {ubase}_{ucoin}."
    )

    shareddb.execute(query)
    # shareddb.commit() left out on purpose


def process_cmc_section(section_id):
    """Process the cmc section from the configuration"""

    # Download CoinMarketCap data
    startnumber = int(config.get(section_id, "start-number"))
    endnumber = int(config.get(section_id, "end-number"))
    limit = 1 + (endnumber - startnumber)
    base = config.get(section_id, "percent-change-compared-to")

    logger.debug(
        f"Processing section {section_id} with start {startnumber} "
        f"and limit {limit}. Use {base} as base for the pairs."
    )

    baselist = ("BNB", "BTC", "ETH", "USD")
    if base not in baselist:
        logger.error(
            f"Percent change ('{base}') must be one of the following: "
            f"{baselist}"
        )
        return False

    data = get_coinmarketcap_data(
        logger, config.get("settings", "cmc-apikey"), startnumber, limit, base
    )

    # Check if CMC replied with an error
    # 0: statuscode
    # 1: statusmessage
    # 2: cmc data
    if data[0] != -1:
        logger.error(
            f"Received error {data[0]}: '{data[1]}'. "
            f"Stop processing and retry in 24h again."
        )

        # And exit loop so we can wait 24h before trying again
        return False

    isindexprovider = config.get("settings", "index-provider").lower() == "coinmarketcap"

    for entry in data[2]:
        try:
            coin = str(entry["symbol"])

            # The base could be as coin inside the list, and then skip it
            if base == coin:
                continue

            coinpercent1h = float(entry["quote"][base]["percent_change_1h"])
            coinpercent24h = float(entry["quote"][base]["percent_change_24h"])
            coinpercent7d = float(entry["quote"][base]["percent_change_7d"])

            if not has_pair(base, coin):
                if isindexprovider:
                    # Pair does not yet exist and CoinMarketCap is the index provider
                    add_pair(base, coin)
                else:
                    # Coin does not exist, skip this one
                    logger.debug(
                        f"Coin {coin} not in database, cannot update data for this coin."
                    )
                    continue

            if isindexprovider:
                # Update rankings data
                rankdata = {}
                rankdata["coinmarketcap"] = entry["cmc_rank"]
                update_values("rankings", base, coin, rankdata)

            # Update pricings data
            pricesdata = {}
            pricesdata["change_1h"] = coinpercent1h
            pricesdata["change_24h"] = coinpercent24h
            pricesdata["change_7d"] = coinpercent7d
            update_values("prices", base, coin, pricesdata)

            # Make sure to update the last_updated field to avoid deletion
            update_pair_last_updated(base, coin)
        except KeyError as err:
            logger.error(
                "Something went wrong while parsing CoinMarketCap data. KeyError for field: %s"
                % err
            )
            # Rollback any pending changes
            shareddb.rollback()
            return False

    # Commit everyting to the database
    shareddb.commit()

    logger.info(
        f"CoinMarketCap; updated {len(data[2])} coins ({startnumber}-{endnumber}) "
        f"for base '{base}'.",
        True
    )

    # No exceptions or other cases happened, everything went Ok
    return True


def process_cg_section(section_id):
    """Process the cg section from the configuration"""

    # Download CoinGecko data
    startnumber = int(config.get(section_id, "start-number"))
    endnumber = int(config.get(section_id, "end-number"))
    base = config.get(section_id, "percent-change-compared-to")

    logger.debug(
        f"Processing section {section_id} with start {startnumber} "
        f"and end {endnumber}. Use {base} as base for the pairs."
    )

    baselist = ("BNB", "BTC", "ETH", "USD")
    if base not in baselist:
        logger.error(
            f"Percent change ('{base}') must be one of the following: "
            f"{baselist}"
        )
        return False

    data = get_coingecko_data(
        logger, config.get("settings", "cg-apikey"), startnumber, endnumber, base
    )

    # Check if CG replied with an error
    # 0: statuscode
    # 1: cg data
    if data[0] != -1:
        logger.error(
            f"Received error {data[0]}: "
            f"Stop processing and retry in 24h again."
        )

        # And exit loop so we can wait 24h before trying again
        return False

    isindexprovider = config.get("settings", "index-provider").lower() == "coingecko"

    for entry in data[1]:
        try:
            coin = str(entry["symbol"])

            # The base could be as coin inside the list, and then skip it
            if base == coin:
                continue

            coinpercent1h = 0.0
            if entry.get("price_change_percentage_1h_in_currency") is not None:
                coinpercent1h = float(entry["price_change_percentage_1h_in_currency"])

            coinpercent24h = 0.0
            if entry.get("price_change_percentage_24h_in_currency") is not None:
                coinpercent24h = float(entry["price_change_percentage_24h_in_currency"])

            coinpercent7d = 0.0
            if entry.get("price_change_percentage_7d_in_currency") is not None:
                coinpercent7d = float(entry["price_change_percentage_7d_in_currency"])

            coinpercent14d = 0.0
            if entry.get("price_change_percentage_14d_in_currency") is not None:
                coinpercent14d = float(entry["price_change_percentage_14d_in_currency"])

            coinpercent30d = 0.0
            if entry.get("price_change_percentage_30d_in_currency") is not None:
                coinpercent30d = float(entry["price_change_percentage_30d_in_currency"])

            coinpercent200d = 0.0
            if entry.get("price_change_percentage_200d_in_currency") is not None:
                coinpercent200d = float(entry["price_change_percentage_200d_in_currency"])

            coinpercent1y = 0.0
            if entry.get("price_change_percentage_1y_in_currency") is not None:
                coinpercent1y = float(entry["price_change_percentage_1y_in_currency"])

            if not has_pair(base, coin):
                if isindexprovider:
                    # Pair does not yet exist and CoinGecko is the index provider
                    add_pair(base, coin)
                else:
                    # Coin does not exist, skip this one
                    logger.debug(
                        f"Coin {coin} not in database, cannot update data for this coin."
                    )
                    continue

            if isindexprovider:
                # Update rankings data
                rankdata = {}
                rankdata["coinmarketcap"] = entry["market_cap_rank"]
                update_values("rankings", base, coin, rankdata)

            # Update pricings data
            pricesdata = {}
            pricesdata["change_1h"] = coinpercent1h
            pricesdata["change_24h"] = coinpercent24h
            pricesdata["change_7d"] = coinpercent7d
            pricesdata["change_14d"] = coinpercent14d
            pricesdata["change_30d"] = coinpercent30d
            pricesdata["change_200d"] = coinpercent200d
            pricesdata["change_1y"] = coinpercent1y
            update_values("prices", base, coin, pricesdata)

            # Make sure to update the last_updated field to avoid deletion
            update_pair_last_updated(base, coin)
        except KeyError as err:
            logger.error(
                "Something went wrong while parsing CoinMarketCap data. KeyError for field: %s"
                % err
            )
            # Rollback any pending changes
            shareddb.rollback()
            return False

    # Commit everyting to the database
    shareddb.commit()

    logger.info(
        f"CoinGecko; updated {len(data[1])} coins ({startnumber}-{endnumber}) "
        f"for base '{base}'.",
        True
    )

    # No exceptions or other cases happened, everything went Ok
    return True


def process_lunarcrush_section(section_id, listtype):
    """Process the Altrank or GalaxyScore section from the configuration"""

    # Reset existing data
    shareddb.execute(
        f"UPDATE rankings SET {listtype.lower()} = {0.0}"
    )

    # Download LunarCrush data
    # Volume is not used, so the price is set to 1.0 instead of the real dynamic value
    lunarcrushdata = get_lunarcrush_data(logger, listtype.lower(), config, section_id, 1.0)

    if not lunarcrushdata:
        # Commit clearing of database
        shareddb.commit()

        return False

    # Parse LunaCrush data
    updatedcoins = 0
    for entry in lunarcrushdata:
        coin = entry["s"]

        if not has_pair("*", coin):
            # Coin does not exist, skip this one
            logger.debug(
                f"Coin {coin} not in database, cannot update {listtype} data for this coin."
            )
            continue

        # Update rankings data (both Altrank and GalaxyScore are available in the data)
        rankdata = {}
        rankdata["altrank"] = float(entry["acr"])
        rankdata["galaxyscore"] = float(entry["gs"])
        update_values("rankings", "*", coin, rankdata)

        updatedcoins += 1

    # Commit everyting to the database
    shareddb.commit()

    logger.info(
        f"{listtype}; updated {updatedcoins} coins.",
        True
    )

    return True


def process_volatility_section(section_id):
    """Process the volatility section from the configuration"""

    # Ugly way to read the lists from the configuration
    # Because JSON is not properly saved by the ConfigParser, we need to parse
    # the data and construct the list
    lists = [word.replace("'", "").replace("[", "").replace("]","").strip()
        for word in config.get(section_id, "lists").split(",")]

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

        if not has_pair("USD", coin):
            # Pair does not yet exist
            add_pair("USD", coin)

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
        f"BotAssistExplorer; updated for {len(aggregatedlist)} coins the "
        f"volatility data based on {lists}.",
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
        "Removing coins for which the volatility data is outdated..."
    )

    coincount = 0
    for coin in previous_data.keys():
        if coin in current_data:
            # Coin is updated and actual
            logger.debug(
                f"Coin {coin} from previous interval also in current interval."
            )
            continue

        if not has_pair("USD", coin):
            # Coin does not exist anymore
            logger.debug(
                f"Coin {coin} from previous interval not in db anymore."
            )
            continue

        logger.debug(
            f"Coin {coin} from previous interval not in current interval. Reset data!"
        )

        # Coin not updated and does still exist. Reset old data
        pricesdata = {}
        pricesdata["volatility_24h"] = 0.0
        update_values("prices", "USD", coin, pricesdata)

        coincount += 1

    logger.debug(
        f"Removed {coincount} coins for which the volatility data was outdated."
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
            remove_pair(str(entry[0]), str(entry[1]))

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
        f"UPDATE rankings SET altrank = {0.0}"
    )

    shareddb.execute(
        f"UPDATE rankings SET galaxyscore = {0.0}"
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

# Upgrade the database if needed
upgrade_mc_db(sharedcursor)

# Storage of data for each section (if applicable)
sectionstorage = {}

# Reset some specific data (we don't know how old it is)
reset_database_data()
forceupdate = False

# Refresh market data based on several data sources
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    # Current time to determine which sections to process
    currenttime = int(time.time())

    # House keeping
    cleanup_database()

    for section in config.sections():
        iscmcsection = section.startswith("cmc_")
        iscgsection = section.startswith("cg_")
        isaltranksection = section.startswith("altrank_")
        isgalaxyscoresection = section.startswith("galaxyscore")
        isvolatilitysection = section.startswith("volatility_")

        if (iscmcsection or iscgsection or isaltranksection or
            isgalaxyscoresection or isvolatilitysection
        ):
            sectiontimeinterval = int(config.get(section, "timeinterval"))
            nextprocesstime = get_next_process_time(db, "sections", "sectionid", section)

            logger.debug(
                f"Section {section}: next update at "
                f"{unix_timestamp_to_string(nextprocesstime, '%Y-%m-%d %H:%M:%S')}, "
                f"current time = "
                f"{unix_timestamp_to_string(currenttime, '%Y-%m-%d %H:%M:%S')}, "
            )

            # Only process the section if it's forced, or it's time for the next interval
            if forceupdate or currenttime >= nextprocesstime:
                sectionresult = False
                if iscmcsection:
                    sectionresult = process_cmc_section(section)
                elif iscgsection:
                    sectionresult = process_cg_section(section)
                elif isaltranksection:
                    sectionresult = process_lunarcrush_section(section, "Altrank")
                elif isgalaxyscoresection:
                    sectionresult = process_lunarcrush_section(section, "GalaxyScore")
                elif isvolatilitysection:
                    sectionresult = process_volatility_section(section)

                # Determine new time to process this section. When processing failed
                # it will be retried in 24 hours
                newtime = currenttime + sectiontimeinterval
                if not sectionresult:
                    newtime = currenttime + (24 * 60 * 60)

                    logger.debug(
                        f"Section {section} failed to process. Next update at "
                        f"{unix_timestamp_to_string(newtime, '%Y-%m-%d %H:%M:%S')}."
                    )

                set_next_process_time(db, "sections", "sectionid", section, newtime)
            else:
                logger.debug(
                    f"Section {section} will be processed after "
                    f"{unix_timestamp_to_string(nextprocesstime, '%Y-%m-%d %H:%M:%S')}."
                )
        elif section != "settings":
            logger.warning(
                f"Section '{section}' not processed!",
                False
            )

    # Inital update executed, from here on rely on the section timeinterval
    forceupdate = False

    if not wait_time_interval(logger, notification, timeint, False):
        break
