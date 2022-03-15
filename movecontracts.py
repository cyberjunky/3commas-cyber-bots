#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

import schedule

from helpers.logging import Logger, NotificationHandler
from helpers.threecommas import (
    get_threecommas_account_marketcode,
    get_threecommas_market,
    init_threecommas_api,
    set_threecommas_bot_pairs,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "debug": False,
        "logrotate": 7,
        "botids": [12345, 67890],
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def movecontract_pairs(thebot):
    """Check current pairs and replace expired ones."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    logger.info("Bot base currency: %s" % base)

    # Start from scratch
    newpairs = list()

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, thebot["account_id"])
    if not marketcode:
        return

    # Load tickerlist for this exchange
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    for pair in thebot["pairs"]:
        if not "MOVE" in pair:
            logger.info(f"Pair '{pair}' not a MOVE pair, skipping")
            continue

        if pair in tickerlist:
            logger.info(f"Pair '{pair}' still valid on '{marketcode}' market")
        else:
            logger.info(
                f"Pair '{pair}' not valid on '{marketcode}' market, possibly expired"
            )

            # Calculate current values
            now = datetime.date.today()
            today = f"{now.day:02d}"
            thismonth = f"{now.month:02d}"
            thisquarter = f"{(now.month-1)//3+1}"
            thisyear = now.year

            values = re.split(rf"^([A-Z]+)_([A-Z]+)-(MOVE)-([A-Z-0-9]+)", pair)
            if values:
                coin = values[1]
                base = values[2]
                value = values[4]
                start = f"{coin}_{base}-MOVE-"

                # Check for 'WK-0211', type weekly
                contracttype = re.search("^WK-([0-9]{2})([0-9]{2})", value)
                if contracttype:
                    month = contracttype[1]
                    day = contracttype[2]
                    logger.info(f"Detected Week Contract Month {month} Day {day}")

                    # Find the next valid week contract on market within next 7 days
                    for i in range(0, 7):
                        newday = datetime.date.today() + datetime.timedelta(i)
                        newpair = (
                            f"{coin}_{base}-MOVE-WK-{newday.month:02d}{newday.day:02d}"
                        )
                        if newpair in tickerlist:
                            break
                        logger.info(
                            "Could not find new valid Weekly MOVE contract, skipping"
                        )
                        return

                    logger.info(f"Generated new contract pair: '{newpair}'")
                    newpairs.append(newpair)
                    continue

                # Check for '2022Q1', type quarterly
                contracttype = re.search(rf"^([0-9]+)Q([0-9])", value)
                if contracttype:
                    quarter = contracttype[2]
                    year = contracttype[1]
                    logger.info(
                        f"Detected Quarterly Contract: Year {year} Quarter {quarter}"
                    )
                    newpair = f"{start}{thisyear}Q{thisquarter}"
                    logger.info(f"Generated new contract pair: '{newpair}'")
                    newpairs.append(newpair)
                    continue

                # Check for '0211', type daily
                contracttype = re.search("^([0-9]{2})([0-9]{2})", value)
                if contracttype:
                    month = contracttype[1]
                    day = contracttype[2]
                    logger.info(f"Detected Day Contract Month {month} Day {day}")
                    newpair = f"{start}{thismonth}{today}"
                    logger.info(f"Generated new contract pair: '{newpair}'")
                    newpairs.append(newpair)
                    continue

                if not contracttype:
                    logger.info(
                        f"Could not determine MOVE contract type of '{pair}',' skipping"
                    )
                    return

            else:
                logger.info(
                    f"Could not determine MOVE contract type of '{pair}', skipping"
                )
                return

    if not newpairs:
        return

    # Update the bot with the new pairs
    set_threecommas_bot_pairs(logger, api, thebot, newpairs, False)


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
    logger.info(f"Program with update the bot(s) at 00:00:01")

# Initialize 3Commas API
api = init_threecommas_api(config)

# MOVE contract pairs
def schedule_bots():
    """Update bots at midnight only."""

    # Configuration settings
    botids = json.loads(config.get("settings", "botids"))

    # Walk through all bots configured
    for bot in botids:
        error, data = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )

        if data:
            movecontract_pairs(data)
        else:
            if error and "msg" in error:
                logger.error("Error occurred updating bots: %s" % error["msg"])
            else:
                logger.error("Error occurred updating bots")


scheduler1 = schedule.Scheduler()
scheduler1.every().day.at("00:00:01").do(schedule_bots)
while True:
    scheduler1.run_pending()
    time.sleep(1)
