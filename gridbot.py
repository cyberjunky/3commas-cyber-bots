#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from helpers.logging import Logger, NotificationHandler
from helpers.misc import wait_time_interval
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
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "3c-apiselfsigned": "Your own generated API key, or empty",
        "notifications": False,
        "notify-urls": ["notify-url1", "notify-url2"],
    }

    cfg["gridbots_redbag_example"] = {
        "botids": [12345, 67890],
        "mode": "redbag",
    }

    cfg["gridbots_trade_example"] = {
        "botids": [12345, 67890],
        "mode": "trade",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "3c-apiselfsigned"):
        cfg.set("settings", "3c-apiselfsigned", "")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded the configuration file (3c-apiselfsigned)")

    return cfg


def strtofloat(txtstr):
    """Convert text string to float."""
    val = txtstr.text.strip()
    price = val.replace(".", "")
    floatval = price.replace(",", ".")

    return floatval


def get_gridbots_data(pair):
    """Get the best gridbot settings from grid-bots.com."""

    url = "https://www.grid-bots.com"
    coin = pair.split("_")[1]

    griddata = {}
    try:
        result = requests.get(url)
        result.raise_for_status()
        soup = BeautifulSoup(result.text, features="html.parser")
        tablerows = [t for t in soup.find_all("tr") if not t.find_all("table")]

        for row in tablerows:
            rowcolums = row.find_all("td")
            if len(rowcolums) > 0:
                gridcoin = rowcolums[0].text.strip()
                if coin == gridcoin:
                    griddata["lower"] = strtofloat(rowcolums[2])
                    griddata["upper"] = strtofloat(rowcolums[3])
                    griddata["numgrid"] = int(rowcolums[4].text.strip())
                    griddata["tokensgrid"] = strtofloat(rowcolums[5])
                    break

        logger.debug(griddata)
    except requests.exceptions.HTTPError as err:
        logger.error("Fetching grid-bots data failed with error: %s" % err)
        return griddata

    logger.info("Fetched grid-bots data OK")

    return griddata


def update_gridbot(gridbot, upperprice, lowerprice):
    """Update gridbot with new grid."""

    botname = gridbot["name"]
    pair = gridbot["pair"]

    error, data = api.request(
        entity="grid_bots",
        action="manual_update",
        action_id=str(gridbot["id"]),
        payload={
            "bot_id": gridbot["id"],
            "name": gridbot["name"],
            "account_id": gridbot["account_id"],
            "pair": gridbot["pair"],
            "upper_price": upperprice,
            "lower_price": lowerprice,
            "quantity_per_grid": gridbot["quantity_per_grid"],
            "grids_quantity": gridbot["grids_quantity"],
        },
    )
    if data:
        logger.info(
            f"Moved the grid of gridbot '{botname}' using pair {pair} with"
            f" upper and lower price: {upperprice} - {lowerprice}",
            True,
        )
        return None

    logger.error(
        f"Error occurred updating gridbot '{botname}' with new upper price"
        f" and lower price of {upperprice} & {lowerprice} : %s" % error["msg"]
    )
    return error["msg"]


def update_gridbot_activelines(gridbot, maxactivebuylines, maxactiveselllines):
    """Update gridbot with new active line settings."""

    botname = gridbot["name"]
    pair = gridbot["pair"]

    error, data = api.request(
        entity="grid_bots",
        action="manual_update",
        action_id=str(gridbot["id"]),
        payload={
            "bot_id": gridbot["id"],
            "name": gridbot["name"],
            "account_id": gridbot["account_id"],
            "pair": gridbot["pair"],
            "upper_price": gridbot["upper_price"],
            "lower_price": gridbot["lower_price"],
            'max_active_buy_lines': maxactivebuylines,
            'max_active_sell_lines': maxactiveselllines,
            "quantity_per_grid": gridbot["quantity_per_grid"],
            "grids_quantity": gridbot["grids_quantity"],
        },
    )
    if data:
        logger.info(
            f"Set active lines of gridbot '{botname}' to"
            f" buy: {maxactivebuylines} and sell: {maxactiveselllines}",
            True,
        )
        return None

    logger.error(
        f"Error occurred updating gridbot '{botname}' with new active lines"
        f" buy: {maxactivebuylines} and sell: {maxactiveselllines}: %s" % error["msg"]
    )
    return error["msg"]


def manage_gridbot(thebot):
    """Move grid to match pricing."""
    botname = thebot["name"]

    # bot values to calculate with
    pair = thebot["pair"]
    upperprice = thebot["upper_price"]
    lowerprice = thebot["lower_price"]
    quantitypergrid = thebot["quantity_per_grid"]
    gridsquantity = thebot["grids_quantity"]
    strategytype = thebot["strategy_type"]
    currentprice = thebot["current_price"]

    logger.info("Current settings for '%s':" % botname)
    logger.info("Pair: %s" % pair)
    logger.info("Upper price: %s" % upperprice)
    logger.info("Lower price: %s" % lowerprice)
    logger.info("Quantity per grid: %s" % quantitypergrid)
    logger.info("Grid quantity: %s" % gridsquantity)
    logger.info("Strategy type: %s" % strategytype)
    logger.info("Current price for %s is %s" % (pair, currentprice))

    gridinfo = get_gridbots_data(pair)

    if gridinfo is None:
        logger.info(f"No grid setup information found for {pair}, skipping update")
        return

    newupperprice = gridinfo["upper"]
    newlowerprice = gridinfo["lower"]
    # newtokensgrid = gridinfo["tokensgrid"]
    # newnumgrid = gridinfo["numgrid"]

    # Test updating active lines for @IamtheOnewhoKnocks:
    # maxactivebuylines = 3
    # maxactiveselllines = 3

    # update_gridbot_activelines(thebot, maxactivebuylines, maxactiveselllines)

    if float(upperprice) == float(newupperprice):
        logger.info(
            f"Grid of gridbot '{botname}' with pair {pair}\nis already using"
            " correct upper and price, skipping update.",
            True,
        )
        return

    logger.info(
        f"Grid of gridbot '{botname}' with pair {pair} will be adjusted like this:\n"
        f"Upper: {upperprice} -> {newupperprice} Lower: {lowerprice} -> {newlowerprice}",
        True,
    )
    return

    # Update the bot with new limits
    result = update_gridbot(thebot, newupperprice, newlowerprice)
    if result and "Upper price should be at least " in result:
        uprice = re.search("Upper price should be at least ([0-9.]+)", result)
        if uprice:
            upperprice = uprice[1]
            logger.info(
                f"New upper price was not accepted, retrying with suggested minimum price of {upperprice}"
            )
            result = update_gridbot(thebot, upperprice, newlowerprice)
            if result:
                logger.error(
                    f"Failed to update gridbot with suggested minimum upper price of {upperprice}"
                )

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
    config = upgrade_config(config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Auto tune a running gridbot
while True:

    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))
    botids = json.loads(config.get("settings", "botids"))

    # Walk through all bots specified
    for bot in botids:
        boterror, botdata = api.request(
            entity="grid_bots",
            action="get",
            action_id=str(bot),
        )
        if botdata:
            logger.debug("Raw Gridbot data: %s" % botdata)
            manage_gridbot(botdata)
        else:
            logger.error("Error occurred managing gridbots: %s" % boterror["msg"])

    if not wait_time_interval(logger, notification, timeint):
        break
