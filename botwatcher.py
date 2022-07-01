#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import os
import sqlite3
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    get_shared_bot_data,
    remove_prefix,
    wait_time_interval,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 86400,
        "debug": False,
        "logrotate": 7,
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["botwatch_12345"] = {
        "secret": "secret",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def get_fields_and_types():
    """Get the data fields and there type"""

    datafields = {}
    datafields["bot_id"] = "INT"
    datafields["active_safety_orders_count"] = "INT"
    datafields["allowed_deals_on_same_pair"] = "INT"
    datafields["bot_pair_or_pairs"] = "STRING"
    datafields["enabled"] = "BIT"
    datafields["martingale_step_coefficient"] = "FLOAT"
    datafields["martingale_volume_coefficient"] = "FLOAT"
    datafields["max_active_deals"] = "INT"
    datafields["max_safety_orders"] = "INT"
    datafields["min_volume_btc_24h"] = "INT"
    datafields["profit_currency"] = "STRING"
    datafields["safety_order_step_percentage"] = "FLOAT"
    datafields["strategy"] = "STRING"
    datafields["strategy_list"] = "STRING"
    datafields["take_profit"] = "FLOAT"
    datafields["take_profit_type"] = "STRING"

    return datafields


def get_db_data(bot_id):
    """Get the saved dataset for the specified bot."""

    record = cursor.execute(
        f"SELECT * FROM bot_data "
        f"WHERE bot_id = {bot_id}"
    ).fetchone()

    return record


def store_bot_data(bot_data):
    """Store the latest data for the specified bot."""

    datadef = get_fields_and_types()

    values = []
    for field, fieldtype in datadef.items():
        # Some fields require specific handling, others can be added directly
        if field in ("bot_pair_or_pairs", "strategy_list"):
            values.append(str(bot_data[field])[1:-1])
        else:
            if fieldtype == "STRING":
                values.append(str(bot_data[field]))
            elif fieldtype == "FLOAT":
                values.append(float(bot_data[field]))
            else:
                values.append(bot_data[field])

    db.execute(
        f"INSERT OR REPLACE INTO bot_data ({str(datadef.keys())[11:-2]}) "
        f"VALUES ({str(values)[1:-1]})"
    )

    db.commit()

    logger.info(
        f"Stored latest data for bot '{bot_data['bot_name']}' in database"
    )


def process_shared_bot_data(data, bot_id):
    """Process the downloaded data."""

    storeconfig = False

    botinfo = data['bot_info']

    dbdata = get_db_data(bot_id)
    if dbdata:
        # Compare the latest data with the saved data for changes
        logger.info(
            f"Comparing old and new data for bot \'{botinfo['bot_name']}\' ({bot_id})"
        )

        index = 0
        datadef = get_fields_and_types()
        for field, fieldtype in datadef.items():
            old = None
            new = None

            if field in ("bot_pair_or_pairs", "strategy_list"):
                old = str(dbdata[index])
                new = str(botinfo[field])[1:-1]
            elif fieldtype == "FLOAT":
                old = float(dbdata[index])
                new = float(botinfo[field])
            else:
                old = dbdata[index]
                new = botinfo[field]

            if old != new:
                storeconfig = True
                logger.info(
                    f"\'{botinfo['bot_name']}\' ({bot_id}): {field} changed from {old} to {new}",
                    True
                )

            index += 1
    else:
        storeconfig = True
        logger.info(
            f"New bot to watch: '{botinfo['bot_name']}' (id: {botinfo['bot_id']}). Store current "
            f"configuration only.",
            True
        )

    # Store data if new bot or configuration has changed
    if storeconfig:
        store_bot_data(botinfo)


def init_botwatcher_db():
    """Create or open database to store bot data."""

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

        datadef = get_fields_and_types()

        tablestructure = ""
        for field, fieldtype in datadef.items():
            if tablestructure:
                tablestructure += ", "

            tablestructure += field + " " + fieldtype

            if field == "bot_id":
                tablestructure += " PRIMARY KEY"

        dbcursor.execute(
            f"CREATE TABLE bot_data ("
            f"{tablestructure}"
            f")"
        )
        logger.info("Database tables created successfully")

    return dbconnection


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

# No 3Commas API required

# Initialize or open the database
db = init_botwatcher_db()
cursor = db.cursor()

# Bot monitor watching for configuration changes
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    for section in config.sections():
        if section.startswith("botwatch_"):
            # Bot configuration for section
            botid = remove_prefix(section, "botwatch_")
            botsecret = config.get(section, "secret")

            if botid:
                botdata = get_shared_bot_data(logger, botid, botsecret)

                if botdata:
                    process_shared_bot_data(botdata, botid)
                else:
                    logger.error("Error occurred, no shared bot data to process")
            else:
                logger.error(
                    f"No data fetched for section '{section}'. Check if bot still exists when "
                    f"this message does not disappear on future intervals!"
                )
        elif section not in ("settings"):
            logger.warning(
                f"Section '{section}' not processed (prefix 'botwatch_' missing)!",
                False
            )

    if not wait_time_interval(logger, notification, timeint, False):
        break
