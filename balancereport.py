#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    calculate_deal_funds,
    get_round_digits,
    wait_time_interval
)
from helpers.threecommas import (
    get_threecommas_account_balance,
    get_threecommas_account_balance_chart_data,
    get_threecommas_account_table_balance,
    get_threecommas_accounts,
    get_threecommas_bots,
    get_threecommas_deals,
    init_threecommas_api,
)


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
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def create_account_balance(account_id):
    """Create the account balance"""

    list_of_funds = {}

    balancetable = get_threecommas_account_table_balance(logger, api, account_id)
    for currency in balancetable:
        code = currency["currency_code"]

        if code not in ("BUSD", "EUR", "USD", "USDT", "BTC", "BNB", "ETH"):
            continue

        # Position is the total, including reserved but excluding active deals (for
        # which the currency has been exchanged and will come back after closing the deal)
        position = currency["position"]

        list_of_funds[code] = position

    return list_of_funds

def process_bot_deals(bot_id, strategy):
    """Process the deals of the bot"""

    currentdealfunds = 0.0
    dealsofunds = 0.0
    yesterdayprofit = 0.0

    activedeals = get_threecommas_deals(logger, api, bot_id, "active")
    if activedeals is None:
        logger.info(
            f"No deals active for bot {bot_id}"
        )
        return currentdealfunds

    for activedeal in activedeals:
        if strategy == "long":
            currentdealfunds += float(activedeal["bought_volume"])

            bovolume = float(activedeal["base_order_volume"])
            sovolume = float(activedeal["safety_order_volume"])
            completed_safety_orders = float(activedeal["completed_safety_orders_count"])
            max_safety_orders = float(activedeal["max_safety_orders"])
            martingale_volume_coefficient = float(
                activedeal["martingale_volume_coefficient"]
            )  # Safety order volume scale

            if completed_safety_orders < max_safety_orders:
                safetyfunds = calculate_deal_funds(
                    bovolume, sovolume, max_safety_orders, martingale_volume_coefficient, completed_safety_orders + 1
                )
                logger.debug(
                    f"Deal {activedeal['id']} has {max_safety_orders - completed_safety_orders} Safety Orders left for "
                    f"which {safetyfunds} is required."
                )
                dealsofunds += safetyfunds
            else:
                logger.debug(
                    f"Deal {activedeal['id']} has completed all {completed_safety_orders} Safety Orders. "
                    f"No additional funds required."
                )

            ## Still need to calculate the amount of funds additional SO's would require for each deal
            ## Deals could have different SO settings than max usage of the bot

        else:
            currentdealfunds += float(activedeal["sold_volume"])

            # If short if for one of the major types (currencies as supported by this script),
            # we should take those SO funds also into account

    finisheddeals = get_threecommas_deals(logger, api, bot_id, "finished")
    if finisheddeals is not None:
        yesterday = f"{(datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')}"

        # TODO Ready for improvement, compare date in a better way by converting to a 
        # datetime object and using that
        for finisheddeal in finisheddeals:
            if yesterday in finisheddeal["closed_at"]:
                yesterdayprofit += float(finisheddeal["final_profit"])
    
    logger.debug(
        f"Yesterday profit for {bot_id} is {yesterdayprofit}"
    )

    return currentdealfunds, dealsofunds, yesterdayprofit


def process_account_bots(account_id):
    """Process the bots of the account"""

    list_of_bots = []

    bots = get_threecommas_bots(logger, api, account_id)

    if bots is None:
        logger.debug(
            f"No bots found for account {account_id}"
        )
        return list_of_bots

    for botdata in bots:
        botname = botdata["name"]

        activedeals = int(botdata["active_deals_count"])
        enabled = bool(botdata["is_enabled"])
        if not enabled and activedeals == 0:
            logger.debug(
                f"'{botname}' not enabled and no active deals. Skipping."
            )
            continue

        bovolume = float(botdata["base_order_volume"])
        sovolume = float(botdata["safety_order_volume"])
        maxactivedeals = botdata["max_active_deals"]
        max_safety_orders = float(botdata["max_safety_orders"])
        martingale_volume_coefficient = float(
            botdata["martingale_volume_coefficient"]
        )  # Safety order volume scale

        strategy = botdata["strategy"]
        botpair = botdata["pairs"][0]
        quote = botpair.split("_")[0]

        dealfunds = calculate_deal_funds(
            bovolume, sovolume, max_safety_orders, martingale_volume_coefficient
        )

        # First calculate the funds which will be used by future deals
        maxfunds = (maxactivedeals - activedeals) * dealfunds

        # Second calculate funds used by current active deals
        dealdata = process_bot_deals(botdata["id"], strategy)
        currentdealfunds = dealdata[0]
        currentdealsofunds = dealdata[1]
        yesterdayprofitsum = dealdata[2]

        if enabled:
            maxfunds += currentdealfunds # Add currently used funds (BO + completed SO)
            maxfunds += currentdealsofunds # Remaining SO not yet completed
            logger.debug(
                f"'{botname}' max usage {maxfunds} based on {dealfunds} * {maxactivedeals - activedeals} "
                f"plus active deal SO funds {currentdealsofunds}. "
                f"Currently used funds: {currentdealfunds}"
            )
        else:
            maxfunds = currentdealfunds + currentdealsofunds
            logger.debug(
                f"'{botname}' disabled. Max usage is currently used funds "
                f"{currentdealfunds} plus SO funds {currentdealsofunds}"
            )

        botdict = {
            "name": botdata["name"],
            "strategy": strategy,
            "quote": quote,
            "current": currentdealfunds,
            "max": maxfunds,
            "yesterday_profit": yesterdayprofitsum
        }
        list_of_bots.append(botdict)

    return list_of_bots


def correct_fund_usage(bot_list, funds_list):
    """Calculate the fund usage"""

    for bot in bot_list:
        quote = bot["quote"]
        strategy = bot["strategy"]
        funds = bot["current"]

        quotefunds = 0.0
        if quote in funds_list:
            quotefunds = funds_list[quote]

        if strategy == "long":
            quotefunds += funds

            # User could have added manual SO's on top of the configured SO, 
            # substract that amount from the total funds
            exceedmax = funds - bot["max"]
            if exceedmax > 0.0:
                quotefunds -= exceedmax
        else:
            # Short bot fund usage must be substracted from the available amount of funds, because
            # those funds are needed when the short deal closes. 
            quotefunds -= funds

        logger.debug(
            f"{quote}: changed to {quotefunds} based on strategy {strategy} and current "
            f"funds {funds} of bot {bot['name']}"
        )

        funds_list[quote] = quotefunds

    return funds_list


def create_summary(bot_list, funds_list):
    """Create summary"""

    summary_list = []

    for currency in funds_list.keys():
        rounddigits = get_round_digits(currency)

        #correctedbalance = round(funds_list[currency], rounddigits)

        currentbotusage = 0.0
        maxbotusage = 0.0
        yesterdayprofit = 0.0
        for bot in bot_list:
            if bot["quote"] == currency and bot["strategy"] == "long":
                currentbotusage += bot["current"]
                maxbotusage += bot["max"]
                yesterdayprofit += bot["yesterday_profit"]

        #currentbotusage = round(currentbotusage, rounddigits)
        #maxbotusage = round(maxbotusage, rounddigits)

        free = round(funds_list[currency] - maxbotusage, rounddigits)
        freepercentage = 0.0
        if free > 0.0:
            freepercentage = round((free / funds_list[currency]) * 100.0, 2)

        currencydict = {
            "currency": currency,
            "balance": funds_list[currency],
            "current-bot-usage": currentbotusage,
            "max-bot-usage": maxbotusage,
            "yesterday-profit": yesterdayprofit,
            "free": free,
            "free %": freepercentage
        }
        summary_list.append(currencydict)

    return summary_list


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

# Initialize 3Commas API
api = init_threecommas_api(config)

# Create balance report
while True:

    # Reload config files and data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))
    debug = config.getboolean("settings", "debug")

    accounts = get_threecommas_accounts(logger, api)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = (datetime.now()).strftime("%Y-%m-%d")

    # Fetch all accounts
    for account in accounts:
        balance = get_threecommas_account_balance(logger, api, account["id"])
        historical_balance = get_threecommas_account_balance_chart_data(
            logger, api, account["id"], yesterday, today
        )
        logger.debug(historical_balance)
        logger.info("Getting account data for %s" % balance["name"])

        try:
            amount_yesterday = float(
                historical_balance[0]["usd"]
            )  # 0 = yesterday, 1 = today midnight, 2 = now
            amount_today = float(historical_balance[-1]["usd"])
            gainamount = amount_today - amount_yesterday
            if amount_yesterday:
                gainpercentage = round(
                    100 * (amount_today - amount_yesterday) / amount_yesterday, 2
                )
            else:
                gainpercentage = "NA"

            # Log global information for this exchange
            logger.info(
                f"Report for exchange: {balance['name']}\n"
                f"USD value: {round(float(historical_balance[-1]['usd']), 0)}. "
                f"Change from yesterday: {round(gainamount, 0)} ({gainpercentage}%)",
                True
            )

            # Get current funds of the account
            accountfundslist = create_account_balance(account["id"])
            logger.info(
                f"List of funds: {accountfundslist}"
            )

            # Collect bot and deal data
            botlist = process_account_bots(account["id"])
            if len(botlist) > 0:
                # Correct funds based on deal data
                accountfundslist = correct_fund_usage(botlist, accountfundslist)
                logger.info(
                    f"List of corrected funds: {accountfundslist}"
                )

                # Create summary based on the funds and log it
                summary = create_summary(botlist, accountfundslist)

                currencyoverview = ""
                for entry in summary:
                    rounddigits = get_round_digits(entry['currency'])

                    if currencyoverview:
                        currencyoverview += "\n"
                    currencyoverview += f"{entry['currency']}\n"
                    currencyoverview += f"- Balance: {entry['free']:0.{rounddigits}f} / {entry['balance']:0.{rounddigits}f} ({entry['free %']}% free)\n"
                    currencyoverview += f"- Profit yesterday: {entry['yesterday-profit']:0.{rounddigits}f}"

                if currencyoverview:
                    logger.info(currencyoverview, True)

            notification.send_notification()
        except IndexError:
            pass

    if not wait_time_interval(logger, notification, timeint, False):
        break
