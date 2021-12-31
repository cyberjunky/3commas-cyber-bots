#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sys
import time
from pathlib import Path

from telethon import TelegramClient, events

from helpers.logging import Logger, NotificationHandler
from helpers.threecommas import (
    get_threecommas_account,
    get_threecommas_market,
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
        "usdt-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "tgram-phone-number": "Your Telegram Phone number",
        "tgram-channel": "Telegram Channel to watch",
        "tgram-api-id": "Your Telegram API ID",
        "tgram-api-hash": "Your Telegram API Hash",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def watchlist_deal(thebot, triggerexchange, coin):
    """Check pair and trigger the bot deal."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    minvolume = thebot["min_volume_btc_24h"]

    logger.debug("Base coin for this bot: %s" % base)
    logger.debug("Minimal 24h volume in BTC for this bot: %s" % minvolume)

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account(logger, api, thebot["account_id"])
    if not marketcode:
        return

    # Load tickerlist for this exchange
    tickerlist = get_threecommas_market(logger, api, marketcode)
    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    # Update the blacklist
    blacklist = load_blacklist(logger, api, blacklistfile)
    if len(blacklistfile):
        skipchecks = True

    # Construct pair based on bot settings (BTC stays BTC, but USDT can become BUSD)
    pair = base + "_" + coin
    logger.debug("New pair constructed: %s" % pair)

    # Check if pair is on 3Commas blacklist
    if pair in blacklist:
        logger.debug(
            "This pair is on your 3Commas blacklist and was skipped: %s" % pair, True
        )
        return

    # TODO: replace with check if pair is in bot's pairlist
    # Check if pair is on 3Commas market ticker
    if pair not in tickerlist:
        logger.debug(
            "This pair is not valid on the '%s' market according to 3Commas and was skipped: %s"
            % (exchange, pair),
            True,
        )
        return

    # We have valid pair for our bot so we trigger a deal
    logger.info("Triggering your 3Commas bot")
    trigger_threecommas_bot_deal(logger, api, thebot, pair, skipchecks)


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
    blacklistfile = args.blacklist
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

# Watchlist telegram trigger
client = TelegramClient(
    f"{datadir}/{program}",
    config.get("settings", "tgram-api-id"),
    config.get("settings", "tgram-api-hash"),
).start(config.get("settings", "tgram-phone-number"))


@client.on(events.NewMessage(chats=config.get("settings", "tgram-channel")))
async def callback(event):
    """Parse Telegram message."""
    logger.info(
        "Received telegram message: '%s'" % event.message.text.replace("\n", " - "),
        True,
    )

    trigger = event.raw_text.splitlines()
    if trigger[0] == "BINANCE" or trigger[0] == "FTX" or trigger[0] == "KUCOIN":
        try:
            exchange = trigger[0].replace("\n", "")
            pair = trigger[1].replace("#", "").replace("\n", "")
            base = pair.split("_")[0].replace("#", "").replace("\n", "")
            coin = pair.split("_")[1].replace("\n", "")
            trade = trigger[2].replace("\n", "")
        except IndexError:
            logger.debug("Invalid trigger message format!")
            return

        logger.debug("Exchange: %s" % exchange)
        logger.debug("Pair: %s" % pair)
        logger.debug("Base: %s" % base)
        logger.debug("Coin: %s" % coin)
        logger.debug("Trade type: %s" % trade)

        if trade != "LONG":
            logger.debug(f"Trade type '{trade}' is not supported yet!")
            return
        if base == "USDT":
            botids = json.loads(config.get("settings", "usdt-botids"))
            if len(botids) == 0:
                logger.debug(
                    "No valid usdt-botids configured for '%s', disabled" % base
                )
                return
        elif base == "BTC":
            botids = json.loads(config.get("settings", "btc-botids"))
            if len(botids) == 0:
                logger.debug(
                    "No valid btc-botids configured for '%s', disabled" % base
                )
                return
        else:
            logger.error("Error the base of pair '%s' is not supported yet!" % pair)
            return

        for bot in botids:
            if bot == 0:
                logger.debug(
                    "No valid botid configured for '%s', skipping" % base
                )
                continue

            error, data = api.request(
                entity="bots",
                action="show",
                action_id=str(bot),
            )
            if data:
                await client.loop.run_in_executor(
                    None, watchlist_deal, data, exchange, coin
                )
            else:
                if error and "msg" in error:
                    logger.error("Error occurred triggering bots: %s" % error["msg"])
                else:
                    logger.error("Error occurred triggering bots")
    else:
        logger.info("Not a crypto trigger message, or exchange not yet supported")


# Start telegram client
client.start()
logger.info(
    "Listening to telegram chat '%s' for triggers"
    % config.get("settings", "tgram-channel"),
    True,
)
client.run_until_disconnected()
