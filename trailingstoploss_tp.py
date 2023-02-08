#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import decimal
import json
from math import fabs
import os
import sqlite3
import sys
import time
import traceback
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.database import (
    get_next_process_time,
    set_next_process_time
)
from helpers.misc import (
    get_round_digits,
    round_decimals_up,
    unix_timestamp_to_string,
    wait_time_interval
)
from helpers.threecommas import (
    get_threecommas_deal_order_id,
    get_threecommas_deal_order_status,
    init_threecommas_api,
    threecommas_deal_add_funds,
    threecommas_deal_cancel_order,
    threecommas_get_data_for_adding_funds
)
from helpers.trailingstoploss_tp import (
    calculate_safety_order,
    calculate_sl_percentage,
    calculate_tp_percentage,
    check_float,
    get_pending_order_db_data,
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
        "notify-trailing-update": True,
        "notify-trailing-reset": True,
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
        "safety-config": json.dumps(cfgsectionsafetyconfig),
        "safety-mode": "merge / shift"
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
                    "activation-percentage": "0.25",
                    "activation-so-count": "0",
                    "initial-buy-percentage": "0.0",
                    "buy-increment-factor": "0.50",
                })

                cfg.set(cfgsection, "safety-config", json.dumps(cfgsectionsafetyconfig))

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info(
                    "Upgraded section %s to have profit- and safety- config list" % cfgsection
                    )
            else:
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

            if not cfg.has_option(cfgsection, "safety-mode"):
                cfg.set(cfgsection, "safety-mode", "merge")

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info("Updates section %s to add safety-mode" % cfgsection)

    if not cfg.has_option("settings", "notify-trailing-update"):
        cfg.set("settings", "notify-trailing-update", "True")
        cfg.set("settings", "notify-trailing-reset", "True")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        thelogger.info("Updates settings to add notify options")

    return cfg


def update_deal_profit(bot_data, deal_data, new_stoploss, new_take_profit, sl_timeout):
    """Update bot with new SL and TP."""

    dealupdated = False

    payload = {
        "deal_id": bot_data["id"],
        "stop_loss_percentage": new_stoploss,
        "stop_loss_timeout_enabled": sl_timeout > 0,
        "stop_loss_timeout_in_seconds": sl_timeout
    }

    # Only update TP values when no conditional take profit is used
    # Note: currently the API does not support this. Script cannot be used for MP deals yet!
    #if not len(thebot['close_strategy_list']):
    #if deal_data["status"].lower() not in("close_strategy_activated"):
    #    payload["take_profit"] = new_take_profit
    #    payload["trailing_enabled"] = False
    #else:
    #    payload["take_profit"] = 0.05
    #    payload["trailing_enabled"] = False
    if len(deal_data["close_strategy_list"]) == 0:
        payload["take_profit"] = new_take_profit

    payload["trailing_enabled"] = deal_data["trailing_enabled"]
    payload["tsl_enabled"] = deal_data["tsl_enabled"]

    logger.debug(
        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
        f"Request update_deal with payload: {payload}."
    )

    error, data = api.request(
        entity="deals",
        action="update_deal",
        action_id=str(deal_data["id"]),
        payload=payload
    )

    if data:
        if (float(data["stop_loss_percentage"]) != new_stoploss or
            float(data["take_profit"]) != new_take_profit or
            int(data["stop_loss_timeout_in_seconds"]) != sl_timeout
        ):
            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"update of deal failed. Received data: {data}."
            )
        else:
            dealupdated = True
            logger.debug(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"changed SL from {deal_data['stop_loss_percentage']}% "
                f"to {data['stop_loss_percentage']}%. "
                f"Changed TP from {deal_data['take_profit']}% "
                f"to {data['take_profit']}%. "
                f"Changed SL timeout from {deal_data['stop_loss_timeout_in_seconds']}s "
                f"to {data['stop_loss_timeout_in_seconds']}s."
            )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred updating deal with new SL/TP values: %s" % error["msg"]
            )
        else:
            logger.error("Error occurred updating deal with new SL/TP valuess")

    return dealupdated


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

    return settings


def process_deals(bot_data, section_profit_config, section_safety_config, section_safety_mode):
    """Check deals from bot, compare against the database and handle them."""

    monitoreddeals = 0

    botid = bot_data["id"]
    deals = bot_data["active_deals"]

    if deals:
        currentdeals = []

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

                # Only process deals with bought status. Created or base order placed
                # means not all data is available for further calculations. Failed,
                # cancelled, completed and panic_sell_pending are states in which we
                # don't need to do anything or should not interfere with.
                #if deal["status"].lower() not in("bought", "close_strategy_activated"):
                if deal["status"].lower() not in("bought", "close_strategy_activated"):
                    logger.info(
                        f"\"{bot_data['name']}\": {deal['pair']}/{deal['id']} has status "
                        f"'{deal['status']}' which is not valid for further processing!"
                    )
                    continue

                currentdeals.append(deal["id"])

                if is_new_deal(cursor, deal["id"]):
                    add_deal_in_db(deal["id"], botid)

                    # Only deals without 3C Safety Orders active can be processed by this script
                    if deal['active_safety_orders_count'] == 0 and len(section_safety_config) > 0:
                        set_first_safety_order(bot_data, deal, 0, 0.0)

                if float(deal["actual_profit_percentage"]) > 0.0:
                    monitoreddeals += process_deal_for_profit(
                        section_profit_config, bot_data, deal
                    )
                elif float(deal["actual_profit_percentage"]) < 0.0:
                    monitoreddeals += process_deal_for_safety_order(
                        section_safety_config, section_safety_mode, bot_data, deal
                    )
            else:
                logger.warning(
                    f"\"{bot_data['name']}\": {deal['pair']}/{deal['id']}: "
                    f"Unknown strategy {deal['strategy']}!"
                )

        # Housekeeping, clean things up and prevent endless growing database
        remove_closed_deals(botid, currentdeals)

        logger.debug(
            f"Bot \"{bot_data['name']}\" ({botid}) has {len(deals)} deal(s) "
            f"of which {monitoreddeals} require monitoring."
        )
    else:
        logger.debug(
            f"Bot \"{bot_data['name']}\" ({botid}) has no active deals."
        )
        remove_all_deals(botid)

    return monitoreddeals


def process_deal_for_profit(section_profit_config, bot_data, deal_data):
    """Process a deal which has positive profit"""

    if len(section_profit_config) == 0:
        return 0 #Deal does not require monitoring

    # Close strategy is based on conditions, which means minimal take profit
    # is used and not the regular take profit
    if len(deal_data["close_strategy_list"]) == 0:
        if float(deal_data["actual_profit_percentage"]) > float(deal_data["take_profit"]):
            logger.info(
                f"Deal data: {deal_data}. "
            )
            logger.debug(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"current profit {deal_data['actual_profit_percentage']} above take profit of "
                f"{deal_data['take_profit']}, so there is no point in updating "
                f"TP and/or SL value. Deal should be closed by 3Commas any moment now."
            )
            return 0 #Deal does not require monitoring

    requiremonitoring = 0

    # Deal is in positive profit, so TSL mode which requires the profit-config
    dealdbdata = get_profit_db_data(cursor, deal_data["id"])

    profitconfig = get_settings(
        section_profit_config,
        float(deal_data["actual_profit_percentage"]),
        int(deal_data["completed_safety_orders_count"])
    )

    # Available profit_config means trailing must be applied. So for deals
    # which have not reached the desired profit yet,
    # no profit_config can be found.
    if profitconfig:
        requiremonitoring = handle_deal_profit(
                bot_data, deal_data, dealdbdata, profitconfig
            )
    else:
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"no profit config available for profit {deal_data['actual_profit_percentage']}% "
            f"and {deal_data['completed_safety_orders_count']} filled SO."
        )

        # Reset trailing data if trailing was activated before (profit has dropped)
        if float(dealdbdata["last_profit_percentage"]) > float(bot_data["take_profit"]):
            if update_deal_profit(bot_data, deal_data, 0.0, float(bot_data["take_profit"]), 0):
                update_profit_in_db(
                    deal_data['id'], 0.0, 0.0, 0.0
                )
                logger.info(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"profit has decreased below configured profit-config. Trailing "
                    f"has been reset and TP restored to {bot_data['take_profit']}%.",
                    notifytrailingreset
                )

    return requiremonitoring


def process_deal_for_safety_order(section_safety_config, section_safety_mode, bot_data, deal_data):
    """Process a deal which has negative profit"""

    if len(section_safety_config) == 0:
        return 0 #Deal does not require monitoring

    if deal_data['active_safety_orders_count'] != 0:
        logger.warning(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
            f"has active Safety Orders by bot configuration which will break the "
            f"functionality of this script. Not processing this deal!"
        )
        return 0 #Deal does not require monitoring

    # SO mode requires the total % drop without filled safety oders
    totalprofit = round(fabs(
        ((float(deal_data["current_price"]) /
        float(deal_data["base_order_average_price"])) * 100.0) - 100.0
    ), 2)

    # Fetch data from local DB for this deal
    dealdbdata = get_safety_db_data(cursor, deal_data["id"])
    orderdbdata = get_pending_order_db_data(cursor, deal_data["id"])

    openorderfilled = False
    if orderdbdata is not None and orderdbdata["order_id"]:
        if deal_data['active_manual_safety_orders'] > 0:
            if totalprofit >= orderdbdata["cancel_at_percentage"]:
                logger.debug(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
                    f"has pending Safety Order. "
                    f"Current profit {totalprofit}% has not reached cancel at "
                    f"{orderdbdata['cancel_at_percentage']}%. "
                    f"Wait for it to fill, before handling next Safety Order."
                )
                return 1 #Deal requires monitoring

            # Profit has passed the SO boundary, time to cancel the pending order
            # and start over with trailing
            if threecommas_deal_cancel_order(logger, api, deal_data["id"], orderdbdata["order_id"]):
                logger.info(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"order {orderdbdata['order_id']} cancelled because profit  "
                    f"{totalprofit}% exceeded {orderdbdata['cancel_at_percentage']}%",
                    True
                )

                # Reset trailing
                update_safetyorder_monitor_in_db(
                    deal_data["id"], 0.0, orderdbdata["next_so_percentage"]
                )

                # Remove pending order
                remove_pending_order_from_db(deal_data["id"], orderdbdata["order_id"])

                # Refresh the data as it has been changed
                dealdbdata = get_safety_db_data(cursor, deal_data["id"])
            else:
                orderstatus = get_threecommas_deal_order_status(logger, api, deal_data["pair"], deal_data["id"], orderdbdata["order_id"])

                if orderstatus.lower() == "filled":
                    # Order is filled, however deal data not yet updated at 3C?
                    openorderfilled = True
                else:
                    logger.warning(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"cancellation of order {orderdbdata['order_id']} failed. "
                        f"Current state is {orderstatus}. Will be retried next interval..."
                    )

                    return 1 #Deal requires monitoring
        else:
            # No active order anymore, so it has been filled
            openorderfilled = True

    if openorderfilled:
        totalfilledso = dealdbdata["filled_so_count"] + orderdbdata["number_of_so"]
        logger.info(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"order {orderdbdata['order_id']} has been filled. "
            f"{totalfilledso}/{deal_data['max_safety_orders']} Safety Order(s) are filled.",
            True
        )

        # Save total filled and next SO to database
        update_safetyorder_in_db(
            deal_data["id"], totalfilledso, orderdbdata["next_so_percentage"], orderdbdata["shift_percentage"]
        )

        # Set up trailing for next SO
        update_safetyorder_monitor_in_db(
            deal_data["id"], 0.0, orderdbdata["next_so_percentage"]
        )

        # Remove pending order as it has been filled
        remove_pending_order_from_db(deal_data["id"], orderdbdata["order_id"])

        # Refresh the data as it has been changed
        dealdbdata = get_safety_db_data(cursor, deal_data["id"])

    if dealdbdata['filled_so_count'] == deal_data['max_safety_orders']:
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
            f"has filled all {deal_data['max_safety_orders']} Safety Orders."
        )
        return 0 #Deal does not require monitoring

    # Return value for this function
    requiremonitoring = 0

    # We use the relative profit to the next SO for determining if further processing is required
    sorelativeprofit = round(totalprofit - dealdbdata["next_so_percentage"], 2)
    if sorelativeprofit >= 0.0:
        safetyconfig = get_settings(
                section_safety_config, sorelativeprofit, dealdbdata["filled_so_count"]
            )

        if safetyconfig:
            requiremonitoring = handle_deal_safety(
                        bot_data, deal_data, dealdbdata, safetyconfig, totalprofit, section_safety_mode
                    )
        else:
            logger.debug(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"no safety config available for profit -{sorelativeprofit}% "
                f"and {dealdbdata['filled_so_count']} filled SO."
            )

            if (dealdbdata["last_profit_percentage"] != 0.0 or
                dealdbdata["add_funds_percentage"] != dealdbdata["next_so_percentage"]
            ):
                logger.info(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"trailing reset because current profit suddenly changed above "
                    f"the first configured safety config.",
                    notifytrailingreset
                )
                update_safetyorder_monitor_in_db(
                    deal_data["id"], 0.0, dealdbdata['next_so_percentage']
                )
    else:
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
            f"requires {fabs(sorelativeprofit)}% change before next SO "
            f"at {dealdbdata['next_so_percentage']:0.2f}% will be reached."
        )

        if (dealdbdata["last_profit_percentage"] != 0.0 or
            dealdbdata["add_funds_percentage"] != dealdbdata["next_so_percentage"]
        ):
            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"trailing reset because profit suddenly changed and went above "
                f"the SO at {dealdbdata['next_so_percentage']:0.2f}%.",
                notifytrailingreset
            )
            update_safetyorder_monitor_in_db(deal_data["id"], 0.0, dealdbdata['next_so_percentage'])

    return requiremonitoring


def handle_deal_profit(bot_data, deal_data, deal_db_data, profit_config):
    """Update deal (short or long) and increase SL (Trailing SL) when profit has increased."""

    requiremonitoring = 0

    currentprofitpercentage = float(deal_data["actual_profit_percentage"])
    lastprofitpercentage = float(deal_db_data["last_profit_percentage"])
    if currentprofitpercentage > lastprofitpercentage:
        message = (
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
            f"profit increased from {lastprofitpercentage}% to {currentprofitpercentage}%. "
        )

        activationdiff = (
            currentprofitpercentage - float(profit_config.get("activation-percentage"))
        )

        # SL data contains three values:
        # 0. The current SL percentage on 3C axis (inverted range compared to TP axis)
        # 1. The SL percentage on 3C axis (inverted range compared to TP axis)
        # 2. The SL percentage on TP axis (understandable for the user)
        sldata = calculate_sl_percentage(logger, deal_data, profit_config, activationdiff)

        # TP data contains two values:
        # 0. The current TP value
        # 1. The new TP value
        tpdata = calculate_tp_percentage(
            logger, deal_data, profit_config, activationdiff, lastprofitpercentage
        )

        sendnotification = notifytrailingupdate

        newsltimeout = int(profit_config.get("sl-timeout"))
        if (fabs(sldata[1]) > 0.0 and sldata[1] != sldata[0]):
            if deal_db_data['last_readable_sl_percentage'] != sldata[2]:
                message += (
                    f"StopLoss increased from {deal_db_data['last_readable_sl_percentage']}% "
                    f"to {sldata[2]}%. "
                )

            # Check whether there is an old timeout, and log when the new time out is different
            currentsltimeout = deal_data["stop_loss_timeout_in_seconds"]
            if currentsltimeout is not None and currentsltimeout != newsltimeout:
                message += (
                    f"StopLoss timeout changed from {currentsltimeout}s "
                    f"to {newsltimeout}s. "
                )

        if tpdata[1] > tpdata[0]:
            sendnotification = (lastprofitpercentage == 0.0) or notifytrailingupdate
            message += (
                f"TakeProfit increased from {tpdata[0]}% "
                f"to {tpdata[1]}%. "
            )

        # Update deal in 3C
        if update_deal_profit(
            bot_data, deal_data, sldata[1], tpdata[1], newsltimeout
        ):
            # Update deal in our database
            update_profit_in_db(
                deal_data['id'], currentprofitpercentage,
                sldata[2], tpdata[1]
            )

            # Send the message to the user
            logger.info(message, sendnotification)
        else:
            logger.error(
                f"Update failed for message: {message}"
            )

        # SL and/or TP calculated, so deal must be monitored for any changes
        requiremonitoring = 1
    else:
        # Profit has not increased, but SL and/or TP active so check frequently
        requiremonitoring = 1

        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"no profit increase (current: {currentprofitpercentage}%, "
            f"previous: {lastprofitpercentage}%). Keep on monitoring."
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
        db.execute(
            f"DELETE FROM pending_orders WHERE botid = {bot_id} "
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
    db.execute(
        f"DELETE FROM pending_orders WHERE botid = {bot_id}"
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
        f"shift_percentage "
        f") VALUES ("
        f"{deal_id}, {bot_id}, {0.0}, {0.0}, {0.0}, {0}, {0.0}"
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


def update_safetyorder_in_db(deal_id, filled_so_count, next_so_percentage, shift_percentage):
    """Update deal safety related fields (short or long) in database."""

    db.execute(
        f"UPDATE deal_safety SET "
        f"next_so_percentage = {next_so_percentage}, "
        f"filled_so_count = {filled_so_count}, "
        f"shift_percentage = {shift_percentage} "
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


def add_pending_order_in_db(deal_id, bot_id, active_order_id, cancel_at_percentage, number_of_so, next_so_percentage, shift_percentage):
    """Add deal safety order (short or long) in database."""

    db.execute(
        f"INSERT INTO pending_orders ("
        f"dealid, "
        f"botid, "
        f"order_id, "
        f"cancel_at_percentage, "
        f"number_of_so, "
        f"next_so_percentage, "
        f"shift_percentage "
        f") VALUES ("
        f"{deal_id}, {bot_id}, '{active_order_id}', {cancel_at_percentage}, {number_of_so}, {next_so_percentage}, {shift_percentage}"
        f")"
    )

    db.commit()


def update_pending_order_in_db(deal_id, old_order_id, new_order_id):
    """Update the id of the current open active order"""

    db.execute(
        f"UPDATE pending_orders SET "
        f"order_id = '{new_order_id}' "
        f"WHERE dealid = {deal_id} "
        f"AND order_id = '{old_order_id}'"
    )

    db.commit()


def remove_pending_order_from_db(deal_id, order_id):
    """Remove deal safety order (short or long) from database."""

    db.execute(
        f"DELETE FROM pending_orders WHERE dealid = {deal_id} "
        f"AND order_id = '{order_id}'"
    )

    db.commit()


def handle_deal_safety(bot_data, deal_data, deal_db_data, safety_config, current_profit_percentage, safety_mode):
    """Handle the Safety Orders for this deal."""

    requiremonitoring = 0

    profitprefix = ""
    if deal_data["strategy"] == "long":
        profitprefix = "-"

    currentaddfundspercentage = deal_db_data["add_funds_percentage"]
    lastprofitpercentage = deal_db_data["last_profit_percentage"]
    if current_profit_percentage > lastprofitpercentage:
        initialbuy = float(safety_config.get("initial-buy-percentage"))

        newaddfundspercentage = deal_db_data["next_so_percentage"] + initialbuy
        newaddfundspercentage += round(
            (current_profit_percentage - newaddfundspercentage) *
            float(safety_config.get("buy-increment-factor")),
            2
        )

        if fabs(newaddfundspercentage) > fabs(currentaddfundspercentage):
            sendnotification = (lastprofitpercentage == 0.0) or notifytrailingupdate

            # Update data in database
            update_safetyorder_monitor_in_db(
                deal_data["id"], current_profit_percentage, newaddfundspercentage
            )

            # Send message to user
            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"profit from {profitprefix}{lastprofitpercentage:0.2f}% to "
                f"{profitprefix}{current_profit_percentage:0.2f}% (trailing "
                f"from {profitprefix}{deal_db_data['next_so_percentage']:0.2f}%). "
                f"Add Funds threshold from "
                f"{profitprefix}{currentaddfundspercentage:0.2f}% "
                f"to {profitprefix}{newaddfundspercentage:0.2f}%.",
                sendnotification
            )

        # Profit percentage has changed, monitor profit for changes
        requiremonitoring = 1
    elif current_profit_percentage <= currentaddfundspercentage:
        # Current profit passed or equal to buy percentage. Add funds to the deal
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"profit {profitprefix}{current_profit_percentage:0.2f}% "
            f"passed Add Funds threshold of {profitprefix}{currentaddfundspercentage}%."
        )

        # When current profit is below the desired Safety Order, reset and start from the beginning
        if current_profit_percentage < deal_db_data["next_so_percentage"]:
            update_safetyorder_monitor_in_db(
                deal_data["id"], 0.0, deal_db_data["next_so_percentage"]
            )

            logger.info(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"profit {profitprefix}{current_profit_percentage:0.2f}% above Safety Order "
                f"of {profitprefix}{deal_db_data['next_so_percentage']:0.2f}%. Missed Add Funds "
                f"oppertunity; reset so trailing can start over again.",
                notifytrailingreset
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

            logger.debug(
                f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                f"complete deal data is {deal_data}."
            )

            quantity = sodata[1]
            limitprice = sodata[2]
            if deal_data["strategy"] == "long" and limitprice > float(deal_data["current_price"]):
                logger.debug(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"current price {deal_data['current_price']} lower than "
                    f"calculated price {limitprice}, so using the current price."
                )
                limitprice = float(deal_data["current_price"])
            elif deal_data["strategy"] == "short" and limitprice < float(deal_data["current_price"]):
                logger.debug(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"current price {deal_data['current_price']} higher than "
                    f"calculated price {limitprice}, so using the current price."
                )
                limitprice = float(deal_data["current_price"])

            if deal_data["safety_order_volume_type"] == "quote_currency":
                quantity = quantity / limitprice
                logger.debug(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"calculated quantity {quantity} based on "
                    f"volume {sodata[1]} and price {limitprice}."
                )
            else:
                logger.info(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"using quantity {quantity} based on 'base_currency' volume "
                    f"order type."
                )

            # TODO: use the data to validate the request
            fundsdata = threecommas_get_data_for_adding_funds(logger, api, deal_data)
            if fundsdata:
                limitvalue = fundsdata["limits"]["lotStep"].split(".")
                #decimals = fundsdata["limits"]["lotStep"][::-1].find('.')
                decimals = 0
                if int(limitvalue[1]) > 0:
                    decimals = len(limitvalue[1])
                quantity = round_decimals_up(quantity, decimals)

                logger.debug(
                    f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                    f"changed quantity to {quantity} based on "
                    f"lotStep {fundsdata['limits']['lotStep']} and value {limitvalue}."
                )

                #TODO: below is only debugging. Incorperate when it's clear how this works
                if ("marketBuyMinTotal" in fundsdata["limits"] and
                    sodata[1] <= float(fundsdata["limits"]["marketBuyMinTotal"]) > sodata[1]
                ):
                    logger.error(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"buy amount of {sodata[1]} lower than "
                        f"{fundsdata['limits']['marketBuyMinTotal']}!"
                    )

                if ("maxMarketBuyAmount" in fundsdata["limits"] and
                    sodata[1] >= float(fundsdata["limits"]["maxMarketBuyAmount"])
                ):
                    logger.error(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"buy amount of {sodata[1]} higher than "
                        f"{fundsdata['limits']['maxMarketBuyAmount']}!"
                    )

                # Modulo executed with Decimal and string to prevent rounding and
                # floating point issues.
                sizemodulo = decimal.Decimal(str(quantity - float(fundsdata["limits"]["minLotSize"]))) % decimal.Decimal(fundsdata["limits"]["lotStep"])
                if sizemodulo != 0.0:
                    logger.error(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"quantity {quantity} not a multiply of stepsize "
                        f"{fundsdata['limits']['lotStep']}, taking min size of "
                        f"{fundsdata['limits']['minLotSize']} into account! Remaining "
                        f"is {sizemodulo}"
                    )


            if threecommas_deal_add_funds(
                logger, api, deal_data["pair"], deal_data["id"], quantity, limitprice
            ):
                orderid = get_threecommas_deal_order_id(
                    logger, api, deal_data["pair"], deal_data["id"], "Manual Safety", "Active"
                )

                rounddigits = get_round_digits(deal_data["pair"])

                nextsopercentage = sodata[4]
                shiftpercentage = deal_db_data["shift_percentage"]

                #if safety_mode.lower() == "shift":
                #    previoussopercentage = sodata[3]
                #    diffsopercentage = fabs(nextsopercentage - previoussopercentage)

                #    nextsopercentage = current_profit_percentage + diffsopercentage
                #    shiftpercentage += diffsopercentage

                #    logger.debug(
                #        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                #        f"shifting SO by {diffsopercentage}% based on prev SO "
                #        f"{previoussopercentage}% and next SO {sodata[4]}%. "
                #        f"New next SO on {nextsopercentage}%."
                #        f"Total shift is now {shiftpercentage}%.",
                #        True
                #    )

                if orderid:
                    logger.info(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"profit {profitprefix}{current_profit_percentage:0.2f}% passed Add Funds "
                        f"threshold at {profitprefix}{currentaddfundspercentage:0.2f}%. "
                        f"Created order '{orderid}' for {quantity:0.{rounddigits}f} "
                        f"{deal_data['pair'].split('_')[1]}. ",
                        True
                    )

                    add_pending_order_in_db(
                        deal_data["id"], bot_data["id"], orderid, sodata[3], sodata[0], nextsopercentage, shiftpercentage
                    )
                else:
                    totalfilledso = deal_db_data["filled_so_count"] + sodata[0]

                    logger.info(
                        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
                        f"profit {profitprefix}{current_profit_percentage:0.2f}% passed Add Funds "
                        f"threshold at {profitprefix}{currentaddfundspercentage:0.2f}%. "
                        f"Filled {sodata[0]} Safety Order(s) for {quantity:0.{rounddigits}f} "
                        f"{deal_data['pair'].split('_')[1]}. "
                        f"{totalfilledso}/{deal_data['max_safety_orders']} Safety Order(s) are filled.",
                        True
                    )

                    # Save total filled and next SO to database
                    update_safetyorder_in_db(
                        deal_data["id"], totalfilledso, nextsopercentage, shiftpercentage
                    )

                    # Set up trailing for next SO
                    update_safetyorder_monitor_in_db(deal_data["id"], 0.0, nextsopercentage)
            else:
                logger.error(
                    f"{deal_data['pair']}/{deal_data['id']} failed to Add Funds!"
                )
    else:
        # Buy percentage has not changed, but monitor frequently for changes
        requiremonitoring = 1

        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"no profit decrease "
            f"(current: {profitprefix}{current_profit_percentage}%, "
            f"previous: {profitprefix}{lastprofitpercentage}%, "
            f"Add Funds threshold: {profitprefix}{currentaddfundspercentage}%). "
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
    update_safetyorder_in_db(deal_data["id"], filled_so_count, sodata[4], 0.0)
    update_safetyorder_monitor_in_db(deal_data["id"], 0, sodata[4])

    logger.debug(
        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
        f"new deal with next SO on {sodata[4]}%"
    )


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
            "shift_percentage FLOAT "
            ")"
        )

        dbcursor.execute(
            "CREATE TABLE IF NOT EXISTS pending_orders ("
            "dealid INT Primary Key, "
            "botid INT, "
            "order_id TEXT, "
            "cancel_at_percentage FLOAT, "
            "number_of_so INT, "
            "next_so_percentage FLOAT, "
            "shift_percentage FLOAT "
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
            "shift_percentage FLOAT "
            ")"
        )

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS pending_orders ("
            "dealid INT Primary Key, "
            "botid INT, "
            "order_id TEXT, "
            "cancel_at_percentage FLOAT, "
            "number_of_so INT, "
            "next_so_percentage FLOAT, "
            "shift_percentage FLOAT "
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

    notifytrailingupdate = config.getboolean("settings", "notify-trailing-update")
    notifytrailingreset = config.getboolean("settings", "notify-trailing-reset")

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
            sectionsafetyconfig = json.loads(config.get(section, "safety-config"))
            sectionsafetymode = config.get(section, "safety-mode")
            #if sectionsafetymode.lower() not in ("merge", "shift"):
            if sectionsafetymode.lower() not in ("merge"):
                logger.warning(
                    f"Section {section} has an invalid \'safety-mode\'. Skipping this section!"
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
                        try:
                            bot_deals_to_monitor = process_deals(
                                botdata, sectionprofitconfig, sectionsafetyconfig, sectionsafetymode
                            )

                            # Determine new time to process this bot, based on the monitored deals
                            newtime = starttime + (
                                check_interval if bot_deals_to_monitor == 0 else monitor_interval
                            )
                            set_next_process_time(db, "bots", "botid", bot, newtime)

                            deals_to_monitor += bot_deals_to_monitor
                        except Exception as err:
                            logger.error(err)
                            logger.error(traceback.print_exc())
                            logger.error(traceback.print_tb(err.__traceback__))
                            sys.exit(0)
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
