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
            f"Changing SL for deal {deal['pair']} ({deal_id}) on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}%. "
            f"Changed TP from {deal['take_profit']}% to {new_take_profit}"
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating bot with new SL/TP values: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred updating bot with new SL/TP valuess")


def process_deals(thebot):
    """Check deals from bot, compare against the database and handle them."""

    monitored_deals = 0

    botid = thebot["id"]
    deals = thebot["active_deals"]

    if deals:
        current_deals = []

        for deal in deals:
            deal_id = deal["id"]
            deal_strategy = deal["strategy"]

            if deal_strategy == "short":
                logger.warning(
                    f"Deal {deal_id} strategy is short; only long is supported for now!"
                )
            elif deal_strategy == "long":
                current_deals.append(deal_id)

                existing_deal = check_deal(cursor, deal_id)
                if not existing_deal and float(deal["actual_profit_percentage"]) >= activation_percentage:
                    monitored_deals = +1

                    new_long_deal(thebot, deal)
                elif existing_deal:
                    deal_sl = deal["stop_loss_percentage"]
                    current_stoploss_percentage = 0.0 if deal_sl is None else float(deal_sl)
                    if current_stoploss_percentage != 0.0:
                        monitored_deals = +1

                        update_long_deal(thebot, deal, existing_deal)
                    else:
                        # Existing deal, but stoploss is 0.0 which means it has been reset
                        remove_active_deal(deal_id)

        # Housekeeping, clean things up and prevent endless growing database
        remove_closed_deals(botid, current_deals)

        logger.info(
            f"Bot \"{thebot['name']}\" ({botid}) has {len(deals)} deal(s)"
            f"of which {monitored_deals} require monitoring."
        )
    else:
        logger.info(
            f"Bot \"{thebot['name']}\" ({botid}) has no active deals."
        )
        remove_all_deals(botid)

    return monitored_deals


def new_long_deal(thebot, deal):
    """New long deal to activate SL on"""

    botid = thebot["id"]
    deal_id = deal["id"]
    pair = deal['pair']
    actual_profit_percentage = float(deal["actual_profit_percentage"])

    # Take space between trigger and actual profit into account
    activation_diff = actual_profit_percentage - activation_percentage

    # SL is calculated by 3C on base order price. Because of filled SO's,
    # we must first calculate the SL price based on the bought average price
    bought_average_price = float(deal["bought_average_price"])
    sl_price = bought_average_price + (bought_average_price * ((initial_stoploss_percentage / 100.0)
                                       + ((activation_diff / 100.0) * sl_increment_factor))
                                       )

    logger.debug(
        f"Deal {pair} ({deal_id}); SL price {sl_price} calculated based on bought "
        f"price {bought_average_price}, initial SL of {initial_stoploss_percentage}, "
        f"activation diff of {activation_diff} and sl factor {sl_increment_factor}"
    )

    # Now we know the SL price, let's calculate the percentage from
    # the base order price so we have the desired SL for 3C
    base_price = float(deal["base_order_average_price"])
    base_price_sl_percentage = round(
        100.0 - ((sl_price / base_price) * 100.0),
        2
    )

    logger.debug(
        f"Deal {pair} ({deal_id}); base SL of {base_price_sl_percentage}% calculated "
        f"based on base price {base_price} and SL price {sl_price}."
    )

    if base_price_sl_percentage != 0.00:
        # Calculate understandable SL percentage based on bought average price
        average_price_sl_percentage = round(
            ((sl_price / bought_average_price) * 100.0) - 100.0,
            2
        )

        logger.debug(
            f"Deal {pair} ({deal_id}); average SL of {average_price_sl_percentage}% "
            f"calculated based on average price {bought_average_price} and "
            f"SL price {sl_price}."
        )

        # Calculate new TP percentage
        current_tp_percentage = float(deal["take_profit"])
        new_tp_percentage = round(
            current_tp_percentage
            + (activation_diff * tp_increment_factor),
            2
        )

        logger.info(
            f"Deal {pair} ({deal_id}): actual profit ({actual_profit_percentage}%) above "
            f"activation ({activation_percentage}%). StopLoss activated "
            f"on {average_price_sl_percentage}%.",
            True
        )

        if new_tp_percentage > current_tp_percentage:
            logger.info(
                f"TakeProfit increased from {current_tp_percentage}% "
                f"to {new_tp_percentage}%",
                True
            )

        update_deal(thebot, deal, base_price_sl_percentage, new_tp_percentage)

        db.execute(
            f"INSERT INTO deals (dealid, botid, last_profit_percentage, last_stop_loss_percentage) "
            f"VALUES ({deal_id}, {botid}, {actual_profit_percentage}, {base_price_sl_percentage})"
        )

        db.commit()
    else:
        logger.info(
            f"Deal {pair} ({deal_id}) calculated SL of {base_price_sl_percentage} which "
            f"will cause 3C not to activate SL. No action taken!"
        )


def update_long_deal(thebot, deal, existing_deal):
    """Update long deal and increase SL (Trailing SL) if profit has increased."""

    deal_id = deal["id"]
    pair = deal['pair']
    actual_profit_percentage = float(deal["actual_profit_percentage"])
    last_profit_percentage = float(existing_deal["last_profit_percentage"])

    if actual_profit_percentage > last_profit_percentage:
        # Existing deal with TSL and profit increased, so move TSL
        # Because initial SL was calculated correctly, we only have
        # to adjust with the profit change
        current_sl_percentage = float(deal["stop_loss_percentage"])
        current_tp_percentage = float(deal["take_profit"])
        profit_diff = actual_profit_percentage - last_profit_percentage

        new_base_price_sl_percentage = round(
            current_sl_percentage - (profit_diff * sl_increment_factor), 2
        )

        logger.debug(
            f"Deal {pair} ({deal_id}); new base SL of {new_base_price_sl_percentage}% "
            f"calculated based on current SL {current_sl_percentage}%, "
            f"profit diff {profit_diff} and increment {sl_increment_factor}."
        )

        if new_base_price_sl_percentage != 0.00:
            new_tp_percentage = round(
                current_tp_percentage + (profit_diff * tp_increment_factor), 2
            )

            # Calculate understandable SL percentage based on bought average price
            # First calculate the base prices for current and new SL %
            base_price = float(deal["base_order_average_price"])
            current_base_sl_price = base_price - ((base_price / 100.0)
                                                  * current_sl_percentage)
            new_base_sl_price = base_price - ((base_price / 100.0)
                                              * new_base_price_sl_percentage)

            logger.debug(
                f"Deal {pair} ({deal_id}); current SL price of {current_base_sl_price} "
                f"on base price {base_price} and {current_sl_percentage}%. New "
                f"SL price {new_base_sl_price} on base price {base_price} "
                f"and {new_base_price_sl_percentage}%."
            )

            # Then calculate the SL % based on the average price, same axis as TP %
            bought_average_price = float(deal["bought_average_price"])
            current_average_price_sl_percentage = round(
                ((current_base_sl_price / bought_average_price) * 100.0) - 100.0,
                2
            )
            new_average_price_sl_percentage = round(
                ((new_base_sl_price / bought_average_price) * 100.0) - 100.0,
                2
            )

            logger.debug(
                f"Deal {pair} ({deal_id}); average SL {current_average_price_sl_percentage}% "
                f"based on base sl price {current_base_sl_price} and bought price "
                f"{bought_average_price}. New average SL {new_average_price_sl_percentage}% "
                f"based on new base sl price {new_base_sl_price} and bought price "
                f"{bought_average_price}."
            )

            logger.info(
                f"Deal {pair} ({deal_id}) profit increased from {last_profit_percentage}% "
                f"to {actual_profit_percentage}%. "
                f"StopLoss increased from {current_average_price_sl_percentage}% to "
                f"{new_average_price_sl_percentage}%. ",
                True
            )

            if new_tp_percentage > current_tp_percentage:
                logger.info(
                    f"TakeProfit increased from {current_tp_percentage}% "
                    f"to {new_tp_percentage}%",
                    True
                )

            update_deal(thebot, deal, new_base_price_sl_percentage, new_tp_percentage)

            db.execute(
                f"UPDATE deals SET last_profit_percentage = {actual_profit_percentage}, "
                f"last_stop_loss_percentage = {new_base_price_sl_percentage} "
                f"WHERE dealid = {deal_id}"
            )

            db.commit()
        else:
            logger.info(
                f"Deal {pair} ({deal_id}) calculated SL of 0.0 which will cause 3C "
                f"to deactive SL; no update this round!"
            )
    else:
        logger.info(
            f"Deal {pair} ({deal_id}) no profit increase (current: {actual_profit_percentage}%, "
            f"previous: {last_profit_percentage}%). Keep on monitoring."
        )


def remove_active_deal(deal_id):
    """Remove long deal (deal SL reset by user)."""

    logger.info(
        f"Deal {deal_id} stoploss deactivated by somebody else; stop monitoring and start "
        f"in the future again if conditions are met."
    )

    db.execute(
        f"DELETE FROM deals WHERE dealid = {deal_id}"
    )

    db.commit()


def remove_closed_deals(bot_id, current_deals):
    """Remove all deals for the given bot, except the ones in the list."""

    if current_deals:
        # Remove start and end square bracket so we can properly use it
        current_deals_str = str(current_deals)[1:-1]

        logger.info(f"Deleting old deals from bot {bot_id} except {current_deals_str}")
        db.execute(
            f"DELETE FROM deals WHERE botid = {bot_id} AND dealid NOT IN ({current_deals_str})"
        )

        db.commit()


def remove_all_deals(bot_id):
    """Remove all stored deals for the specified bot."""

    logger.info(
        f"Removing all stored deals for bot {bot_id}."
    )

    db.execute(
        f"DELETE FROM deals WHERE botid = {bot_id}"
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
    if not wait_time_interval(logger, notification, timeint, False):
        break
