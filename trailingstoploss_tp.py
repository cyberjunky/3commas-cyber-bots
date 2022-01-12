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
        "check-interval": 120,
        "monitor-interval": 60,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["tsl_tp_default"] = {
        "botids": [12345, 67890],
        "activation-percentage": 3.0,
        "initial-stoploss-percentage": 1.0,
        "sl-increment-factor": 0.5,
        "tp-increment-factor": 0.5,
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, cfg):
    """Upgrade config file if needed."""

    if len(cfg.sections()) == 1:
        # Old configuration containing only one section (settings)
        logger.error(
            f"Upgrading config file '{datadir}/{program}.ini' to support multiple sections"
        )

        cfg["tsl_tp_default"] = {
            "botids": cfg.get("settings", "botids"),
            "activation-percentage": cfg.get("settings", "activation-percentage"),
            "initial-stoploss-percentage": cfg.get("settings", "initial-stoploss-percentage"),
            "sl-increment-factor": cfg.get("settings", "sl-increment-factor"),
            "tp-increment-factor": cfg.get("settings", "tp-increment-factor"),
        }

        cfg.remove_option("settings", "botids")
        cfg.remove_option("settings", "activation-percentage")
        cfg.remove_option("settings", "initial-stoploss-percentage")
        cfg.remove_option("settings", "sl-increment-factor")
        cfg.remove_option("settings", "tp-increment-factor")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file")

    return cfg


def update_deal(thebot, deal, new_stoploss, new_take_profit):
    """Update bot with new SL."""
    bot_name = thebot["name"]
    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload={
            "deal_id": thebot["id"],
            "stop_loss_percentage": new_stoploss,
            "take_profit": new_take_profit,
        },
    )
    if data:
        logger.info(
            f"Changing SL for deal {deal_id}/{deal['pair']} on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}%. "
            f"Changed TP from {deal['take_profit']}% to {new_take_profit}",
            True,
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating bot with new SL/TP values: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred updating bot with new SL/TP valuess")


def process_deals(thebot):
    """Check deals from bot and compare StopLoss against the database."""

    deals = thebot["active_deals"]
    monitored_deals = 0

    if deals:
        botid = thebot["id"]
        current_deals = ""

        for deal in deals:
            deal_id = deal["id"]

            if current_deals:
                current_deals += ","
            current_deals += str(deal_id)

            actual_profit_percentage = float(deal["actual_profit_percentage"])
            existing_deal = check_deal(cursor, deal_id)

            if not existing_deal and actual_profit_percentage >= activation_percentage:
                monitored_deals = +1

                logger.info(
                    f"New deal data: {deal}"
                )

                # Take space between trigger and actual profit into account
                activation_diff = actual_profit_percentage - activation_percentage

                # SL is calculated by 3C on base order price. Because of filled SO's,
                # we must first calculate the SL price based on the current average price
                current_average_price = float(deal["bought_average_price"])
                sl_price = current_average_price + (current_average_price * ((initial_stoploss_percentage / 100.0)
                                                    + ((activation_diff / 100.0) * sl_increment_factor))
                                                    )

                logger.debug(
                    f"Deal {deal_id}; SL price {sl_price} calculated based on average "
                    f"price {current_average_price}, initial SL of {initial_stoploss_percentage}, "
                    f"activation diff of {activation_diff} and factor {sl_increment_factor}"
                )

                # Now we know the SL price, let's calculate the percentage from
                # the base order price so we have the desired SL for 3C
                initial_bought_price = float(deal["base_order_average_price"])
                new_stoploss = round(
                    100.0 - ((sl_price / initial_bought_price) * 100.0),
                    2
                )

                if new_stoploss != 0.00:
                    # No magic required for increasing TP if configured
                    new_take_profit = round(
                        float(deal["take_profit"])
                        + (activation_diff * tp_increment_factor),
                        2
                    )

                    logger.info(
                        f"Deal {deal_id} (\"{thebot['name']}\") profit ({actual_profit_percentage}%) above "
                        f"activation ({activation_percentage}%). Stoploss on {new_stoploss}%, based on "
                        f"SL price {sl_price} and BO price {initial_bought_price}. Take profit on {new_take_profit}%"
                    )

                    update_deal(thebot, deal, new_stoploss, new_take_profit)

                    db.execute(
                        f"INSERT INTO deals (dealid, botid, last_profit_percentage, last_stop_loss_percentage) "
                        f"VALUES ({deal_id}, {botid}, {actual_profit_percentage}, {new_stoploss})"
                    )
                else:
                    logger.info(
                        f"Deal {deal_id} calculated SL of {new_stoploss} which will cause 3C not to activate SL. No action taken!"
                    )
            elif existing_deal:
                deal_sl = deal["stop_loss_percentage"]
                current_stoploss_percentage = 0.0 if deal_sl is None else float(deal_sl)
                if current_stoploss_percentage != 0.0:
                    monitored_deals = +1
                    last_profit_percentage = float(existing_deal["last_profit_percentage"])

                    if actual_profit_percentage > last_profit_percentage:
                        logger.info(
                            f"Existing deal data: {deal}"
                        )

                        # Existing deal with TSL and profit increased, so move TSL
                        # Because initial SL was calculated correctly, we only have
                        # to adjust with the profit change
                        actual_stoploss = float(deal["stop_loss_percentage"])
                        actual_take_profit = float(deal["take_profit"])
                        profit_diff = actual_profit_percentage - last_profit_percentage

                        new_stoploss = round(
                            actual_stoploss - (profit_diff * sl_increment_factor), 2
                        )

                        if new_stoploss != 0.00:
                            new_take_profit = round(
                                actual_take_profit + (profit_diff * tp_increment_factor), 2
                            )

                            logger.info(
                                f"Deal {deal_id} profit increase from {last_profit_percentage}% to "
                                f"{actual_profit_percentage}%. Update and keep on monitoring."
                            )

                            update_deal(thebot, deal, new_stoploss, new_take_profit)

                            db.execute(
                                f"UPDATE deals SET last_profit_percentage = {actual_profit_percentage}, "
                                f"last_stop_loss_percentage = {new_stoploss} "
                                f"WHERE dealid = {deal_id}"
                            )
                        else:
                            logger.info(
                                f"Deal {deal_id} calculated new SL of {new_stoploss} which will cause 3C "
                                f"to deactive SL. No action taken!"
                            )
                    else:
                        logger.info(
                            f"Deal {deal_id} no profit increase (current: {actual_profit_percentage}%, "
                            f"last: {last_profit_percentage}%). Keep on monitoring."
                        )
                else:
                    # Existing deal, but stoploss is 0.0 which means it has been reset (by the user?)
                    logger.info(
                        f"Deal {deal_id} stoploss deactivated by somebody else; stop monitoring and start "
                        f"in the future again if conditions are met."
                    )

                    db.execute(
                        f"DELETE FROM deals WHERE dealid = {deal_id}"
                    )

        logger.info(
            f"Finished processing {len(deals)} deals for bot \"{thebot['name']}\""
        )

        # Housekeeping, clean things up and prevent endless growing database
        if current_deals:
            logger.info(f"Deleting old deals from bot {botid} except {current_deals}")
            db.execute(
                f"DELETE FROM deals WHERE botid = {botid} AND dealid NOT IN ({current_deals})"
            )

        db.commit()

        logger.info(
            f"Bot {botid} has {len(deals)} of which {monitored_deals} deal(s) require monitoring."
        )
    # No else, no deals for this bot

    return monitored_deals


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
            "CREATE TABLE deals (dealid INT Primary Key, botid INT, last_profit_percentage FLOAT, last_stop_loss_percentage FLOAT)"
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

# TrailingStopLoss and TakeProfit %
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    check_interval = int(config.get("settings", "check-interval"))
    monitor_interval = int(config.get("settings", "monitor-interval"))

    # Used to determine the correct interval
    deals_to_monitor = 0

    for section in config.sections():
        if section.startswith("tsl_tp_"):
            # Bot configuration for section
            botids = json.loads(config.get(section, "botids"))

            activation_percentage = float(
                json.loads(config.get(section, "activation-percentage"))
            )
            initial_stoploss_percentage = float(
                json.loads(config.get(section, "initial-stoploss-percentage"))
            )
            sl_increment_factor = float(
                json.loads(config.get(section, "sl-increment-factor"))
            )
            tp_increment_factor = float(
                json.loads(config.get(section, "tp-increment-factor"))
            )

            # Walk through all bots configured
            for bot in botids:
                boterror, botdata = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(bot),
                )
                if botdata:
                    deals_to_monitor += process_deals(botdata)
                else:
                    if boterror and "msg" in boterror:
                        logger.error("Error occurred updating bots: %s" % boterror["msg"])
                    else:
                        logger.error("Error occurred updating bots")

    timeint = check_interval if deals_to_monitor == 0 else monitor_interval
    if not wait_time_interval(logger, notification, timeint):
        break
