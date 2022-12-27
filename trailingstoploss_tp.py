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
    get_threecommas_deal_active_manual_safety_order,
    init_threecommas_api,
    threecommas_deal_add_funds
)
from helpers.trailingstoploss_tp import (
    calculate_average_price_sl_percentage_long,
    calculate_average_price_sl_percentage_short,
    calculate_safety_order,
    calculate_slpercentage_base_price_long,
    calculate_slpercentage_base_price_short,
    check_float,
    get_profit_db_data,
    get_safety_db_data,
    is_new_deal
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
        "activation-percentage": "0.25",
        "activation-so-count": "0",
        "initial-buy-percentage": "0.0",
        "buy-increment-factor": "0.50",
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

    dealupdated = False

    bot_name = thebot["name"]
    deal_id = deal["id"]

    payload = {
        "deal_id": thebot["id"],
        "stop_loss_percentage": new_stoploss,
        "stop_loss_timeout_enabled": sl_timeout > 0,
        "stop_loss_timeout_in_seconds": sl_timeout
    }

    # Only update TP values when no conditional take profit is used
    # Note: currently the API does not support this. Script cannot be used for MP deals yet!
    #if not len(thebot['close_strategy_list']):
    #    payload["take_profit"] = new_take_profit
    #    payload["trailing_enabled"] = False
    #else:
    #    payload["take_profit"] = 0.05
    #    payload["trailing_enabled"] = False
    payload["take_profit"] = new_take_profit
    payload["trailing_enabled"] = deal["trailing_enabled"]
    payload["tsl_enabled"] = deal["tsl_enabled"]

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_id),
        payload=payload
    )

    if data:
        dealupdated = True

        logger.info(
            f"Changing SL for deal {deal['pair']}/{deal['id']} on bot \"{bot_name}\"\n"
            f"Changed SL from {deal['stop_loss_percentage']}% to {new_stoploss}%. "
            f"Changed TP from {deal['take_profit']}% to {new_take_profit}%. "
            f"Changed SL timeout from {deal['stop_loss_timeout_in_seconds']}s to {sl_timeout}s."
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating deal with new SL/TP values: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred updating deal with new SL/TP valuess")

    return dealupdated


#def get_data_for_add_funds(deal):
#    """Get data for correctly adding funds."""
#
#    deal_id = deal["id"]
#
#    error, data = api.request(
#        entity="deals",
#        action="data_for_adding_funds",
#        action_id=str(deal_id)
#    )
#    if data:
#        logger.info(
#            f"Data for adding funds to deal {deal['pair']}/{deal['id']}: "
#            f"Received response data: {data}"
#        )
#    else:
#        if error and "msg" in error:
#            logger.error(
#                "Error occurred retrieving data for adding funds to deal: %s" % error["msg"]
#            )
#        else:
#            logger.error("Error occurred retrieving data for adding funds to deal")


def get_settings(section_config: dict, current_profit: float, current_so_level: int) -> dict:
    """
        Get the settings from the config corresponding to the current profit
        and current so level.

        @param section_config: The config section to check
        @param current_profit: The profit percentage of the current deal
        @param current_so_level: The filled safety order count of the current deal

        @return: The last matching config entry if there are multiple matches or an empty dict
    """

    settings = {}

    for entry in section_config:
        if (current_profit >= float(entry["activation-percentage"]) and
            current_so_level >= int(entry["activation-so-count"])):
            settings = entry

    if settings:
        logger.debug(
            f"Settings to use based on current profit {current_profit}% "
            f"and current so count {current_so_level} is {settings}"
        )
    else:
        logger.debug(
            f"No settings found based on current profit {current_profit}% "
            f"and so count {current_so_level}."
        )

    return settings


def process_deals(bot_data, section_profit_config, section_safety_config):
    """Check deals from bot, compare against the database and handle them."""

    monitored_deals = 0

    botid = bot_data["id"]
    deals = bot_data["active_deals"]

    if deals:
        current_deals = []

        for deal in deals:
            if deal["strategy"] in ("short", "long"):
                # Check whether the actual_profit_percentage can be obtained from the deal,
                # If it can't, skip this deal.

                if not check_float(deal["actual_profit_percentage"]):
                    logger.warning(
                        f"\"{bot_data['name']}\": {deal['pair']}/{deal['id']} does no longer "
                        f"exist on the exchange! Cancel or handle deal manually on 3Commas!"
                    )
                    continue

                current_deals.append(deal["id"])

                if is_new_deal(cursor, deal["id"]):
                    add_deal_in_db(deal["id"], botid)

                    # Only deals without 3C Safety Orders active can be processed by this script
                    if deal['active_safety_orders_count'] == 0:
                        set_first_safety_order(bot_data, deal, 0, 0.0)

                if float(deal["actual_profit_percentage"]) >= 0.0:
                    monitored_deals += process_deal_for_profit(
                        section_profit_config, bot_data, deal
                    )
                else:
                    #Todo: implement this also for short deals
                    if deal["strategy"] == "long":
                        monitored_deals += process_deal_for_safety_order(
                            section_safety_config, bot_data, deal
                        )
            else:
                logger.warning(
                    f"Unknown strategy {deal['strategy']} for deal {deal['id']}"
                )

        # Housekeeping, clean things up and prevent endless growing database
        remove_closed_deals(botid, current_deals)

        logger.debug(
            f"Bot \"{bot_data['name']}\" ({botid}) has {len(deals)} deal(s) "
            f"of which {monitored_deals} require monitoring."
        )
    else:
        logger.debug(
            f"Bot \"{bot_data['name']}\" ({botid}) has no active deals."
        )
        remove_all_deals(botid)

    return monitored_deals


def process_deal_for_profit(section_profit_config, bot_data, deal_data):
    """Process a deal which has positive profit"""

    requiremonitoring = 0

    # Deal is in positive profit, so TSL mode which requires the profit-config
    deal_db_data = get_profit_db_data(cursor, deal_data["id"])

    profit_config = get_settings(
        section_profit_config,
        float(deal_data["actual_profit_percentage"]),
        int(deal_data['completed_safety_orders_count'])
    )

    # Available profit_config means trailing must be applied. So for deals
    # which have not reached the desired profit yet,
    # no profit_config can be found.
    if profit_config:
        requiremonitoring = handle_deal_profit(
                bot_data, deal_data, deal_db_data, profit_config
            )

    return requiremonitoring


def process_deal_for_safety_order(section_safety_config, bot_data, deal_data):
    """Process a deal which has negative profit"""

    requiremonitoring = 0

    # Deal is in negative profit, so SO mode.
    if deal_data['active_safety_orders_count'] == 0:
        deal_db_data = get_safety_db_data(cursor, deal_data["id"])

        # SO mode requires the total % drop without filled safety oders
        totalprofit = round(fabs(
            ((float(deal_data["current_price"]) /
            float(deal_data["base_order_average_price"])) * 100.0) - 100.0
        ),2)
        sorelativeprofit = totalprofit - deal_db_data["next_so_percentage"]

        if sorelativeprofit >= 0.0:
            safety_config = get_settings(
                    section_safety_config, sorelativeprofit, deal_db_data["filled_so_count"]
                )

            requiremonitoring = handle_deal_safety(
                        bot_data, deal_data, deal_db_data, safety_config, totalprofit
                    )
        else:
            logger.debug(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} has not "
                f"yet reached next SO at {deal_db_data['next_so_percentage']}%."
            )
    else:
        logger.warning(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} has "
            f"active Safety Orders by bot configuration which will break the "
            f"functionality of this script. Not processing this deal!"
        )

    return requiremonitoring


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


def handle_deal_profit(bot_data, deal_data, deal_db_data, profit_config):
    """Update deal (short or long) and increase SL (Trailing SL) when profit has increased."""

    requiremonitoring = 0

    if not deal_data['completed_safety_orders_count'] >= int(profit_config.get("activation-so-count")):
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} has "
            f"lower active safety orders then configured"
        )
        return requiremonitoring

    current_profit_percentage = float(deal_data["actual_profit_percentage"])
    last_profit_percentage = float(deal_db_data["last_profit_percentage"])

    if current_profit_percentage >= float(deal_data["take_profit"]):
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: current profit {current_profit_percentage} "
            f"above take profit, so there is no point in updating TP and/or SL value. "
            f"Deal should be closed by 3C any moment now."
        )
    elif current_profit_percentage > last_profit_percentage:
        tp_increment_factor = float(profit_config.get("tp-increment-factor"))

        activation_diff = (
            current_profit_percentage - float(profit_config.get("activation-percentage"))
        )

        # SL data contains three values:
        # 0. The sold or bought average price
        # 1. The calculated SL price
        # 2. The SL percentage on 3C axis (inverted range compared to TP axis)
        sl_data = calculate_sl_percentage(deal_data, profit_config, activation_diff)

        current_sl_percentage = float(deal_data["stop_loss_percentage"])

        # Only calculate and update deal when SL has changed or TP will be changed
        if (fabs(sl_data[2]) > 0.0 and sl_data[2] != current_sl_percentage) or (tp_increment_factor > 0.0):
            new_sl_timeout = int(profit_config.get("sl-timeout"))

            # Calculate understandable SL percentage (TP axis range) based on average price
            new_average_price_sl_percentage = 0.0

            if deal_data["strategy"] == "short":
                new_average_price_sl_percentage = calculate_average_price_sl_percentage_short(
                        sl_data[1], sl_data[0]
                    )
            else:
                new_average_price_sl_percentage = calculate_average_price_sl_percentage_long(
                        sl_data[1], sl_data[0]
                    )

            logger.debug(
                f"{deal_data['pair']}/{deal_data['id']}: new average SL "
                f"of {new_average_price_sl_percentage}% calculated "
                f"based on average price {sl_data[0]} and "
                f"SL price {sl_data[1]}."
            )

            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} profit increased "
                f"from {last_profit_percentage}% to {current_profit_percentage}%. "
                f"StopLoss increased from {deal_db_data['last_readable_sl_percentage']}% to "
                f"{new_average_price_sl_percentage}%. ",
                True
            )

            # Calculate new TP percentage based on the increased profit and increment factor
            current_tp_percentage = float(deal_data["take_profit"])
            new_tp_percentage = round(
                current_tp_percentage + (
                        (current_profit_percentage - last_profit_percentage)
                        * tp_increment_factor
                    ), 2
            )

            if new_tp_percentage > current_tp_percentage:
                logger.info(
                    f"TakeProfit increased from {current_tp_percentage}% "
                    f"to {new_tp_percentage}%.",
                    True
                )

            # Check whether there is an old timeout, and log when the new time out is different
            current_sl_timeout = deal_data["stop_loss_timeout_in_seconds"]
            if current_sl_timeout is not None and current_sl_timeout != new_sl_timeout:
                logger.info(
                    f"StopLoss timeout changed from {current_sl_timeout}s "
                    f"to {new_sl_timeout}s.",
                    True
                )

            # Update deal in 3C
            if update_deal_profit(
                bot_data, deal_data, sl_data[2], new_tp_percentage, new_sl_timeout
            ):
                # Update deal in our database
                update_profit_in_db(
                    deal_data['id'], current_profit_percentage,
                    new_average_price_sl_percentage, new_tp_percentage
                )
        else:
            logger.debug(
                f"{deal_data['pair']}/{deal_data['id']}: calculated SL of {sl_data[2]}% which "
                f"is equal to current SL {current_sl_percentage}% or "
                f"is 0.0 which causes 3C to deactive SL; no change made!"
            )

        # SL calculated, so deal must be monitored for any changes (even if an
        # invalid SL has been calculated)
        requiremonitoring = 1
    else:
        # Profit has not increased, but SL active so check frequently
        requiremonitoring = 1

        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: no profit increase "
            f"(current: {current_profit_percentage}%, "
            f"previous: {last_profit_percentage}%). Keep on monitoring."
        )

    return requiremonitoring


def remove_closed_deals(bot_id, current_deals):
    """Remove all deals for the given bot, except the ones in the list."""

    if current_deals:
        # Remove start and end square bracket so we can properly use it
        current_deals_str = str(current_deals)[1:-1]

        logger.debug(f"Deleting old deals from bot {bot_id} except {current_deals_str}")
        db.execute(
            f"DELETE FROM deal_profit WHERE botid = {bot_id} "
            f"AND dealid NOT IN ({current_deals_str})"
        )
        db.execute(
            f"DELETE FROM deal_safety WHERE botid = {bot_id} "
            f"AND dealid NOT IN ({current_deals_str})"
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
        f"last_profit_percentage, "
        f"add_funds_percentage, "
        f"next_so_percentage, "
        f"filled_so_count, "
        f"active_order_id "
        f") VALUES ("
        f"{deal_id}, {bot_id}, {0.0}, {0.0}, {0.0}, {0}, {0}"
        f")"
    )

    logger.debug(
        f"Added deal {deal_id} on bot {bot_id} as new deal to db."
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


def update_safetyorder_in_db(deal_id, filled_so_count, next_so_percentage):
    """Update deal safety related fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"next_so_percentage = {next_so_percentage}, "
        f"filled_so_count = {filled_so_count} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()


def update_safetyorder_monitor_in_db(deal_id, last_profit_percentage, add_funds_percentage):
    """Update deal safety monitor fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"last_profit_percentage = {last_profit_percentage}, "
        f"add_funds_percentage = {add_funds_percentage} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()


def update_safetyorder_active_order_in_db(deal_id, active_order_id):
    """Update deal safety monitor fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"active_order_id = {active_order_id} "
        f"WHERE dealid = {deal_id}"
    )

    db.commit()


##################################################################################################
def handle_deal_safety(bot_data, deal_data, deal_db_data, safety_config, current_profit_percentage):
    """Handle the Safety Orders for this deal."""

    requiremonitoring = 0

    # Debug data, remove later...
    logger.debug(
        f"Processing deal {deal_data['id']} with current "
        f"profit {float(deal_data['actual_profit_percentage'])}%. "
        f"Total profit is {current_profit_percentage}%. "
        f"Max SO: {deal_data['max_safety_orders']}, "
        f"Active: {deal_data['active_safety_orders_count']}, "
        f"Current active: {deal_data['current_active_safety_orders_count']}, "
        f"Completed: {deal_data['completed_safety_orders_count']}. "
        f"Manual SO active: {deal_data['active_manual_safety_orders']}, "
        f"Completed manual SO: {deal_data['completed_manual_safety_orders_count']}. "
        f"Stored bought SO: {deal_db_data['filled_so_count']}"
    )

    # Return if deal has used all the Safety Orders. Nothing to do anymore.
    if deal_db_data['filled_so_count'] == deal_data['max_safety_orders']:
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']} has filled "
            f"all {deal_data['max_safety_orders']} Safety Orders."
        )
        return requiremonitoring

    if deal_data['active_manual_safety_orders'] == 1:
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']} has pending Safety Order. "
            f"Wait for it to fill, before next Safety Order can be filled."
        )
        return requiremonitoring

    # Notify when pending safety order has been filled
    if deal_data['active_manual_safety_orders'] == 0 and deal_db_data["active_order_id"] > 0:
        logger.info(
            f"{deal_data['pair']}/{deal_data['id']}: "
            f"order {deal_db_data['active_order_id']} has been filled!",
            True
        )
        update_safetyorder_active_order_in_db(deal_data["id"], 0)

    profitprefix = ""
    if deal_data["strategy"]  == "short":
        profitprefix = "-"

    logger.info(
        f"{deal_data['pair']}/{deal_data['id']} current profit: {profitprefix}{current_profit_percentage}, "
        f"next SO at {profitprefix}{deal_db_data['next_so_percentage']}"
    )

    addfundspercentage = deal_db_data["add_funds_percentage"]
    last_profit_percentage = float(deal_db_data["last_profit_percentage"])
    if safety_config and current_profit_percentage > last_profit_percentage:
        if last_profit_percentage == 0.0:
            # First time activation, calculate initial buy percentage
            activation_diff = current_profit_percentage - deal_db_data["next_so_percentage"]
            addfundspercentage = (
                deal_db_data["next_so_percentage"] +
                float(safety_config.get("initial-buy-percentage")) +
                (activation_diff * float(safety_config.get("buy-increment-factor")))
            )

            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
                f"profit {profitprefix}{current_profit_percentage:0.2f}% dropped below "
                f"Safety Order at {profitprefix}{deal_db_data['next_so_percentage']:0.2f}%. "
                f"Next Safety Order set to {profitprefix}{addfundspercentage:0.2f}%.",
                True
            )
        else:
            # Shift buy percentage based on profit change
            profit_diff = current_profit_percentage - last_profit_percentage
            addfundspercentage = addfundspercentage + (
                profit_diff * float(safety_config.get("buy-increment-factor"))
            )

            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} profit changed "
                f"from {profitprefix}{last_profit_percentage:0.2f}% to {profitprefix}{current_profit_percentage:0.2f}%. "
                f"Add Funds changed from {profitprefix}{deal_db_data['add_funds_percentage']:0.2f}% to "
                f"{profitprefix}{addfundspercentage:0.2f}%.",
                True
            )

        # Update data in database
        update_safetyorder_monitor_in_db(deal_data["id"], current_profit_percentage, addfundspercentage)

        # Buy percentage has changed, monitor profit for changes
        requiremonitoring = 1
    elif current_profit_percentage <= addfundspercentage:
        # Current profit passed or equal to buy percentage. Add funds to the deal
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']} profit {profitprefix}{current_profit_percentage:0.2f}% "
            f"passed Add Funds of {profitprefix}{addfundspercentage}%."
        )

        # When current profit is below the desired Safety Order, reset and start from the beginning
        if current_profit_percentage < float(deal_db_data["next_so_percentage"]):
            update_safetyorder_monitor_in_db(
                deal_data["id"], 0.0, deal_db_data["next_so_percentage"]
            )

            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
                f"profit {profitprefix}{current_profit_percentage:0.2f}% above Safety Order "
                f"of {profitprefix}{deal_db_data['next_so_percentage']:0.2f}%. Missed Add Funds "
                f"oppertunity; reset so trailing can start over again.",
                True
            )
        else:
            # SO data contains five values:
            # 0. The number of configured Safety Orders to be filled using a Manual trade
            # 1. The total volume for those number of Safety Orders
            # 2. The buy price of that volume
            # 3. The total negative profit percentage for the current Safety Order
            # 4. The total negative profit percentage on which the next Safety Order is configured
            sodata = calculate_safety_order(
                logger, bot_data, deal_data,
                deal_db_data["filled_so_count"], current_profit_percentage
            )

            limitprice = sodata[2]
            if limitprice > float(deal_data["current_price"]):
                logger.debug(
                    f"{deal_data['pair']}/{deal_data['id']} current price "
                    f"{deal_data['current_price']} lower than calculated "
                    f"price {limitprice}, so using the current price."
                )
                limitprice = float(deal_data["current_price"])

            quantity = sodata[1] / limitprice
            logger.debug(
                f"{deal_data['pair']}/{deal_data['id']} calculated quantity {quantity} "
                f"based on volume {sodata[1]} and price {limitprice}."
            )

            # Required for later, in order to use tick size ed
            #get_data_for_add_funds(deal)

            if threecommas_deal_add_funds(
                logger, api, deal_data["pair"], deal_data["id"], quantity, limitprice
            ):
                activeorderid = get_threecommas_deal_active_manual_safety_order(
                    logger, api, deal_data["pair"], deal_data["id"]
                )
                totalfilledso = deal_db_data["filled_so_count"] + sodata[0]

                if activeorderid > 0:
                    update_safetyorder_active_order_in_db(deal_data["id"], activeorderid)

                    logger.info(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} profit "
                        f"{profitprefix}{current_profit_percentage:0.2f}% passed Add Funds moment "
                        f"at {profitprefix}{addfundspercentage:0.2f}%. "
                        f"Created order {activeorderid} for {quantity} of "
                        f"{deal_data['pair'].split('_')[1]}. In total {totalfilledso} out of "
                        f"{deal_data['max_safety_orders']} Safety Order(s) are filled.",
                        True
                    )
                else:
                    logger.info(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} profit "
                        f"{profitprefix}{current_profit_percentage:0.2f}% passed Add Funds moment "
                        f"at {profitprefix}{addfundspercentage:0.2f}%. "
                        f"Filled {sodata[0]} Safety Order(s) for {quantity} of "
                        f"{deal_data['pair'].split('_')[1]}. In total {totalfilledso} out of "
                        f"{deal_data['max_safety_orders']} Safety Order(s) are filled.",
                        True
                    )

                # Save total filled and next SO to database
                update_safetyorder_in_db(deal_data["id"], totalfilledso, sodata[4])

                # Set up trailing for next SO
                update_safetyorder_monitor_in_db(deal_data["id"], 0.0, sodata[4])
            else:
                logger.error(
                    f"{deal_data['pair']}/{deal_data['id']} failed to Add Funds!"
                )
    else:
        # Buy percentage has not changed, but monitor frequently for changes
        requiremonitoring = 1

        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: no profit decrease "
            f"(current: {profitprefix}{current_profit_percentage}%, "
            f"previous: {profitprefix}{last_profit_percentage}%, "
            f"Add Funds: {profitprefix}{addfundspercentage}%). "
            f"Keep on monitoring."
        )

    return requiremonitoring


def set_first_safety_order(bot_data, deal_data, filled_so_count, current_profit_percentage):
    """Calculate and set the first safety order"""

    # Next SO percentage is unknown / not set. This will, logically, only be the case
    # for newly started deals. So, let's calculate...

    # SO data contains five values:
    # 0. The number of configured Safety Orders to be filled using a Manual trade
    # 1. The total volume for those number of Safety Orders
    # 2. The buy price of that volume
    # 3. The total negative profit percentage for the current Safety Order
    # 4. The next total negative profit percentage on which the next Safety Order is configured
    sodata = calculate_safety_order(
        logger, bot_data, deal_data, filled_so_count, current_profit_percentage
    )

    # Update data in database
    update_safetyorder_in_db(deal_data["id"], filled_so_count, sodata[4])

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: new deal and set first SO to {sodata[4]}%",
        True # Remove later
    )

###############################################################################################

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
            "last_profit_percentage FLOAT, "
            "add_funds_percentage FLOAT, "
            "next_so_percentage FLOAT, "
            "filled_so_count INT, "
            "active_order_id INT "
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
            "last_profit_percentage FLOAT, "
            "add_funds_percentage FLOAT, "
            "next_so_percentage FLOAT, "
            "filled_so_count INT, "
            "active_order_id INT "
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
