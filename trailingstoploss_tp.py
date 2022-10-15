#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
from math import fabs
import os
import sqlite3
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.database import (
    get_next_process_time,
    set_next_process_time
)
from helpers.misc import (
    unix_timestamp_to_string,
    wait_time_interval
)
from helpers.threecommas import (
    init_threecommas_api
)

def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser(strict=False)
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

    cfgsectionprofitconfig = list()
    cfgsectionprofitconfig.append({
        "activation-percentage": "2.0",
        "activation-so-count": "0",
        "initial-stoploss-percentage": "0.5",
        "sl-timeout": "0",
        "sl-increment-factor": "0.0",
        "tp-increment-factor": "0.0",
    })
    cfgsectionprofitconfig.append({
        "activation-percentage": "3.0",
        "activation-so-count": "0",
        "initial-stoploss-percentage": "2.0",
        "sl-timeout": "0",
        "sl-increment-factor": "0.4",
        "tp-increment-factor": "0.4",
    })

    cfgsectionsafetyconfig = list()
    cfgsectionsafetyconfig.append({
        "activation-percentage": "-1.0",
        "increment-factor": "0.25",
        "limit-order-deviation": "0.00",
    })

    cfg["tsl_tp_default"] = {
        "botids": [12345, 67890],
        "profit-config": json.dumps(cfgsectionprofitconfig),
        "safety-config": json.dumps(cfgsectionsafetyconfig)
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
            "activation-so-count": cfg.get("settings", "activation-so-count"),
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

    for cfgsection in cfg.sections():
        if cfgsection.startswith("tsl_tp_"):
            if not cfg.has_option(cfgsection, "profit-config"):
                cfg.set(cfgsection, "profit-config", config.get(cfgsection, "config"))
                cfg.remove_option(cfgsection, "config")

                cfgsectionsafetyconfig = list()
                cfgsectionsafetyconfig.append({
                    "activation-percentage": "-1.0",
                    "increment-factor": "0.25",
                    "limit-order-deviation": "0.00",
                })

                cfg.set(cfgsection, "safety-config", json.dumps(cfgsectionsafetyconfig))

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info("Upgraded section %s to have profit- and safety- config list" % cfgsection)
            elif not cfg.has_option(cfgsection, "config") and not cfg.has_option(cfgsection, "profit-config"):
                cfgsectionconfig = list()
                cfgsectionconfig.append({
                    "activation-percentage": cfg.get(cfgsection, "activation-percentage"),
                    "activation-so-count": cfg.get("settings", "activation-so-count"),
                    "initial-stoploss-percentage": cfg.get(cfgsection, "initial-stoploss-percentage"),
                    "sl-timeout": cfg.get(cfgsection, "sl-timeout"),
                    "sl-increment-factor": cfg.get(cfgsection, "sl-increment-factor"),
                    "tp-increment-factor": cfg.get(cfgsection, "tp-increment-factor"),
                })


                cfg.set(cfgsection, "config", json.dumps(cfgsectionconfig))

                cfg.remove_option(cfgsection, "activation-percentage")
                cfg.remove_option(cfgsection, "initial-stoploss-percentage")
                cfg.remove_option(cfgsection, "sl-increment-factor")
                cfg.remove_option(cfgsection, "tp-increment-factor")

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info("Upgraded section %s to have config list" % cfgsection)
            elif cfg.has_option(cfgsection, "profit-config"):
                jsonconfiglist = list()
                for configsectionconfig in json.loads(cfg.get(cfgsection, "profit-config")):
                    if "activation-so-count" not in configsectionconfig:
                        cfgsectionconfig = {
                            "activation-percentage": configsectionconfig.get("activation-percentage"),
                            "activation-so-count": "0",
                            "initial-stoploss-percentage": configsectionconfig.get("initial-stoploss-percentage"),
                            "sl-timeout": configsectionconfig.get("sl-timeout"),
                            "sl-increment-factor": configsectionconfig.get("sl-increment-factor"),
                            "tp-increment-factor": configsectionconfig.get("tp-increment-factor"),
                        }
                        jsonconfiglist.append(cfgsectionconfig)

                if len(jsonconfiglist) > 0:
                    cfg.set(cfgsection, "config", json.dumps(jsonconfiglist))

                    with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                        cfg.write(cfgfile)

                    thelogger.info("Updates section %s to add activation-so-count" % cfgsection)

    return cfg


def update_deal_profit(thebot, deal, new_stoploss, new_take_profit, sl_timeout):
    """Update bot with new SL and TP."""

    bot_name = thebot["name"]
    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload={
            "deal_id": deal_id,
            "stop_loss_percentage": new_stoploss,
            "take_profit": new_take_profit,
            "stop_loss_timeout_enabled": sl_timeout > 0,
            "stop_loss_timeout_in_seconds": sl_timeout
        }
    )
    if data:
        logger.info(
            f"Changing SL for deal {deal['pair']} ({deal_id}) on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}%. "
            f"Changed TP from {deal['take_profit']}% to {new_take_profit}% "
            f"Changed SL timeout from {deal['stop_loss_timeout_in_seconds']}s to {sl_timeout}s."
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating deal with new SL/TP values: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred updating deal with new SL/TP valuess")


def get_data_for_add_funds(deal):
    """Get data for correctly adding funds."""

    deal_id = deal["id"]

    error, data = api.request(
        entity="deals",
        action="data_for_adding_funds",
        action_id=str(deal_id)
    )
    if data:
        logger.info(
            f"Data for adding funds to deal {deal['pair']} ({deal_id}): "
            f"Received response data: {data}"
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred retrieving data for adding funds to deal: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred retrieving data for adding funds to deal")


def update_deal_add_safety_funds(thebot, deal, quantity, limit_price):
    """Update bot with new Safety Order configuration."""

    bot_name = thebot["name"]
    deal_id = deal["id"]

    orderplaced = False

    error, data = api.request(
        entity="deals",
        action="add_funds",
        action_id=str(deal_id),
        payload={
            "quantity": quantity,
            "is_market": False,
            "rate": limit_price,
            "deal_id": deal_id,
        },
    )
    if data:
        logger.info(
            f"Adding funds for deal {deal['pair']} ({deal_id}) on bot \"{bot_name}\"\n"
            f"Add {quantity} at limit price {limit_price}."
            f"Received response data: {data}"
        )

        if data["status"] == "success":
            orderplaced = True
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred adding funds for safety to deal: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred adding funds for safety to deal")

    return orderplaced


def get_deal_open_safety_orders(deal):
    """Get the current open safety orders for the given deal."""

    deal_id = deal["id"]

    activeorderid = 0

    error, data = api.request(
        entity="deals",
        action="market_orders",
        action_id=str(deal_id)
    )
    if data:
        logger.info(
            f"Open Safety Orders for deal {deal['pair']} ({deal_id}): "
            f"Received response data: {data}"
        )

        for order in data:
            order_id = order["order_id"]
            order_type = order["deal_order_type"]
            order_status = order["status_string"]

            if order_type == "Manual Safety" and order_status == "Active":
                activeorderid = order_id
                logger.info(
                    f"Order {order_id} for {order_type} is {order_status}"
                )
                break
            else:
                logger.info(
                    f"Order {order_id} for {order_type} not what we are looking for!"
                )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred adding funds for safety to deal: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred adding funds for safety to deal")

    return activeorderid


def calculate_slpercentage_base_price_short(sl_price, base_price):
    """Calculate the SL percentage of the base price for a short deal"""

    return round(
        ((sl_price / base_price) * 100.0) - 100.0,
        2
    )


def calculate_slpercentage_base_price_long(sl_price, base_price):
    """Calculate the SL percentage of the base price for a long deal"""

    return round(
        100.0 - ((sl_price / base_price) * 100.0),
        2
    )


def calculate_average_price_sl_percentage_short(sl_price, average_price):
    """Calculate the SL percentage based on the average price for a short deal"""

    return round(
        100.0 - ((sl_price / average_price) * 100.0),
        2
    )


def calculate_average_price_sl_percentage_long(sl_price, average_price):
    """Calculate the SL percentage based on the average price for a long deal"""

    return round(
        ((sl_price / average_price) * 100.0) - 100.0,
        2
    )

def check_float(potential_float):
    """Check if the passed argument is a valid float"""

    try:
        float(potential_float)
        return True
    except ValueError:
        return False


def get_config_for_profit(section_profit_config, current_profit):
    """Get the settings from the config corresponding to the current profit"""

    profitconfig = {}

    for entry in section_profit_config:
        if current_profit >= float(entry["activation-percentage"]):
            profitconfig = entry
        else:
            break

    logger.debug(
        f"Profit config to use based on current profit {current_profit}% "
        f"is {profitconfig}"
    )

    return profitconfig


def get_config_for_safety(section_safety_config, current_profit):
    """Get the settings from the config corresponding to the current safety"""

    safetyconfig = {}

    for entry in section_safety_config:
        if current_profit <= float(entry["activation-percentage"]):
            safetyconfig = entry
        else:
            break

    logger.debug(
        f"Safety config to use based on current profit {current_profit}% "
        f"is {safetyconfig}"
    )

    return safetyconfig


def process_deals(thebot, section_profit_config, section_safety_config):
    """Check deals from bot, compare against the database and handle them."""

    monitored_deals = 0

    botid = thebot["id"]
    deals = thebot["active_deals"]

    if deals:
        current_deals = []

        for deal in deals:
            deal_id = deal["id"]

            logger.info(deal)

            if deal["strategy"] in ("short", "long"):
                # Check whether the actual_profit_percentage can be obtained from the deal,
                # If it can't, skip this deal.

                if not check_float(deal["actual_profit_percentage"]):
                    logger.info(
                        f"\"{thebot['name']}\": {deal['pair']}/{deal['id']} does no longer "
                        f"exist on the exchange! Cancel or handle deal manually on 3Commas!",
                        True # Make sure the user can see this message on Telegram
                    )
                    continue

                current_deals.append(deal_id)

                if is_new_deal(cursor, deal_id):
                    # New deal, so add to database
                    add_deal_in_db(deal_id, botid)

                if float(deal["actual_profit_percentage"]) >= 0.0:
                    # Deal is in positive profit, so TSL mode which requires the profit-config
                    deal_db_data = get_deal_profit_db_data(cursor, deal_id)


                    actual_profit_config = get_config_for_profit(
                        section_profit_config, float(deal["actual_profit_percentage"])
                        )

                    if actual_profit_config:
                        monitored_deals += handle_deal_profit(
                                thebot, deal, deal_db_data, actual_profit_config
                            )
                else:
                    # Deal is negative profit, so SO mode. SO mode requires the total % drop
                    deal_db_data = get_deal_safety_db_data(cursor, deal_id)

                    totalnegativeprofit = ((float(deal["current_price"]) / float(deal["base_order_average_price"])) * 100.0) - 100.0

                    actual_safety_config = get_config_for_safety(
                            section_safety_config, totalnegativeprofit
                        )

                    monitored_deals += handle_deal_safety(
                                thebot, deal, deal_db_data, actual_safety_config, totalnegativeprofit
                            )
            else:
                logger.warning(
                    f"Unknown strategy {deal['strategy']} for deal {deal_id}"
                )

        # Housekeeping, clean things up and prevent endless growing database
        remove_closed_deals(botid, current_deals)

        logger.debug(
            f"Bot \"{thebot['name']}\" ({botid}) has {len(deals)} deal(s) "
            f"of which {monitored_deals} require monitoring."
        )
    else:
        logger.debug(
            f"Bot \"{thebot['name']}\" ({botid}) has no active deals."
        )
        remove_all_deals(botid)

    return monitored_deals


def calculate_sl_percentage(deal_data, profit_config, activation_diff):
    """Calculate the SL percentage in 3C range"""

    initial_stoploss_percentage = float(profit_config.get("initial-stoploss-percentage"))
    sl_increment_factor = float(profit_config.get("sl-increment-factor"))

    # SL is calculated by 3C on base order price. Because of filled SO's,
    # we must first calculate the SL price based on the average price
    average_price = 0.0
    if deal_data["strategy"] == "short":
        average_price = float(deal_data["sold_average_price"])
    else:
        average_price = float(deal_data["bought_average_price"])

    # Calculate the amount we need to substract or add to the average price based
    # on the configured increments and activation
    percentage_price = average_price * ((initial_stoploss_percentage / 100.0)
                                        + ((activation_diff / 100.0) * sl_increment_factor))

    sl_price = average_price
    if deal_data["strategy"] == "short":
        sl_price -= percentage_price
    else:
        sl_price += percentage_price

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: SL price {sl_price} calculated based on average "
        f"price {average_price}, initial SL of {initial_stoploss_percentage}, "
        f"activation diff of {activation_diff} and sl factor {sl_increment_factor}"
    )

    # Now we know the SL price, let's calculate the percentage from
    # the base order price so we have the desired SL for 3C
    base_price = float(deal_data["base_order_average_price"])
    base_price_sl_percentage = 0.0

    if deal_data["strategy"] == "short":
        base_price_sl_percentage = calculate_slpercentage_base_price_short(
                sl_price, base_price
            )
    else:
        base_price_sl_percentage = calculate_slpercentage_base_price_long(
                sl_price, base_price
            )

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: base SL of {base_price_sl_percentage}% calculated "
        f"based on base price {base_price} and SL price {sl_price}."
    )

    return average_price, sl_price, base_price_sl_percentage


### Misschien niet meer nodig??
def handle_new_deal(thebot, deal, profit_config):
    """New deal (short or long) to activate SL on"""

    botid = thebot["id"]
    actual_profit_percentage = float(deal["actual_profit_percentage"])

    activation_percentage = float(profit_config.get("activation-percentage"))

    sl_timeout = int(profit_config.get("sl-timeout"))

    # Take space between trigger and actual profit into account
    activation_diff = actual_profit_percentage - activation_percentage

    # SL data contains three values:
    # 0. The sold or bought average price
    # 1. The calculated SL price
    # 2. The SL percentage on 3C axis (inverted range compared to TP axis)
    sl_data = calculate_sl_percentage(deal, profit_config, activation_diff)

    if sl_data[2] != 0.00:
        # Calculate understandable SL percentage (TP axis range) based on average price
        average_price_sl_percentage = 0.0

        if deal["strategy"] == "short":
            average_price_sl_percentage = calculate_average_price_sl_percentage_short(
                    sl_data[1], sl_data[0]
                )
        else:
            average_price_sl_percentage = calculate_average_price_sl_percentage_long(
                    sl_data[1], sl_data[0]
                )

        logger.debug(
            f"{deal['pair']}/{deal['id']}: average SL of {average_price_sl_percentage}% "
            f"calculated based on average price {sl_data[0]} and "
            f"SL price {sl_data[1]}."
        )

        # Calculate new TP percentage
        current_tp_percentage = float(deal["take_profit"])
        new_tp_percentage = round(
            current_tp_percentage
            + (activation_diff * float(profit_config.get("tp-increment-factor"))),
            2
        )

        logger.info(
            f"\"{thebot['name']}\": {deal['pair']}/{deal['id']} "
            f"profit ({actual_profit_percentage}%) above activation ({activation_percentage}%). "
            f"StopLoss activated on {average_price_sl_percentage}%.",
            True
        )

        logger.info(
            f"StopLoss timeout set at {sl_timeout}s",
            True
        )

        if new_tp_percentage > current_tp_percentage:
            logger.info(
                f"TakeProfit increased from {current_tp_percentage}% "
                f"to {new_tp_percentage}%",
                True
            )

        # Update deal in 3C
        update_deal_profit(thebot, deal, sl_data[2], new_tp_percentage, sl_timeout)

        # Add deal to our database
        add_deal_in_db(
            deal["id"], botid, actual_profit_percentage, average_price_sl_percentage, new_tp_percentage
        )
    else:
        logger.debug(
            f"{deal['pair']}/{deal['id']}: calculated SL of {sl_data[2]} which "
            f"will cause 3C not to activate SL. No action taken!"
        )


def handle_deal_profit(thebot, deal, deal_db_data, profit_config):
    """Update deal (short or long) and increase SL (Trailing SL) when profit has increased."""

    deal_monitored = 0

    if not deal['completed_safety_orders_count'] >= int(profit_config.get("activation-so-count")):
        logger.debug(
            f"\"{thebot['name']}\": {deal['pair']}/{deal['id']} has lower active safety orders then "
            f"configured"
        )
        return deal_monitored

    actual_profit_percentage = float(deal["actual_profit_percentage"])
    last_profit_percentage = float(deal_db_data["last_profit_percentage"])

    if actual_profit_percentage > last_profit_percentage:
        sl_increment_factor = float(profit_config.get("sl-increment-factor"))
        tp_increment_factor = float(profit_config.get("tp-increment-factor"))

        if sl_increment_factor > 0.0 or tp_increment_factor > 0.0:
            activation_diff = actual_profit_percentage - float(profit_config.get("activation-percentage"))

            # SL data contains three values:
            # 0. The sold or bought average price
            # 1. The calculated SL price
            # 2. The SL percentage on 3C axis (inverted range compared to TP axis)
            sl_data = calculate_sl_percentage(deal, profit_config, activation_diff)

            current_sl_percentage = float(deal["stop_loss_percentage"])
            if fabs(sl_data[2]) > 0.0 and sl_data[2] != current_sl_percentage:
                new_sl_timeout = int(profit_config.get("sl-timeout"))

                # Calculate understandable SL percentage (TP axis range) based on average price
                new_average_price_sl_percentage = 0.0

                if deal["strategy"] == "short":
                    new_average_price_sl_percentage = calculate_average_price_sl_percentage_short(
                            sl_data[1], sl_data[0]
                        )
                else:
                    new_average_price_sl_percentage = calculate_average_price_sl_percentage_long(
                            sl_data[1], sl_data[0]
                        )

                logger.debug(
                    f"{deal['pair']}/{deal['id']}: new average SL "
                    f"of {new_average_price_sl_percentage}% calculated "
                    f"based on average price {sl_data[0]} and "
                    f"SL price {sl_data[1]}."
                )

                logger.info(
                    f"\"{thebot['name']}\": {deal['pair']}/{deal['id']} profit increased "
                    f"from {last_profit_percentage}% to {actual_profit_percentage}%. "
                    f"StopLoss increased from {deal_db_data['last_readable_sl_percentage']}% to "
                    f"{new_average_price_sl_percentage}%. ",
                    True
                )

                # Calculate new TP percentage based on the increased profit and increment factor
                current_tp_percentage = float(deal["take_profit"])
                new_tp_percentage = round(
                    current_tp_percentage + (
                            (actual_profit_percentage - last_profit_percentage)
                            * tp_increment_factor
                        ), 2
                )

                if new_tp_percentage > current_tp_percentage:
                    logger.info(
                        f"TakeProfit increased from {current_tp_percentage}% "
                        f"to {new_tp_percentage}%",
                        True
                    )

                # Check whether there is an old timeout, and log when the new time out is different
                current_sl_timeout = deal["stop_loss_timeout_in_seconds"]
                if current_sl_timeout is not None and current_sl_timeout != new_sl_timeout:
                    logger.info(
                        f"StopLoss timeout changed from {current_sl_timeout}s "
                        f"to {new_sl_timeout}s",
                        True
                    )

                # Update deal in 3C
                update_deal_profit(thebot, deal, sl_data[2], new_tp_percentage, new_sl_timeout)

                # Update deal in our database
                update_profit_in_db(
                    deal['id'], actual_profit_percentage, new_average_price_sl_percentage, new_tp_percentage
                )
            else:
                logger.debug(
                    f"{deal['pair']}/{deal['id']}: calculated SL of {sl_data[2]}% which "
                    f"is equal to current SL {current_sl_percentage}% or "
                    f"is 0.0 which causes 3C to deactive SL; no change made!"
                )

            # SL calculated, so deal must be monitored for any changes (even if an invalid SL has been calculated)
            deal_monitored = 1
        else:
            logger.debug(
                f"{deal['pair']}/{deal['id']}: profit increased from {last_profit_percentage}% "
                f"to {actual_profit_percentage}%, but increment factors are 0.0 so "
                f"no change required for this deal."
            )
    else:
        logger.debug(
            f"{deal['pair']}/{deal['id']}: no profit increase "
            f"(current: {actual_profit_percentage}%, "
            f"previous: {last_profit_percentage}%). Keep on monitoring."
        )

    return deal_monitored


def is_new_deal(cursor, dealid):
    """Return True if the deal is not know yet, otherwise False"""

    if cursor.execute(f"SELECT * FROM deal_profit WHERE dealid = {dealid}").fetchone():
        return False

    return True


def get_deal_profit_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_profit WHERE dealid = {dealid}").fetchone()


def get_deal_safety_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_safety WHERE dealid = {dealid}").fetchone()


def remove_closed_deals(bot_id, current_deals):
    """Remove all deals for the given bot, except the ones in the list."""

    if current_deals:
        # Remove start and end square bracket so we can properly use it
        current_deals_str = str(current_deals)[1:-1]

        logger.debug(f"Deleting old deals from bot {bot_id} except {current_deals_str}")
        db.execute(
            f"DELETE FROM deal_profit WHERE botid = {bot_id} AND dealid NOT IN ({current_deals_str})"
        )
        db.execute(
            f"DELETE FROM deal_safety WHERE botid = {bot_id} AND dealid NOT IN ({current_deals_str})"
        )

        db.commit()


def remove_all_deals(bot_id):
    """Remove all stored deals for the specified bot."""

    logger.debug(
        f"Removing all stored deals for bot {bot_id}."
    )

    db.execute(
        f"DELETE FROM deal_profit WHERE botid = {bot_id}"
    )
    db.execute(
        f"DELETE FROM deal_safety WHERE botid = {bot_id}"
    )

    db.commit()


def get_bot_next_process_time(bot_id):
    """Get the next processing time for the specified bot."""

    dbrow = cursor.execute(
            f"SELECT next_processing_timestamp FROM bots WHERE botid = {bot_id}"
        ).fetchone()

    nexttime = int(time.time())
    if dbrow is not None:
        nexttime = dbrow["next_processing_timestamp"]
    else:
        # Record missing, create one
        set_bot_next_process_time(bot_id, nexttime)

    return nexttime


def set_bot_next_process_time(bot_id, new_time):
    """Set the next processing time for the specified bot."""

    logger.debug(
        f"Next processing for bot {bot_id} not before "
        f"{unix_timestamp_to_string(new_time, '%Y-%m-%d %H:%M:%S')}."
    )

    db.execute(
        f"REPLACE INTO bots (botid, next_processing_timestamp) "
        f"VALUES ({bot_id}, {new_time})"
    )

    db.commit()


def add_deal_in_db(deal_id, bot_id):
    """Add default data for deal (short or long) to database."""

    db.execute(
        f"INSERT INTO deal_profit ("
        f"dealid, "
        f"botid, "
        f"last_profit_percentage, "
        f"last_readable_sl_percentage, "
        f"last_readable_tp_percentage "
        f") VALUES ("
        f"{deal_id}, {bot_id}, {0.0}, {0.0}, {0.0}"
        f")"
    )
    db.execute(
        f"INSERT INTO deal_safety ("
        f"dealid, "
        f"botid, "
        f"min_profit_percentage, "
        f"buy_on_percentage, "
        f"filled_so_count, "
        f"next_so_percentage, "
        f"manual_safety_order_id "
        f") VALUES ("
        f"{deal_id}, {bot_id}, {0.0}, {0.0}, {0.0}, {0.0}, {0.0}"
        f")"
    )

    db.commit()


def update_profit_in_db(deal_id, tp_percentage, readable_sl_percentage, readable_tp_percentage):
    """Update deal profit related fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_profit SET "
        f"last_profit_percentage = {tp_percentage}, "
        f"last_readable_sl_percentage = {readable_sl_percentage}, "
        f"last_readable_tp_percentage = {readable_tp_percentage} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()


def update_safetyorder_in_db(deal_id, filled_so_count, next_so_percentage, so_order_id):
    """Update deal safety related fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"filled_so_count = {filled_so_count}, "
        f"next_so_percentage = {next_so_percentage}, "
        f"manual_safety_order_id = {so_order_id} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()


def update_safetyorder_monitor_in_db(deal_id, min_profit_percentage, buy_on_percentage):
    """Update deal safety monitor fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"min_profit_percentage = {min_profit_percentage}, "
        f"buy_on_percentage = {buy_on_percentage} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()

###################################################################################################################################################
def handle_deal_safety(thebot, deal, deal_db_data, safety_config, total_negative_profit):
    """Handle the Safety Orders for this deal."""

    deal_monitored = 0

    # Debug data, remove later...
    logger.info(
        f"Processing deal {deal['id']} with current profit {float(deal['actual_profit_percentage'])}%. Total is {total_negative_profit}%. \n"
        f"Max SO: {deal['max_safety_orders']}, Active: {deal['active_safety_orders_count']}, Current active: {deal['current_active_safety_orders_count']}, Completed: {deal['completed_safety_orders_count']}. "
        f"Manual SO active: {deal['active_manual_safety_orders']}, Completed manual SO: {deal['completed_manual_safety_orders_count']}. "
        f"Stored bought SO: {deal_db_data['filled_so_count']}"
    )

    logger.info(f"Total negative profit: {total_negative_profit}, next: {deal_db_data['next_so_percentage']}")


    actual_absolute_profit_percentage = fabs(total_negative_profit)
    last_profit_percentage = float(deal_db_data["min_profit_percentage"])

    if actual_absolute_profit_percentage > last_profit_percentage:
        current_buy_on_percentage = deal_db_data["buy_on_percentage"]
        increment_factor = float(safety_config.get("increment-factor"))

        new_buy_on_percentage = round(
            current_buy_on_percentage + (
                    (actual_absolute_profit_percentage - last_profit_percentage)
                    * increment_factor
                ), 2
        )

        logger.info(
            f"\"{thebot['name']}\": {deal['pair']}/{deal['id']} profit decreased "
            f"from {last_profit_percentage}% to {actual_absolute_profit_percentage}%. "
            f"Buy decreased from {current_buy_on_percentage}% to "
            f"{new_buy_on_percentage}%. ",
            True
        )

        # Update last_drop_percentage in db
        update_safetyorder_monitor_in_db(deal["id"], actual_absolute_profit_percentage, new_buy_on_percentage)


    # Only process the deal when no manual SO is pending and the negative profit has reached the buy moment
    if deal_db_data['filled_so_count'] == deal['max_safety_orders']:
        logger.info("Max SO reached!")
    elif deal['active_manual_safety_orders'] > 0:
        logger.info("Manual Safety Order in progress, wait for it to complete.")
    else:
        #if fabs(total_negative_profit) > deal_db_data["next_so_percentage"]:
        if actual_absolute_profit_percentage <= new_buy_on_percentage:
            # SO data contains four values:
            # 0. The number of configured Safety Orders to be filled using a Manual trade
            # 1. The total volume for those number of Safety Orders
            # 2. The buy price of that volume
            # 3. The next total negative profit percentage on which the next Safety Order is configured
            sodata = calculate_safety_order(thebot, deal, deal_db_data, total_negative_profit)

            logger.info(
                f"SO data: {sodata}..."
            )

            if sodata[0] > 0:
                logger.info("Adding safety funds for deal...")

                so_price = sodata[2]
                if so_price > float(deal["current_price"]):
                    logger.info(
                        f"Current price {deal['current_price']} lower than so price {so_price}"
                    )
                    so_price = float(deal["current_price"])

                limitorderdeviation = float(safety_config.get("limit-order-deviation"))
                if limitorderdeviation != 0.00:
                    new_so_price = so_price + ((so_price / 100.0) * limitorderdeviation)

                    logger.info(f"Updated so price from {so_price} to {new_so_price} based on deviation {limitorderdeviation}")
                    so_price = new_so_price

                quantity = sodata[1] / so_price
                logger.info(
                    f"Quantity based on volume {sodata[1]} and price {so_price}; {quantity} "
                )

                get_data_for_add_funds(deal)

                if update_deal_add_safety_funds(thebot, deal, quantity, so_price):
                    orderid = get_deal_open_safety_orders(deal)

                    newtotalso = deal_db_data["filled_so_count"] + sodata[0]
                    logger.info(
                        f"Updating deal {deal['id']} SO to {newtotalso} and next SO on {sodata[3]}%"
                        f"Open order is {orderid}"
                    )
                    update_safetyorder_in_db(deal["id"], newtotalso, sodata[3], orderid)
                else:
                    logger.error(
                        f"Failed to add Manual SO for deal {deal['id']}"
                    )
            elif deal_db_data["next_so_percentage"] == 0.0 or sodata[3] > deal_db_data["next_so_percentage"]:
                logger.info(f"Updating next so percentage to {sodata[3]}%")
                update_safetyorder_in_db(deal["id"], deal_db_data["filled_so_count"], sodata[3], 0)
            else:
                logger.info("No safety funds for deal required at this time")
        else:
            logger.info(f"Profit has not reached next so at {deal_db_data['next_so_percentage']}")

    return deal_monitored


def calculate_safety_order(thebot, deal_data, deal_db_data, total_negative_profit):
    """Calculate the next SO order."""

    # Return values
    sobuycount = 0
    sobuyvolume = 0.0
    sobuyprice = 0.0
    sonextdroppercentage = 0.0

    # Default values before calculation(s)
    sovolume = totalvolume = 0.0
    sopercentagedropfrombaseprice = percentagetotaldrop = 0.0
    sobuyprice = 0.0

    # The SO loop
    socounter = 0
    while socounter < deal_data['max_safety_orders']:
        # Print data of SO we are currently at
        logger.info(
            f"At SO {socounter} --- Volume: {sovolume}/{totalvolume}, Drop: {sopercentagedropfrombaseprice}/{percentagetotaldrop}, Price: {sobuyprice}"
        )

        # Calculate data for the next SO
        nextsovolume = 0.0
        nextsopercentagedropfrombaseprice = 0.0

        if socounter == 0:
            nextsovolume = float(thebot["safety_order_volume"])
            nextsopercentagedropfrombaseprice = float(thebot["safety_order_step_percentage"])
        else:
            nextsovolume = float(sovolume) * float(thebot["martingale_volume_coefficient"])
            nextsopercentagedropfrombaseprice = float(sopercentagedropfrombaseprice) * float(thebot["martingale_step_coefficient"])

        nextsototalvolume = totalvolume + nextsovolume
        nextsopercentagetotaldrop = percentagetotaldrop + nextsopercentagedropfrombaseprice
        nextsobuyprice = float(deal_data["base_order_average_price"])  * ((100.0 - nextsopercentagetotaldrop) / 100.0)

        # Print data for next SO
        logger.info(
            f"Calculated next SO {socounter + 1} --- Volume: {nextsovolume}/{nextsototalvolume}, Drop: {nextsopercentagedropfrombaseprice}/{nextsopercentagetotaldrop}, Price: {nextsobuyprice}"
        )

        # Descision making :) Optimize later...
        if socounter < deal_db_data["filled_so_count"]:
            logger.info(f"SO {socounter} already filled!")

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            percentagetotaldrop = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice

            socounter += 1
        elif nextsopercentagetotaldrop <= fabs(total_negative_profit):
            logger.info(f"Next SO {socounter + 1} not filled and required based on (negative) profit!")

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            percentagetotaldrop = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice

            socounter += 1

            sobuycount += 1
            sobuyvolume += nextsovolume
            sobuyprice = nextsobuyprice
        elif nextsopercentagetotaldrop > fabs(total_negative_profit):
            logger.info(f"Next SO {socounter + 1} not filled and not required! Stop at SO {socounter}")

            sonextdroppercentage = nextsopercentagetotaldrop

            break
        else:
            logger.info("BIG ERROR, unhandled case!")
            sys.exit(1)

    logger.info(
        f"SO level {socounter} reached. Need to buy {sobuycount} - {sobuyvolume}/{sobuyprice}! Next SO at {sonextdroppercentage}"
    )

    return sobuycount, sobuyvolume, sobuyprice, sonextdroppercentage


#######################################################################################################################################################

def open_tsl_db():
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
            "CREATE TABLE IF NOT EXISTS deal_profit ("
            "dealid INT Primary Key, "
            "botid INT, "
            "last_profit_percentage FLOAT, "
            "last_readable_sl_percentage FLOAT, "
            "last_readable_tp_percentage FLOAT"
            ")"
        )

        dbcursor.execute(
            "CREATE TABLE IF NOT EXISTS deal_safety ("
            "dealid INT Primary Key, "
            "botid INT, "
            "min_profit_percentage FLOAT, "
            "buy_on_percentage FLOAT, "
            "filled_so_count INT, "
            "next_so_percentage FLOAT, "
            "manual_safety_order_id INT "
            ")"
        )

        dbcursor.execute(
            "CREATE TABLE IF NOT EXISTS bots ("
            "botid INT Primary Key, "
            "next_processing_timestamp INT"
            ")"
        )

        logger.info("Database tables created successfully")

    return dbconnection


def upgrade_trailingstoploss_tp_db():
    """Upgrade database if needed."""

    # Changes required for readable SL percentages
    try:
        try:
            # DROP column supported from sqlite 3.35.0 (2021.03.12)
            cursor.execute("ALTER TABLE deals DROP COLUMN last_stop_loss_percentage")
        except sqlite3.OperationalError:
            logger.debug("Older SQLite version; not used column not removed")

        cursor.execute("ALTER TABLE deals ADD COLUMN last_readable_sl_percentage FLOAT DEFAULT 0.0")
        cursor.execute("ALTER TABLE deals ADD COLUMN last_readable_tp_percentage FLOAT DEFAULT 0.0")

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS bots ("
            "botid INT Primary Key, "
            "next_processing_timestamp INT"
            ")"
        )

        logger.info("Database schema upgraded for readable percentages")
    except sqlite3.OperationalError:
        logger.debug("Database schema up-to-date for readable percentages")

    # Changes required for handling Safety Orders
    try:
        cursor.execute("ALTER TABLE deals RENAME TO deal_profit")

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS deal_safety ("
            "dealid INT Primary Key, "
            "botid INT, "
            "min_profit_percentage FLOAT, "
            "buy_on_percentage FLOAT, "
            "filled_so_count INT, "
            "next_so_percentage FLOAT, "
            "manual_safety_order_id INT "
            ")"
        )

        logger.info("Database schema upgraded for safety orders")
    except sqlite3.OperationalError:
        logger.debug("Database schema up-to-date for safety orders")


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
db = open_tsl_db()
cursor = db.cursor()

# Upgrade the database if needed
upgrade_trailingstoploss_tp_db()

# TrailingStopLoss and TakeProfit %
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    check_interval = int(config.get("settings", "check-interval"))
    monitor_interval = int(config.get("settings", "monitor-interval"))

    # Used to determine the correct interval
    deals_to_monitor = 0

    # Current time to determine which bots to process
    starttime = int(time.time())

    for section in config.sections():
        if section.startswith("tsl_tp_"):
            # Bot configuration for section
            botids = json.loads(config.get(section, "botids"))

            # Get and check the profit-config for this section
            sectionprofitconfig = json.loads(config.get(section, "profit-config"))
            if len(sectionprofitconfig) == 0:
                logger.warning(
                    f"Section {section} has an empty \'profit-config\'. Skipping this section!"
                )
                continue

            sectionsafetyconfig = json.loads(config.get(section, "safety-config"))
            if len(sectionsafetyconfig) == 0:
                logger.warning(
                    f"Section {section} has an empty \'safety-config\'. Skipping this section!"
                )
                continue

            # Walk through all bots configured
            for bot in botids:
                nextprocesstime = get_next_process_time(db, "bots", "botid", bot)

                # Only process the bot if it's time for the next interval, or
                # time exceeds the check interval (clock has changed somehow)
                if starttime >= nextprocesstime or (
                        abs(nextprocesstime - starttime) > check_interval
                ):
                    boterror, botdata = api.request(
                        entity="bots",
                        action="show",
                        action_id=str(bot),
                    )
                    if botdata:
                        bot_deals_to_monitor = process_deals(botdata, sectionprofitconfig, sectionsafetyconfig)

                        # Determine new time to process this bot, based on the monitored deals
                        newtime = starttime + (
                                check_interval if bot_deals_to_monitor == 0 else monitor_interval
                            )
                        set_next_process_time(db, "bots", "botid", bot, newtime)

                        deals_to_monitor += bot_deals_to_monitor
                    else:
                        if boterror and "msg" in boterror:
                            logger.error("Error occurred updating bots: %s" % boterror["msg"])
                        else:
                            logger.error("Error occurred updating bots")
                else:
                    logger.debug(
                        f"Bot {bot} will be processed after "
                        f"{unix_timestamp_to_string(nextprocesstime, '%Y-%m-%d %H:%M:%S')}."
                    )
        elif section not in ("settings"):
            logger.warning(
                f"Section '{section}' not processed (prefix 'tsl_tp_' missing)!",
                False
            )

    timeint = check_interval if deals_to_monitor == 0 else monitor_interval
    if not wait_time_interval(logger, notification, timeint, False):
        break
