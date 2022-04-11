#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    get_botassist_data,
    populate_pair_lists,
    remove_excluded_pairs,
    wait_time_interval,
)
from helpers.threecommas import (
    control_threecommas_bots,
    get_threecommas_account_marketcode,
    get_threecommas_market,
    init_threecommas_api,
    load_blacklist,
    set_threecommas_bot_pairs,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "timeinterval": 1800,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }
    cfg["botassist_default"] = {
        "botids": [12345, 67890],
        "start-number": 1,
        "end-number": 200,
        "originalmaxdeals": 15,
        "mingalaxyscore": 0,
        "allowmaxdealchange": False,
        "allowbotstopstart": False,
        "list": "binance_spot_usdt_winner_60m",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, theapi, cfg):
    """Upgrade config file if needed."""

    for cfg_section in config.sections():
        if cfg_section.startswith("botassist_"):
            if not cfg.has_option(cfg_section, "originalmaxdeals"):
                thebotids = json.loads(cfg.get(cfg_section, "botids"))

                newmaxdeals = 0
                # Walk through all bots configured
                for thebot in thebotids:
                    boterror, botdata = theapi.request(
                        entity="bots",
                        action="show",
                        action_id=str(thebot),
                    )
                    if botdata:
                        if int(botdata["max_active_deals"]) > newmaxdeals:
                            newmaxdeals = int(botdata["max_active_deals"])
                    else:
                        if boterror and "msg" in boterror:
                            logger.error(
                                "Error occurred upgrading config: %s" % boterror["msg"]
                            )
                        else:
                            logger.error("Error occurred upgrading config")

                cfg.set(cfg_section, "originalmaxdeals", str(newmaxdeals))
                cfg.set(cfg_section, "allowmaxdealchange", "False")

                with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                    cfg.write(cfgfile)

                thelogger.info("Upgraded the configuration file (added deal changing)")

    for cfgsection in cfg.sections():
        if cfgsection.startswith("botassist_") and not cfg.has_option(cfgsection, "mingalaxyscore"):
            cfg.set(cfgsection, "mingalaxyscore", "0")
            cfg.set(cfgsection, "allowbotstopstart", "False")

            with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                cfg.write(cfgfile)

        thelogger.info("Upgraded the configuration file (mingalaxyscore and bot stop-start)")

    return cfg


def botassist_pairs(cfg_section, thebot, botassistdata):
    """Find new pairs and update the bot."""

    # Gather bot settings
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]

    if thebot["min_volume_btc_24h"] is None:
        minvolume = 0.0
    else:
        minvolume = float(thebot["min_volume_btc_24h"])

    newmaxdeals = False

    # Get deal settings for this bot
    mingalaxyscore = int(config.get(cfg_section, "mingalaxyscore", fallback=0))
    originalmaxdeals = int(config.get(cfg_section, "originalmaxdeals"))
    allowmaxdealchange = config.getboolean(
        cfg_section, "allowmaxdealchange", fallback=False
    )
    allowbotstopstart = config.getboolean(
        cfg_section, "allowbotstopstart", fallback=False
    )

    logger.info("Bot base currency: %s" % base)
    logger.debug("Bot minimal 24h BTC volume: %s" % minvolume)
    logger.debug("Bot allowmaxdealchange setting: %s" % allowmaxdealchange)

    # Start from scratch
    newpairs = list()
    badpairs = list()
    blackpairs = list()

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, thebot["account_id"])
    if not marketcode:
        return

    # Load tickerlist for this exchange
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    # Parse bot-assist data
    for pairdata in botassistdata:
        # Check if coin has minimum 24h volume as set in bot
        if pairdata["24h volume"] < minvolume:
            logger.debug(
                "Pair '%s' does not have enough 24h BTC volume (%s), skipping"
                % (pairdata["pair"], str(pairdata["volume"]))
            )
            continue

        if "galaxy-score" in pairdata and pairdata["galaxy-score"] < mingalaxyscore:
            logger.debug(
                "Pair '%s' with galaxyscore %s below minimal galaxyscore %s"
                % (pairdata["pair"], pairdata["galaxy-score"], str(mingalaxyscore))
            )
            continue

        # Populate lists
        populate_pair_lists(pairdata["pair"], blacklist, blackpairs, badpairs, newpairs, tickerlist)

    logger.debug("These pairs are blacklisted and were skipped: %s" % blackpairs)

    logger.debug(
        "These pairs are invalid on '%s' and were skipped: %s" % (marketcode, badpairs)
    )

    # If sharedir is set, other scripts could provide a file with pairs to exclude
    if sharedir is not None:
        remove_excluded_pairs(logger, sharedir, thebot['id'], marketcode, base, newpairs)

    if not newpairs:
        logger.info(
            "None of the 3c-tools bot-assist suggested pairs have been found on the %s (%s) exchange!"
            % (exchange, marketcode)
        )
        return

    # Lower the number of max deals if not enough new pairs and change allowed and
    # change back to original if possible
    if allowmaxdealchange:
        if len(newpairs) < thebot["max_active_deals"]:
            newmaxdeals = len(newpairs)
        elif (
            len(newpairs) > thebot["max_active_deals"]
            and len(newpairs) < originalmaxdeals
        ):
            newmaxdeals = len(newpairs)
        elif (
            len(newpairs) > thebot["max_active_deals"]
            and thebot["max_active_deals"] != originalmaxdeals
        ):
            newmaxdeals = originalmaxdeals

        if allowbotstopstart:
            if newmaxdeals == 0 and thebot["is_enabled"]:
                # No pairs and bot is running (zero pairs not allowed), so stop it...
                control_threecommas_bots(logger, api, thebot, "disable")
            elif newmaxdeals > 0 and not thebot["is_enabled"]:
                # Valid pairs and bot is not running, so start it...
                control_threecommas_bots(logger, api, thebot, "enable")

    # Update the bot with the new pairs
    set_threecommas_bot_pairs(logger, api, thebot, newpairs, newmaxdeals)


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument(
    "-d", "--datadir", help="directory to use for config and logs files", type=str
)
parser.add_argument(
    "-s", "--sharedir", help="directory to use for shared files", type=str
)
parser.add_argument(
    "-b", "--blacklist", help="local blacklist to use instead of 3Commas's", type=str
)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# pylint: disable-msg=C0103
if args.sharedir:
    sharedir = args.sharedir
else:
    sharedir = None

# pylint: disable-msg=C0103
if args.blacklist:
    blacklistfile = f"{datadir}/{args.blacklist}"
else:
    blacklistfile = None

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

# Upgrade config file if needed
config = upgrade_config(logger, api, config)

# Refresh coin pairs based on CoinMarketCap data
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    # Update the blacklist
    blacklist = load_blacklist(logger, api, blacklistfile)

    for section in config.sections():
        if section.startswith("botassist_"):
            # Bot configuration for section
            botids = json.loads(config.get(section, "botids"))

            # Download CoinMarketCap data
            startnumber = int(config.get(section, "start-number"))
            endnumber = 1 + (int(config.get(section, "end-number")) - startnumber)
            botassist_data = get_botassist_data(
                logger, config.get(section, "list"), startnumber, endnumber
            )

            if botassist_data:
                # Walk through all bots configured
                for bot in botids:
                    error, data = api.request(
                        entity="bots",
                        action="show",
                        action_id=str(bot),
                    )
                    if data:
                        botassist_pairs(section, data, botassist_data)
                    else:
                        if error and "msg" in error:
                            logger.error(
                                "Error occurred updating bots: %s" % error["msg"]
                            )
                        else:
                            logger.error("Error occurred updating bots")
            else:
                logger.error("Error occurred during fetch of botassist data")

    if not wait_time_interval(logger, notification, timeint):
        break
