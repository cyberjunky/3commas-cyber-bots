#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
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

    botinfo = data['bot_info']

    if botinfo:
        #Max active safety trades count
        active_safety_orders_count = botinfo['active_safety_orders_count']

        #Simultaneous deals per same pair
        allowed_deals_on_same_pair = botinfo['allowed_deals_on_same_pair']

        #Pairs
        botpairlist = botinfo['bot_pair_or_pairs']

        enabled = botinfo['enabled']

        #Safety order step scale
        martingale_step_coefficient = botinfo['martingale_step_coefficient']

        #Safety order volume scale
        martingale_volume_coefficient = botinfo['martingale_volume_coefficient']

        #Max active deals
        max_active_deals = botinfo['max_active_deals']

        #Max safety trades count
        max_safety_orders = botinfo['max_safety_orders']

        #Trading 24h minimal volume
        min_volume_btc_24h = botinfo['min_volume_btc_24h']

        #quote or base currency
        profit_currency = botinfo['profit_currency']

        # Price deviation to open safety orders (% from initial order)
        safety_order_step_percentage = botinfo['safety_order_step_percentage']

        strategy = botinfo['strategy']

        #Deal start condition
        strategy_list = botinfo['strategy_list']

        # Target profit (%)
        take_profit = botinfo['take_profit']

        take_profit_type = botinfo['take_profit_type']

        logger.info(
            f"Bot {bot_id}: \n"
            f"Max active safety trades count: {active_safety_orders_count}\n"
            f"Simultaneous deals per same pair: {allowed_deals_on_same_pair}\n"
            f"Bot pair(s): {botpairlist}\n"
            f"Enabled: {enabled}\n"
            f"Safety order step scale: {martingale_step_coefficient}\n"
            f"Safety order volume scale: {martingale_volume_coefficient}\n"
            f"Max active deals: {max_active_deals}\n"
            f"Max safety trades count: {max_safety_orders}\n"
            f"Min 24h volume: {min_volume_btc_24h}\n"
            f"Profit in: {profit_currency}\n"
            f"Price deviation to open safety orders: {safety_order_step_percentage}%\n"
            f"Strategy: {strategy}\n"
            f"Deal start conditions: {strategy_list}\n"
            f"TP: {take_profit}%\n"
            f"TP type: {take_profit_type}\n"
        )
    else:
        logger.info(
            f"No bot_info data for bot {bot_id}"
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

# No 3Commas API required

# Bot monitor watching for configuration changes
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
