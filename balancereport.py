#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
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
from helpers.threecommas_smarttrade import (
    get_threecommas_smarttrade_orders,
    get_threecommas_smarttrades
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
        "conditional-botids": [],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "conditional-botids"):
        cfg.set("settings", "conditional-botids", "[]")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded section settings to have conditional-botids")

    return cfg


def create_account_balance(account_id):
    """Create the account balance"""

    list_of_funds = {}

    balancetable = get_threecommas_account_table_balance(logger, api, account_id)
    if balancetable is None:
        return None

    for currency in balancetable:
        code = currency["currency_code"]

        if code not in ("BUSD", "EUR", "USD", "USDT", "BTC", "BNB", "ETH"):
            continue

        # Position is the total, including reserved but excluding active deals (for
        # which the currency has been exchanged and will come back after closing the deal)
        position = currency["position"]

        list_of_funds[code] = position

    return list_of_funds


def process_bot_deals(bot_id, bot_name, strategy):
    """Process the deals of the bot"""

    currentdealfunds = 0.0
    dealsofunds = 0.0
    yesterdayprofit = 0.0

    activedeals = get_threecommas_deals(logger, api, bot_id, "active")
    if activedeals is None:
        logger.debug(
            f"No deals active for '{bot_name}'"
        )
    else:
        logger.debug(
            f"Processing active deals of bot '{bot_name}'..."
        )

        for activedeal in activedeals:
            if strategy == "long":
                currentdealfunds += float(activedeal["bought_volume"])

                bovolume = float(activedeal["base_order_volume"])
                sovolume = float(activedeal["safety_order_volume"])
                completed_manual_safety_orders = int(
                    activedeal["completed_manual_safety_orders_count"]
                ) #Filled manual SO
                completed_safety_orders = int(
                    activedeal["completed_safety_orders_count"]
                ) #Filled automatic SO (excluding manual)
                max_safety_orders = int(
                    activedeal["max_safety_orders"]
                ) #Max automatic SO
                current_active_safety_orders = int(
                    activedeal["current_active_safety_orders_count"]
                ) #Number of active SO
                martingale_volume_coefficient = float(
                    activedeal["martingale_volume_coefficient"]
                )

                activesofunds = 0.0
                if completed_safety_orders < max_safety_orders:
                    # Calculate required funds for remaining SO and active SO (which is
                    # less or equal to remaining)
                    dealfunddata = calculate_deal_funds(
                        bovolume, sovolume, max_safety_orders, martingale_volume_coefficient,
                        completed_safety_orders + 1, current_active_safety_orders
                    )

                    remainingsofunds = dealfunddata[0]
                    activesofunds = dealfunddata[1]

                    if (max_safety_orders > 0 and current_active_safety_orders == 0):
                        # Substract bought volume from required funds for all SO's
                        # only when the SO's are not filled yet
                        if remainingsofunds > float(activedeal["bought_volume"]):
                            remainingsofunds -= float(activedeal["bought_volume"])
                        else:
                            remainingsofunds = 0.0

                        logger.debug(
                            f"Deal {activedeal['id']} SO is managed by trailingstoploss_tp script; "
                            f"in total {remainingsofunds} required and "
                            f"currently {activesofunds} in active SO."
                        )
                    else:
                        # Substract BO because it's already included in the 'bought_volume' above
                        # and we are only interested in SO funds
                        remainingsofunds -= bovolume

                        logger.debug(
                            f"Deal {activedeal['id']} has "
                            f"{max_safety_orders - completed_safety_orders} SO left; "
                            f"in total {remainingsofunds} required and "
                            f"currently {activesofunds} in active SO."
                        )
                    dealsofunds += remainingsofunds
                else:
                    logger.debug(
                        f"Deal {activedeal['id']} has completed {completed_safety_orders} SO and "
                        f"{completed_manual_safety_orders} manual SO. No additional funds required."
                    )

                if current_active_safety_orders > 0:
                    # There are SO active, which could be `automatic` from the configuration or
                    # manual. Above the current active SO funds where calculated, so substract
                    # this from the reserved funds and add the remaining sum (which must be for
                    # manual placed orders, like a limit order) to the total amount of SO funds
                    # for this deal.
                    reservedfunds = float(activedeal["reserved_quote_funds"])
                    manualfunds = abs(activesofunds - reservedfunds)
                    dealsofunds += manualfunds

                    logger.debug(
                        f"Deal {activedeal['id']} has {reservedfunds} funds reserved "
                        f"for {current_active_safety_orders} SO. Funds for active SO "
                        f"are {activesofunds}, so {manualfunds} is manually placed."
                    )
            else:
                currentdealfunds += float(activedeal["sold_volume"])

                # If short is for one of the major types (currencies as supported by this script),
                # we should take those SO funds also into account

    finisheddeals = get_threecommas_deals(logger, api, bot_id, "finished")
    if finisheddeals is not None:
        yesterdaydate = f"{(datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')}"

        # TODO Ready for improvement, compare date in a better way by converting to a
        # datetime object and using that
        for finisheddeal in finisheddeals:
            if yesterdaydate in finisheddeal["closed_at"]:
                yesterdayprofit += float(finisheddeal["final_profit"])

    logger.debug(
        f"Yesterday profit of {yesterdayprofit} for '{bot_name}'"
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

    conditionalbotids = json.loads(config.get("settings", "conditional-botids"))

    for botdata in bots:
        botname = botdata["name"]

        activedeals = int(botdata["active_deals_count"])
        enabled = bool(botdata["is_enabled"])

        if botdata["id"] in conditionalbotids:
            logger.debug(
                f"'{botname}' is in list of conditional bots, so process it "
                f"as if it's enabled."
            )
            enabled = True

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

        # Calculate remaining SO funds and ignore second return value (active SO funds)
        dealfunds = calculate_deal_funds(
            bovolume, sovolume, max_safety_orders, martingale_volume_coefficient
        )[0]

        # First calculate the funds which will be used by future deals
        maxfunds = (maxactivedeals - activedeals) * dealfunds

        # Second calculate funds used by current active deals
        dealdata = process_bot_deals(botdata["id"], botname, strategy)
        currentdealfunds = dealdata[0]
        currentdealsofunds = dealdata[1]
        yesterdayprofitsum = dealdata[2]

        if enabled:
            maxfunds += currentdealfunds # Add currently used funds (BO + completed SO)
            maxfunds += currentdealsofunds # Remaining SO not yet completed
            logger.debug(
                f"'{botname}' max usage {maxfunds} based on {dealfunds} * "
                f"{maxactivedeals - activedeals} plus active deal SO "
                f"funds {currentdealsofunds}. "
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


def correct_bot_fund_usage(bot_list, funds_list):
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
            # those funds are required for closing the short deal.
            quotefunds -= funds

        logger.debug(
            f"{quote}: changed from {funds_list[quote]} to {quotefunds} "
            f"based on strategy {strategy} and current used "
            f"funds {funds} of bot {bot['name']}"
        )

        funds_list[quote] = quotefunds

    return funds_list


def process_account_trades(account_id):
    """Process the trades of the account"""

    list_of_trades = []

    trades = get_threecommas_smarttrades(logger, api, account_id, "active")
    if trades is None:
        logger.debug(
            f"No smarttrades found for account {account_id}"
        )
        return list_of_trades

    for trade in trades:
        positiontype = trade["position"]["type"]
        tradepair = trade["pair"]
        quote = tradepair.split("_")[0]

        orderdata = get_threecommas_smarttrade_orders(logger, api, trade["id"])

        reserved = 0.0
        for order in orderdata:
            if order["order_side"] == "buy" and order["status"] == "order_placed":
                reserved += float(order["initial_total"])

                logger.debug(
                    f"Open order {order['id']} for {order['initial_total']} found; "
                    f"increased reserved amount to {reserved}"
                )

        # Gather current profit of open trade. Only consider when trade is actually
        # started and orders are filled
        currentprofit = 0.0
        if trade["status"]["type"] == "waiting_targets":
            currentprofit = float(trade["profit"]["volume"])

        tradedict = {
            "id": trade["id"],
            "pair": trade["pair"],
            "strategy": "long" if positiontype == "buy" else "short",
            "quote": quote,
            "current": float(trade["data"]["entered_total"]),
            "current_profit": currentprofit,
            "reserved": reserved
        }
        list_of_trades.append(tradedict)

        logger.debug(
            f"'{trade['id']}/{trade['pair']}' currently using {tradedict['current']} "
            f"and reserved {tradedict['reserved']} funds."
        )

    return list_of_trades


def correct_trade_fund_usage(trade_list, funds_list):
    """Calculate the fund usage"""

    for trade in trade_list:
        quote = trade["quote"]
        strategy = trade["strategy"]
        funds = trade["current"]

        quotefunds = 0.0
        if quote in funds_list:
            quotefunds = funds_list[quote]

        if strategy == "long":
            quotefunds += funds
        else:
            # Short bot fund usage must be substracted from the available amount of funds, because
            # those funds are required for closing the short deal.
            quotefunds -= funds

        logger.debug(
            f"{quote}: changed from {funds_list[quote]} to {quotefunds} "
            f"based on strategy {strategy} and required "
            f"funds {funds} of trade {trade['pair']} ({trade['id']})"
        )

        funds_list[quote] = quotefunds

    return funds_list


def create_summary(funds_list, bot_list, trade_list):
    """Create summary"""

    summary_list = []

    for currency in funds_list.keys():
        # Summary for bots
        botcount = 0
        currentbotusage = 0.0
        maxbotusage = 0.0
        yesterdaybotprofit = 0.0
        for bot in bot_list:
            if bot["quote"] == currency:
                botcount += 1
                if bot["strategy"] == "long":
                    currentbotusage += bot["current"]
                    maxbotusage += bot["max"]
                    yesterdaybotprofit += bot["yesterday_profit"]

        # Summary for trades
        tradecount = 0
        currenttradeusage = 0.0
        reservedtradeusage = 0.0
        currenttradeprofit = 0.0
        for trade in trade_list:
            if trade["quote"] == currency:
                tradecount += 1
                if trade["strategy"] == "long":
                    currenttradeusage += trade["current"]
                    reservedtradeusage += trade["reserved"]
                    currenttradeprofit += trade["current_profit"]

        free = funds_list[currency] - maxbotusage - currenttradeusage - reservedtradeusage
        freepercentage = 0.0
        if free > 0.0:
            freepercentage = round((free / funds_list[currency]) * 100.0, 2)

        currencydict = {
            "currency": currency,
            "balance": funds_list[currency],
            "bot-count": botcount,
            "current-bot-usage": currentbotusage,
            "max-bot-usage": maxbotusage,
            "yesterday-bot-profit": yesterdaybotprofit,
            "trade-count": tradecount,
            "current-trade-usage": currenttradeusage,
            "reserved-trade-usage": reservedtradeusage,
            "max-trade-usage": currenttradeusage + reservedtradeusage,
            "current-trade-profit": currenttradeprofit,
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

    # Upgrade config file if needed
    config = upgrade_config(config)

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

        if balance is None or historical_balance is None:
            logger.warning(
                f"Failed to fetch balance data for account {account['id']}. "
                f"Skip for now and retry next time!"
            )
            continue

        logger.debug(historical_balance)
        logger.info(f"Fetching account data for {balance['name']}")

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
            if accountfundslist is None:
                logger.warning(
                    f"Fetching funds for account {balance['name']} failed."
                    f"Can't collect & show more stats without fund(s) information."
                )
                continue

            logger.info(
                f"Initial list of account funds: {accountfundslist}"
            )

            # Collect bot and deal data
            botlist = process_account_bots(account["id"])
            if len(botlist) > 0:
                # Correct funds based on deal data
                accountfundslist = correct_bot_fund_usage(botlist, accountfundslist)
                logger.info(
                    f"Account funds after correction for bots: {accountfundslist}"
                )

            # Collect Trades data
            tradelist = process_account_trades(account["id"])
            if len(tradelist) > 0:
                # Correct funds based on deal data
                accountfundslist = correct_trade_fund_usage(tradelist, accountfundslist)
                logger.info(
                    f"Account funds after correction for trades: {accountfundslist}"
                )

            # Create summary based on the funds and log it
            summary = create_summary(accountfundslist, botlist, tradelist)

            currencyoverview = ""
            for entry in summary:
                rounddigits = get_round_digits(entry['currency'])

                if currencyoverview:
                    currencyoverview += "\n"
                currencyoverview += f"{entry['currency']}\n"
                currencyoverview += f"- Balance: {entry['free']:0.{rounddigits}f} / {entry['balance']:0.{rounddigits}f} ({entry['free %']}% free)\n"
                currencyoverview += f"  - Bots: {entry['current-bot-usage']:0.{rounddigits}f} / {entry['max-bot-usage']:0.{rounddigits}f}\n"
                currencyoverview += f"  - Trades: {entry['current-trade-usage']:0.{rounddigits}f} / {entry['max-trade-usage']:0.{rounddigits}f}\n"
                currencyoverview += "- Profit:\n"
                currencyoverview += f"  - Bots yesterday: {entry['yesterday-bot-profit']:0.{rounddigits}f}\n"
                currencyoverview += f"  - Trades current: {entry['current-trade-profit']:0.{rounddigits}f}"

            if currencyoverview:
                logger.info(currencyoverview, True)

            # Send notification for each account, so the user can see it as seperate messages
            notification.send_notification()
        except IndexError:
            pass

    if not wait_time_interval(logger, notification, timeint, False):
        break
