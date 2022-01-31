#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
from concurrent.futures import process
import configparser
import json
import os
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    get_shared_bot_data,
    remove_prefix,
    wait_time_interval,
)
from helpers.threecommas import (
    init_threecommas_api,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 86400,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "your 3Commas API Key",
        "3c-apisecret": "your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["botwatch_12345"] = {
        "secret": "secret",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def process_shared_bot_data(data, bot_id):
    """Process the downloaded data."""

    logger.info(
        f"Data for bot {bot_id}: {data}"
    )


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

# Refresh coin pairs based on CoinMarketCap data
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    for section in config.sections():
        if section.startswith("botwatch_"):
            # Bot configuration for section
            botid = remove_prefix(section, "botwatch_")
            botsecret = config.get(section, "secret")

            if botid:
                botdata = get_shared_bot_data(logger, botid, botsecret)

                if botdata:
                    process_shared_bot_data(botdata, botid)
                else:
                    logger.error("Error occurred, no shared bot data to process")

    if not wait_time_interval(logger, notification, timeint):
        break
