#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from helpers.datasources import (
    get_lunarcrush_data
)
from helpers.logging import Logger, NotificationHandler
from helpers.misc import (
    format_pair,
    populate_pair_lists,
    remove_excluded_pairs,
    remove_prefix,
    wait_time_interval,
)
from helpers.threecommas import (
    control_threecommas_bots,
    get_threecommas_account_marketcode,
    get_threecommas_btcusd,
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
        "timeinterval": 3600,
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "3c-apikey-path": "Path to your own generated RSA private key, or empty",
        "lc-apikey": "Your LunarCrush API Key",
        "lc-fetchlimit": 150,
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["bot_12345"] = {
        "maxaltrankscore": 1500,
        "mingalaxyscore": 0.0,
        "numberofpairs": 10,
        "originalmaxdeals": 4,
        "allowmaxdealchange": False,
        "allowbotstopstart": False,
        "comment": "Just a description of the bot(s)",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    try:
        cfg.get("settings", "lc-fetchlimit")
    except configparser.NoOptionError:
        logger.error(f"Upgrading config file '{datadir}/{program}.ini'")
        cfg.set("settings", "lc-fetchlimit", "150")

    for cfgsection in cfg.sections():
        if cfgsection.startswith("bot_") and not cfg.has_option(cfgsection, "mingalaxyscore"):
            cfg.set(cfgsection, "mingalaxyscore", "0.0")
            cfg.set(cfgsection, "allowbotstopstart", "False")

            with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
                cfg.write(cfgfile)

            logger.info("Upgraded the configuration file (mingalaxyscore and bot stop-start)")

    if not cfg.has_option("settings", "3c-apikey-path"):
        cfg.set("settings", "3c-apikey-path", "")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded the configuration file (3c-apikey-path)")

    return cfg


def lunarcrush_pairs(cfg, thebot):
    """Find new pairs and update the bot."""

    # Gather some bot values
    bot_id = thebot["id"]
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]

    if thebot["min_volume_btc_24h"] is None:
        minvolume = 0.0
    else:
        minvolume = float(thebot["min_volume_btc_24h"])

    newmaxdeals = False

    # Get original max deal setting
    originalmaxdeals = int(cfg.get(f"bot_{bot_id}", "originalmaxdeals"))
    # Get lunarcrush settings for this bot
    numberofpairs = int(cfg.get(f"bot_{bot_id}", "numberofpairs"))
    maxacrscore = int(cfg.get(f"bot_{bot_id}", "maxaltrankscore", fallback=100))
    mingalaxyscore = float(cfg.get(f"bot_{bot_id}", "mingalaxyscore", fallback=0.0))
    allowmaxdealchange = config.getboolean(
        f"bot_{bot_id}", "allowmaxdealchange", fallback=False
    )
    allowbotstopstart = config.getboolean(
        f"bot_{bot_id}", "allowbotstopstart", fallback=False
    )

    logger.info("Bot base currency: %s" % base)
    logger.debug("Bot minimal 24h BTC volume: %s" % minvolume)
    logger.debug("Bot numberofpairs setting: %s" % numberofpairs)
    logger.debug("Bot maxaltrankscore setting: %s" % maxacrscore)
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

    # Fetch and parse LunaCrush data
    for entry in lunarcrush:
        try:
            coin = entry["s"]
            galaxyscore = entry["gs"]
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, base, coin)

            acrscore = float(entry["acr"])
            volbtc = float(entry["volbtc"])
            if volbtc is None:
                logger.debug("No valid 24h BTC volume for quote '%s', skipping" % coin)
                continue

            # Check if coin has minimum 24h volume as set in bot
            if volbtc < minvolume:
                logger.debug(
                    "Quote currency '%s' does not have enough 24h BTC volume (%s), skipping"
                    % (coin, str(volbtc))
                )
                continue

            # Check if coin has minimum AltRank score
            if acrscore > maxacrscore:
                logger.debug(
                    "Quote currency '%s' is not in AltRank score top %s (%s), skipping"
                    % (coin, maxacrscore, acrscore)
                )
                continue

            if galaxyscore < mingalaxyscore:
                logger.debug(
                    "Quote currency '%s' with galaxyscore %s below minimal galaxyscore %s"
                    % (coin, str(galaxyscore), str(mingalaxyscore))
                )

                break # Sorted list, so next coins will also be below the min galaxyscore

            # Populate lists
            populate_pair_lists(
                pair, blacklist, blackpairs, badpairs, newpairs, tickerlist
            )

            # Did we get enough pairs already?
            if numberofpairs:
                if len(newpairs) == numberofpairs:
                    break
            else:
                if len(newpairs) == int(thebot["max_active_deals"]):
                    break

        except KeyError as err:
            logger.error(
                "Something went wrong while parsing LunarCrush data. KeyError for field: %s"
                % err
            )
            return

    logger.debug("These pairs are blacklisted and were skipped: %s" % blackpairs)

    logger.debug(
        "These pairs are invalid on '%s' and were skipped: %s" % (marketcode, badpairs)
    )

    # If sharedir is set, other scripts could provide a file with pairs to exclude
    if sharedir is not None:
        remove_excluded_pairs(logger, sharedir, thebot["id"], marketcode, base, newpairs)

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
        if len(newpairs) == 0 and thebot["is_enabled"]:
            # No pairs and bot is running (zero pairs not allowed), so stop it...
            control_threecommas_bots(logger, api, thebot, "disable")
        elif len(newpairs) > 0 and not thebot["is_enabled"]:
            # Valid pairs and bot is not running, so start it...
            control_threecommas_bots(logger, api, thebot, "enable")

    # Update the bot with the new pairs
    if newpairs:
        set_threecommas_bot_pairs(logger, api, thebot, newpairs, newmaxdeals)
    else:
        logger.info(
            f"None of the 3c-tools bot-assist suggested pairs have been found on "
            f"the {exchange} ({marketcode}) exchange!"
        )

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

    # Upgrade config file if needed
    config = upgrade_config(config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(logger, config)
if not api:
    sys.exit(0)

logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Lunacrush GalayScore or AltRank pairs
while True:

    # Reload config files and data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))
    lcapikey = config.get("settings", "lc-apikey")

    # Update the blacklist
    blacklist = load_blacklist(logger, api, blacklistfile)

    # Download LunarCrush data
    usdtbtcprice = get_threecommas_btcusd(logger, api)
    lunarcrush = get_lunarcrush_data(logger, program, config, "settings", usdtbtcprice)

    for section in config.sections():
        # Each section is a bot
        if section.startswith("bot_"):
            botid = remove_prefix(section, "bot_")

            if botid:
                boterror, botdata = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(botid),
                )
                if botdata:
                    lunarcrush_pairs(config, botdata)
                else:
                    if boterror and "status_code" in boterror:
                        if boterror["status_code"] == 404:
                            logger.error(
                                "Error occurred updating bots: bot with id '%s' was not found" % botid
                            )
                        else:
                            logger.error(
                                "Error occurred updating bots: %s" % boterror["msg"]
                            )
                    elif boterror and "msg" in boterror:
                        logger.error(
                            "Error occurred updating bots: %s" % boterror["msg"]
                        )
                    else:
                        logger.error("Error occurred updating bots")
            else:
                logger.error("Invalid botid found: %s" % botid)
        elif section not in ("settings"):
            logger.warning(
                f"Section '{section}' not processed (prefix 'bot_' missing)!",
                False
            )

    if not wait_time_interval(logger, notification, timeint):
        break
