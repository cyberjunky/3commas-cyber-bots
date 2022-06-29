#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from helpers.logging import Logger, NotificationHandler
from helpers.misc import wait_time_interval
from helpers.threecommas import (
    get_threecommas_account_balance,
    get_threecommas_account_balance_chart_data,
    get_threecommas_accounts,
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

    accounts = get_threecommas_accounts(logger, api)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = (datetime.now()).strftime("%Y-%m-%d")

    list_of_dicts = []

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
            gain_amount = amount_today - amount_yesterday
            if amount_yesterday:
                gain_percentage = round(
                    100 * (amount_today - amount_yesterday) / amount_yesterday, 2
                )
            else:
                gain_percentage = "NA"
            thisdict = {
                "Name": balance["name"],
                "Exchange": balance["exchange_name"],
                "USD": round(float(historical_balance[-1]["usd"]), 0),
                "Gain USD": round(gain_amount, 0),
                "Gain %": gain_percentage,
            }
            list_of_dicts.append(thisdict)
        except IndexError:
            pass
    df = pd.DataFrame(
        list_of_dicts, columns=["Name", "Exchange", "USD", "Gain USD", "Gain %"]
    )
    print(df.to_string(index=False))

    if not wait_time_interval(logger, notification, timeint):
        break
