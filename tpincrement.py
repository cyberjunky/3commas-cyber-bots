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

from helpers.logging import Logger, NotificationHandler
from helpers.misc import check_deal
from helpers.threecommas import init_threecommas_api


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
        "increment-step-scale": [0.10, 0.05, 0.05, 0.05, 0.05, 0.05],
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, cfg):
    """Upgrade config file if needed."""

    try:
        cfg.get("settings", "increment-step-scale")
    except configparser.NoOptionError:
        cfg.set(
            "settings", "increment-step-scale", "[0.10, 0.05, 0.05, 0.05, 0.05, 0.05]"
        )
        cfg.remove_option("settings", "increment-percentage")
        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    return cfg


def update_deal(thebot, deal, to_increment, new_percentage):
    """Update deal with new take profit percentage."""
    bot_name = thebot["name"]
    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload={
            "deal_id": thebot["id"],
            "take_profit": new_percentage,
        },
    )
    if data:
        logger.info(
            f"Incremented TP for deal {deal_id}/{deal['pair']} and bot \"{bot_name}\"\n"
            f"Changed TP from {deal['take_profit']}% to {new_percentage}% (+{to_increment}%)",
            True,
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating bot with new take profit values: %s"
                % error["msg"]
            )
        else:
            logger.error("Error occurred updating bot with new take profit values")


def increment_takeprofit(thebot):
    """Check deals from bot and compare safety orders against the database."""

    deals_count = 0
    deals = thebot["active_deals"]

    if deals:
        for deal in deals:
            deal_id = deal["id"]
            completed_safety_orders_count = int(deal["completed_safety_orders_count"])
            to_increment = 0

            deals_count += 1

            existing_deal = check_deal(cursor, deal_id)
            if existing_deal is not None:
                db.execute(
                    f"UPDATE deals SET safety_count = {completed_safety_orders_count} "
                    f"WHERE dealid = {deal_id}"
                )
            else:
                db.execute(
                    f"INSERT INTO deals (dealid, safety_count) VALUES ({deal_id}, "
                    f"{completed_safety_orders_count})"
                )

            existing_deal_safety_count = (
                0 if existing_deal is None else existing_deal["safety_count"]
            )

            for cnt in range(
                existing_deal_safety_count + 1, completed_safety_orders_count + 1
            ):
                try:
                    to_increment += float(increment_step_scale[cnt - 1])
                except IndexError:
                    pass

            if to_increment != 0.0:
                new_percentage = round(float(deal["take_profit"]) + to_increment, 2)
                update_deal(thebot, deal, round(to_increment, 2), new_percentage)

        logger.info(
            f"Finished updating {deals_count} deals for bot \"{thebot['name']}\""
        )
        db.commit()


def init_tpincrement_db():
    """Create or open database to store bot and deals data."""
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
            "CREATE TABLE deals (dealid INT Primary Key, safety_count INT)"
        )
        logger.info("Database tables created successfully")

    return dbconnection


def upgrade_tpincrement_db():
    """Upgrade database if needed."""
    try:
        cursor.execute("ALTER TABLE deals DROP COLUMN increment")
        logger.info("Database schema upgraded")
    except sqlite3.OperationalError:
        logger.debug("Database schema is up-to-date")


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument("-d", "--datadir", help="data directory to use", type=str)

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

    # Upgrade config file if needed
    config = upgrade_config(logger, config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Initialize or open the database
db = init_tpincrement_db()
cursor = db.cursor()

# Upgrade the database if needed
upgrade_tpincrement_db()

# Auto increment TakeProfit %
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    botids = json.loads(config.get("settings", "botids"))
    timeint = int(config.get("settings", "timeinterval"))
    increment_step_scale = json.loads(config.get("settings", "increment-step-scale"))

    # Walk through all bots configured
    for bot in botids:
        boterror, botdata = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )
        if botdata:
            increment_takeprofit(botdata)
        else:
            if boterror and "msg" in boterror:
                logger.error("Error occurred updating bots: %s" % boterror["msg"])
            else:
                logger.error("Error occurred updating bots")

    if timeint > 0:
        localtime = time.time()
        nexttime = localtime + int(timeint)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info("Next update in %s Seconds at %s" % (timeint, timeresult), True)
        time.sleep(timeint)
    else:
        break
