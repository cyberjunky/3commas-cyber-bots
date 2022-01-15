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
from helpers.misc import check_deal, wait_time_interval
from helpers.threecommas import init_threecommas_api


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 90,
        "debug": False,
        "logrotate": 7,
        "botids": [12345, 67890],
        "activation-percentage": 0,
        "initial-stoploss-percentage": "[]",
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
        cfg.get("settings", "initial-stoploss-percentage")
    except configparser.NoOptionError:
        cfg.set("settings", "initial-stoploss-percentage", "[]")
        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    return cfg


def update_deal(thebot, deal, new_stoploss):
    """Update deal with new StopLoss."""
    bot_name = thebot["name"]
    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload={
            "deal_id": thebot["id"],
            "stop_loss_percentage": new_stoploss,
        },
    )
    if data:
        logger.info(
            f"Changing SL for deal {deal_id}/{deal['pair']} on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}% - current profit = {deal['actual_profit_percentage']}%",
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


def trailing_stoploss(thebot):
    """Check deals from bot and compare SL against the database."""

    deals_count = 0
    deals = thebot["active_deals"]

    logger.info(f"Activation: {activation_percentage}%")
    logger.info(f"Set stoploss % value @ activation: {initial_stoploss_percentage}")

    if deals:
        for deal in deals:
            deals_count += 1

            sl_price = float(
                (0 if deal["stop_loss_price"] is None else deal["stop_loss_price"])
            )

            if sl_price != 0:
                deal_id = deal["id"]

                actual_profit_percentage = float(deal["actual_profit_percentage"])
                stoploss = float(deal["stop_loss_percentage"])

                existing_deal = check_deal(cursor, deal_id)
                last_profit_percentage = round(
                    actual_profit_percentage
                    if existing_deal is None
                    or existing_deal["last_stop_loss_percentage"] != stoploss
                    else float(existing_deal["last_profit_percentage"]),
                    2,
                )  # If user changes SL in 3C then we have to start again

                logger.debug(f"Pair: {deal['pair']}")
                logger.debug(f"Deal id: {deal_id}")
                logger.debug(f"Bot Strategy: {thebot['strategy']}")
                logger.debug(f"Actual Profit: {actual_profit_percentage}%")
                logger.debug(f"Current Stoploss: {stoploss}")
                logger.debug(f"Last Used Profit: {last_profit_percentage}%")
                logger.debug(
                    "Tracking Position: {}".format(
                        "No" if existing_deal is None else "Yes"
                    )
                )

                if (
                    existing_deal is None
                    or actual_profit_percentage >= last_profit_percentage
                ) and actual_profit_percentage >= activation_percentage:

                    # If the deal has never been tracked before and an inital stoploss value has been configured
                    new_stoploss = round(
                        initial_stoploss_percentage
                        if existing_deal is None
                        and initial_stoploss_percentage is not None
                        else stoploss
                        + (last_profit_percentage - actual_profit_percentage),
                        2,
                    )

                    if new_stoploss < stoploss:
                        update_deal(thebot, deal, new_stoploss)

                    if existing_deal is not None:
                        db.execute(
                            f"UPDATE deals SET last_profit_percentage = {actual_profit_percentage}, "
                            f"last_stop_loss_percentage = {new_stoploss} "
                            f"WHERE dealid = {deal_id}"
                        )
                    else:
                        db.execute(
                            f"INSERT INTO deals (dealid, last_profit_percentage, last_stop_loss_percentage) "
                            f"VALUES ({deal_id}, {actual_profit_percentage}, {new_stoploss})"
                        )
                        logger.info(
                            f"New deal found {deal_id}/{deal['pair']} on bot \"{thebot['name']}\""
                        )

        logger.info(
            f"Finished processing {deals_count} deals for bot \"{thebot['name']}\""
        )
        db.commit()


def init_tsl_db():
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
            "CREATE TABLE deals (dealid INT Primary Key, last_profit_percentage FLOAT, last_stop_loss_percentage FLOAT)"
        )
        logger.info("Database tables created successfully")

    return dbconnection


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
db = init_tsl_db()
cursor = db.cursor()

# TrailingStopLoss %
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    botids = json.loads(config.get("settings", "botids"))
    timeint = int(config.get("settings", "timeinterval"))
    activation_percentage = json.loads(config.get("settings", "activation-percentage"))
    initial_stoploss_percentage = json.loads(
        config.get("settings", "initial-stoploss-percentage")
    )

    # Walk through all bots configured
    for bot in botids:
        boterror, botdata = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )
        if botdata:
            trailing_stoploss(botdata)
        else:
            if boterror and "msg" in boterror:
                logger.error("Error occurred updating bots: %s" % boterror["msg"])
            else:
                logger.error("Error occurred updating bots")

    if not wait_time_interval(logger, notification, timeint):
        break
