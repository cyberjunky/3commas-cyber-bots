#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import os
import sys
import time
from pathlib import Path

from telethon import TelegramClient, events

from helpers.logging import Logger, NotificationHandler
from helpers.misc import format_pair
from helpers.threecommas import (
    close_threecommas_deal,
    get_threecommas_account_marketcode,
    init_threecommas_api,
    load_blacklist,
    trigger_threecommas_bot_deal,
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
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "tgram-phone-number": "Your Telegram Phone number",
        "tgram-api-id": "Your Telegram API ID",
        "tgram-api-hash": "Your Telegram API Hash",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["hodloo_5"] = {
        "bnb-botid": 12345,
        "btc-botid": 12345,
        "busd-botid": 12345,
        "eth-botid": 12345,
        "eur-botid": 12345,
        "usdt-botid": 12345,
    }

    cfg["hodloo_10"] = {
        "bnb-botid": 12345,
        "btc-botid": 12345,
        "busd-botid": 12345,
        "eth-botid": 12345,
        "eur-botid": 12345,
        "usdt-botid": 12345,
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


async def handle_event(category, event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received telegram message on %s: '%s'"
        % (category, event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    trigger = event.raw_text.splitlines()

    pair = trigger[0].replace("\n", "").replace("**", "")
    base = pair.split("/")[1]
    coin = pair.split("/")[0]

    logger.info(
        f"Received message on {category}% for {base}_{coin}"
    )

    if base.lower() not in ("bnb", "btc", "busd", "eth", "eur", "usdt"):
        logger.debug(
            f"Base {base} is not supported yet! Skipping."
        )
        return

    botid = get_botid(category, base)
    if botid == 0:
        logger.debug(
            f"No valid bot configured for {base}. Skipping."
        )
        return

    logger.debug(f"Configured botid for {base} is {botid}")

    # Get bot data and process the deal
    error, data = api.request(
        entity="bots",
        action="show",
        action_id=str(botid),
    )
    if data:
        # Check number of deals, otherwise error will occur anyway (save some processing)
        if data["active_deals_count"] >= data["max_active_deals"]:
            logger.info(
                f"Bot '{data['name']}' on max number of deals ({data['max_active_deals']}). "
                f"Cannot start a new one for {base}_{coin}!",
                True
            )
        else:
            await client.loop.run_in_executor(
                None, watchlist_deal, data, coin, "LONG"
            )
    else:
        if error and "msg" in error:
            logger.error("Error occurred triggering bots: %s" % error["msg"])
        else:
            logger.error("Error occurred triggering bots")

    notification.send_notification()


def watchlist_deal(thebot, coin, trade):
    """Check pair and trigger the bot deal."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    minvolume = thebot["min_volume_btc_24h"]

    logger.debug("Base coin for this bot: %s" % base)
    logger.debug("Minimal 24h volume of %s BTC" % minvolume)

    # Get marketcode from array
    marketcode = marketcodes.get(thebot["id"])
    if not marketcode:
        return
    logger.info("Bot: %s" % thebot["name"])
    logger.info("Exchange %s (%s) used" % (exchange, marketcode))

    # Construct pair based on bot settings and marketcode (BTC stays BTC, but USDT can become BUSD)
    pair = format_pair(logger, marketcode, base, coin)

    if trade == "LONG":
        # Check if pair is on 3Commas blacklist
        if pair in blacklist:
            logger.debug(
                "Pair '%s' is on your 3Commas blacklist and was skipped" % pair, True
            )
            return

        # Check if pair is in bot's pairlist
        if pair not in thebot["pairs"]:
            logger.info(
                "Pair '%s' is not in bot's pairlist and was skipped" % pair,
                True,
            )
            return

        # We have valid pair for our bot so we trigger an open asap action
        logger.info("Triggering your 3Commas bot for a start deal of '%s'" % pair)
        trigger_threecommas_bot_deal(logger, api, thebot, pair, (len(blacklistfile) == 0))
    else:
        # Find active deal(s) for this bot so we can close deal(s) for pair
        deals = thebot["active_deals"]
        if deals:
            for deal in deals:
                if deal["pair"] == pair:
                    logger.info("Triggering your 3Commas bot for a (panic) sell of '%s'" % pair)
                    close_threecommas_deal(logger, api, deal["id"], pair)
                    return

            logger.info(
                "No deal(s) running for bot '%s' and pair '%s'"
                % (thebot["name"], pair), True
            )
        else:
            logger.info("No deal(s) running for bot '%s'" % thebot["name"], True)


def prefetch_marketcodes():
    """Gather and store marketcodes for all bots."""

    marketcodearray = {}
    botids = list()

    for category in ("5", "10"):
        for base in ("bnb", "btc", "busd", "eth", "eur", "usdt"):
            botid = get_botid(category, base)

            if botid not in ("0") and botid not in botids:
                botids.append(botid)

    logger.debug(
        f"Botids collected: {botids}"
    )

    for botid in botids:
        if botid:
            boterror, botdata = api.request(
                entity="bots",
                action="show",
                action_id=str(botid),
            )
            if botdata:
                accountid = botdata["account_id"]
                # Get marketcode (exchange) from account if not already fetched
                marketcode = get_threecommas_account_marketcode(logger, api, accountid)
                marketcodearray[botdata["id"]] = marketcode
            else:
                if boterror and "msg" in boterror:
                    logger.error(
                        "Error occurred fetching marketcode data: %s" % boterror["msg"]
                    )
                else:
                    logger.error("Error occurred fetching marketcode data")

    return marketcodearray


def get_botid(category, base):
    """Get botid from configuration based on category and base"""

    return config.get(f"hodloo_{category}", f"{base.lower()}-botid")


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument("-d", "--datadir", help="data directory to use", type=str)
parser.add_argument("-b", "--blacklist", help="blacklist to use", type=str)

args = parser.parse_args()
if args.datadir:
    datadir = args.datadir
else:
    datadir = os.getcwd()

# pylint: disable-msg=C0103
if args.blacklist:
    blacklistfile = f"{datadir}/{args.blacklist}"
else:
    blacklistfile = ""

# Create or load configuration file
config = load_config()
if not config:
    logger = Logger(datadir, program, None, 7, False, False)
    logger.info(
        f"Created example config file '{program}.ini', edit it and restart the program"
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

# Initialize 3Commas API
api = init_threecommas_api(config)

# Prefect marketcodes for all bots
marketcodes = prefetch_marketcodes()

# Prefect blacklists
blacklist = load_blacklist(logger, api, blacklistfile)

# Watchlist telegram trigger
client = TelegramClient(
    f"{datadir}/{program}",
    config.get("settings", "tgram-api-id"),
    config.get("settings", "tgram-api-hash"),
).start(config.get("settings", "tgram-phone-number"))


@client.on(events.NewMessage(chats="Hodloo Binance 5%"))
async def callback_5(event):
    """Receive Telegram message."""

    await handle_event("5", event)

    notification.send_notification()


@client.on(events.NewMessage(chats="Hodloo Binance 10%"))
async def callback_10(event):
    """Receive Telegram message."""

    await handle_event("10", event)

    notification.send_notification()


# Start telegram client
client.start()
logger.info(
    "Listening to telegram chat '%s' and '%s' for triggers"
    % ("Hodloo Binance 5%", "Hodloo Binance 10%"),
    True,
)
client.run_until_disconnected()
