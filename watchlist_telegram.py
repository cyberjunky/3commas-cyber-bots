#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
from math import nan
import os
import re
import sys
import time
from pathlib import Path

from telethon import TelegramClient, events

from helpers.logging import Logger, NotificationHandler
from helpers.smarttrade import (
    construct_smarttrade_position,
    construct_smarttrade_stoploss,
    construct_smarttrade_takeprofit
)
from helpers.threecommas import (
    get_threecommas_currency_rate,
    init_threecommas_api,
    load_blacklist,
    open_threecommas_smarttrade
)
from helpers.watchlist import (
    prefetch_marketcodes,
    process_botlist
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

    cfg["custom"] = {
        "channel-name": "Telegram Channel to watch",
        "usdt-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
    }

    cfg["smt"] = {
        "channel-name": "Telegram Channel to watch",
        "amount-usdt": 20,
        "amount-btc": 0.0001,
    }

    cfg["hodloo_5"] = {
        "exchange": "Bittrex / Binance / Kucoin",
        "bnb-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
        "busd-botids": [12345, 67890],
        "eth-botids": [12345, 67890],
        "eur-botids": [12345, 67890],
        "usdt-botids": [12345, 67890],
    }

    cfg["hodloo_10"] = {
        "exchange": "Bittrex / Binance / Kucoin",
        "bnb-botids": [12345, 67890],
        "btc-botids": [12345, 67890],
        "busd-botids": [12345, 67890],
        "eth-botids": [12345, 67890],
        "eur-botids": [12345, 67890],
        "usdt-botids": [12345, 67890],
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


async def handle_custom_event(event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received custom message '%s'"
        % (event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    trigger = event.raw_text.splitlines()

    try:
        exchange = trigger[0].replace("\n", "")
        pair = trigger[1].replace("#", "").replace("\n", "")
        base = pair.split("_")[0].replace("#", "").replace("\n", "")
        coin = pair.split("_")[1].replace("\n", "")

        # Fix for future pair format
        if coin.endswith(base) and len(coin) > len(base):
            coin = coin.replace(base, "")

        trade = trigger[2].replace("\n", "")
        if trade == "LONG" and len(trigger) == 4 and trigger[3] == "CLOSE":
            trade = "CLOSE"
    except IndexError:
        logger.debug("Invalid trigger message format!")
        return

    if exchange.lower() not in ("binance", "ftx", "kucoin"):
        logger.debug(
            f"Exchange '{exchange}' is not yet supported."
        )
        return

    if trade not in ('LONG', 'CLOSE'):
        logger.debug(f"Trade type '{trade}' is not supported yet!")
        return

    if base == "USDT":
        botids = json.loads(config.get("custom", "usdt-botids"))
        if len(botids) == 0:
            logger.debug(
                "No valid usdt-botids configured for '%s', disabled" % base
            )
            return
    elif base == "BTC":
        botids = json.loads(config.get("custom", "btc-botids"))
        if len(botids) == 0:
            logger.debug("No valid btc-botids configured for '%s', disabled" % base)
            return
    else:
        logger.error(
            "Error the base of pair '%s' being '%s' is not supported yet!" % (pair, base)
        )
        return

    if len(botids) == 0:
        logger.debug(
            f"{base}_{coin}: no valid botids configured for base '{base}'."
        )
        return

    await client.loop.run_in_executor(
        None, process_botlist, logger, api, blacklistfile, blacklist, marketcodes,
                                botids, coin, trade
    )


async def handle_forex_smarttrade_event(event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received message on Forex smarttrade: '%s'"
        % (event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    data = event.raw_text.splitlines()

    logger.debug(
        f"Converted raw text {event.raw_text} to {data}"
    )

    try:
        if data[0] in ("Short", "Long"):
            logger.debug(f"Received Short or Long message: {data}", True)
        elif "Targets" in event.message.text:
            logger.debug(f"Received Entry message: {data}", True)

            coin = None
            #msgentries = []
            msgstoploss = nan
            msgtargets = []

            for line in data:
                if "#" in line:
                    linedata = line.split(" ")

                    logger.debug(
                        f"'#' found in data, parsing {linedata}"
                    )

                    for l in linedata:
                        if "#" in l:
                            pair = l.replace("#", "")

                            if "/" in pair:
                                coin = pair.split("/")[0]
                            else:
                                coin = pair

                            break
                #elif "Entry" in line:
                #    msgentries.append(line.split("-")[1].replace("CMP", "").replace("$", ""))
                elif "Stoploss" or "SL:" in line:
                    #msgstoploss = float(line.split("-")[1].replace("$", ""))
                    content = re.search("[0-9]{1,5}[.,]\d{1,8}|[0-9]{2}", line)
                    if content is not None:
                        msgstoploss = re.string
                elif "Target" in line:
                    #msgtargets = line.replace("Targets - ", "").split("-")
                    content = line.split("(")[0]
                    msgtargets = re.findall("[0-9]{1,5}[.,]\d{1,8}|[0-9]{2}", content)

            logger.info(
                f"Received concrete smarttrade for {coin} with "
                f"stoploss '{msgstoploss}' and targets '{msgtargets}'",
                True
            )

            pair = f"USDT_{coin}"

            currentprice = get_threecommas_currency_rate(logger, api, "binance", pair)

            amount = config.getfloat("smt_forex", "amount-usdt")
            positionsize = amount / currentprice

            logger.debug(
                f"Calculated position {positionsize} based on amount {amount} and price {currentprice}"
            )

            position = construct_smarttrade_position("buy", "market", positionsize)

            logger.debug(
                f"Position {position} created."
            )

            tpstepvolume = 100.0 / len(msgtargets)
            logger.debug(
                f"Calculated step volume of {tpstepvolume} based on len {len(msgtargets)}"
            )

            tpsteps = list()
            for msgtarget in msgtargets:
                step = {}
                step["price"] = msgtarget
                step["volume"] = tpstepvolume
                tpsteps.append(step)

            takeprofit = construct_smarttrade_takeprofit(True, "limit", tpsteps)
            logger.debug(
                f"Takeprofit {takeprofit} created."
            )

            stoploss = construct_smarttrade_stoploss("limit", msgstoploss)
            logger.debug(
                f"Stoploss {stoploss} created."
            )

            open_threecommas_smarttrade(logger, api, "29981012", pair, position, takeprofit, stoploss)
    except Exception as e:
        logger.debug(f"Exception occured: {e}")
        return

    return


async def handle_cryptosignal_smarttrade_event(event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received message on CryptoSignal smarttrade: '%s'"
        % (event.message.text.replace("\n", " - "))
    )

    # Parse the event and do some error checking
    data = event.raw_text.splitlines()

    logger.debug(
        f"Converted raw text {event.raw_text} to {data}"
    )

    try:
        if "Targets" in event.message.text:
            logger.debug(f"Received Targets message: {data}", True)

            pair = None
            msgstoploss = nan
            msgtargets = []

            btcsatoshireq = False

            for line in data:
                if "/USDT" in line or "/BTC" in line:
                    pairlines = line.split(" ")
                    logger.debug(f"USDT or BTC found, parsing {pairlines}")
                    pair = pairlines[0]
                elif "Stoploss" or "SL:" in line:
                    #msgstoploss = float(line.split("-")[1].replace("$", ""))
                    content = re.search("[0-9]{1,5}[.,]\d{1,8}|[0-9]{2}", line)
                    if content is not None:
                        msgstoploss = re.string
                elif "Target" in line:
                    if "satoshi" in msgtarget:
                        btcsatoshireq = True

                    #msgtargets = line.replace("Targets - ", "").split("-")
                    content = line.split("(")[0]
                    msgtargets = re.findall("[0-9]{1,5}[.,]\d{1,8}|[0-9]{2}", content)

            logger.info(
                f"Received concrete smarttrade with for {pair} with "
                f"stoploss '{msgstoploss}' and targets '{msgtargets}'",
                True
            )

            base = pair.split("/")[1]
            coin = pair.split("/")[0]
            pair = f"{base}_{coin}"

            currentprice = get_threecommas_currency_rate(logger, api, "binance", pair)

            amount = config.getfloat("smt_cryptosignal", "amount-usdt")
            if base == "BTC":
                amount = config.getfloat("smt_cryptosignal", "amount-btc")

            positionsize = amount / currentprice

            logger.debug(
                f"Calculated position {positionsize} based on amount {amount} and price {currentprice}"
            )

            position = construct_smarttrade_position("buy", "market", positionsize)

            logger.debug(
                f"Position {position} created."
            )

            tpstepvolume = 100.0 / len(msgtargets)
            logger.debug(
                f"Calculated step volume of {tpstepvolume} based on len {len(msgtargets)}"
            )

            tpsteps = list()
            for msgtarget in msgtargets:
                step = {}

                step["price"] = float(msgtarget)
                if btcsatoshireq:
                    step["price"] *= 0.00000001
                step["volume"] = float(tpstepvolume)

                tpsteps.append(step)

            takeprofit = construct_smarttrade_takeprofit(True, "limit", tpsteps)
            logger.debug(
                f"Takeprofit {takeprofit} created."
            )

            stoploss = construct_smarttrade_stoploss("limit", msgstoploss)
            logger.debug(
                f"Stoploss {stoploss} created."
            )

            open_threecommas_smarttrade(logger, api, "29981012", pair, position, takeprofit, stoploss)
    except Exception as e:
        logger.debug(f"Exception occured: {e}")
        return

    return

def start_smarttrade():
    """Start a SmartTrade"""

    tpsteps = list()

    firststep = {}
    firststep["price"] = 30000.0
    firststep["volume"] = 50

    secondstep = {}
    secondstep["price"] = 40000.0
    secondstep["volume"] = 50

    tpsteps.append(firststep)
    tpsteps.append(secondstep)

    position = construct_smarttrade_position("buy", "market", 0.001)
    takeprofit = construct_smarttrade_takeprofit(True, "limit", tpsteps)
    stoploss = construct_smarttrade_stoploss(True, "limit", 15000.0)
    open_threecommas_smarttrade(logger, api, "29981012", "USDT_BTC", position, takeprofit, stoploss)


async def handle_hodloo_event(category, event):
    """Handle the received Telegram event"""

    logger.debug(
        "Received message on Hodloo %s: '%s'"
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
            f"{base}_{coin}: base '{base}' is not yet supported."
        )
        return

    botids = get_hodloo_botids(category, base)

    if len(botids) == 0:
        logger.debug(
            f"{base}_{coin}: no valid botids configured for base '{base}'."
        )
        return

    await client.loop.run_in_executor(
        None, process_botlist, logger, api, blacklistfile, blacklist, marketcodes,
                                botids, coin, "LONG"
    )


def get_hodloo_botids(category, base):
    """Get list of botids from configuration based on category and base"""

    return json.loads(config.get(f"hodloo_{category}", f"{base.lower()}-botids"))


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

# Validation of data before starting
hl5exchange = config.get("hodloo_5", "exchange")
if hl5exchange not in ("Bittrex", "Binance", "Kucoin"):
    logger.error(
        f"Exchange {hl5exchange} not supported. Must be 'Bittrex', 'Binance' or 'Kucoin'!"
    )
    sys.exit(0)

hl10exchange = config.get("hodloo_10", "exchange")
if hl10exchange not in ("Bittrex", "Binance", "Kucoin"):
    logger.error(
        f"Exchange {hl10exchange} not supported. Must be 'Bittrex', 'Binance' or 'Kucoin'!"
    )
    sys.exit(0)

# Initialize 3Commas API
api = init_threecommas_api(config)

# Prefetch marketcodes for all bots
# - Custom bots
allbotids = json.loads(config.get("custom", "usdt-botids")) + json.loads(config.get("custom", "btc-botids"))

# - Hodloo bots
for hlcategory in ("5", "10"):
    for hlbase in ("bnb", "btc", "busd", "eth", "eur", "usdt"):
        allbotids += get_hodloo_botids(hlcategory, hlbase)

marketcodes = prefetch_marketcodes(logger, api, allbotids)

# Prefetch blacklists
blacklist = load_blacklist(logger, api, blacklistfile)

# Watchlist telegram trigger
client = TelegramClient(
    f"{datadir}/{program}",
    config.get("settings", "tgram-api-id"),
    config.get("settings", "tgram-api-hash"),
).start(config.get("settings", "tgram-phone-number"))

customchannelname = config.get("custom", "channel-name")
customchannelid = -1

smtforexchannelname = config.get("smt_forex", "channel-name")
smtforexchannelid = -1

smtcryptosignalchannelname = config.get("smt_cryptosignal", "channel-name")
smtcryptosignalchannelid = -1

hl5channelname = f"Hodloo {hl5exchange} 5%"
hl5channelid = -1

hl10channelname = f"Hodloo {hl10exchange} 10%"
hl10channelid = -1

for dialog in client.iter_dialogs():
    if dialog.is_channel:
        logger.debug(
            f"{dialog.id}:{dialog.title}"
        )

        if dialog.title == customchannelname:
            customchannelid = dialog.id
        elif dialog.title == smtforexchannelname:
            smtforexchannelid = dialog.id
        elif dialog.title == smtcryptosignalchannelname:
            smtcryptosignalchannelid = dialog.id
        elif dialog.title == hl5channelname:
            hl5channelid = dialog.id
        elif dialog.title == hl10channelname:
            hl10channelid = dialog.id

logger.debug(
    f"Overview of resolved channel names: "
    f"Custom '{customchannelname}' to {customchannelid}, "
    f"Forex Smarttrade '{smtforexchannelname}' to {smtforexchannelid}, "
    f"Crypto Signal Smarttrade '{smtcryptosignalchannelname}' to {smtcryptosignalchannelid}, "
    f"Hodloo '{hl5channelname}' to {hl5channelid}, "
    f"Hodloo '{hl10channelname}' to {hl10channelid}"
)


if customchannelid != -1:
    logger.info(
        f"Listening to updates from '{customchannelname}' (id={customchannelid}) ...",
        True
    )
    @client.on(events.NewMessage(chats=customchannelid))
    async def callback_custom(event):
        """Receive Telegram message."""

        await handle_custom_event(event)
        notification.send_notification()


if smtforexchannelid != -1:
    logger.info(
        f"Listening to updates from '{smtforexchannelname}' (id={smtforexchannelid}) ...",
        True
    )
    @client.on(events.NewMessage(chats=smtforexchannelid))
    async def callback_forex_smarttrade(event):
        """Receive Telegram message."""

        await handle_forex_smarttrade_event(event)
        notification.send_notification()


if smtcryptosignalchannelid != -1:
    logger.info(
        f"Listening to updates from '{smtcryptosignalchannelname}' (id={smtcryptosignalchannelid}) ...",
        True
    )
    @client.on(events.NewMessage(chats=smtcryptosignalchannelid))
    async def callback_cryptosignal_smarttrade(event):
        """Receive Telegram message."""

        await handle_cryptosignal_smarttrade_event(event)
        notification.send_notification()


if hl5channelid != -1:
    logger.info(
        f"Listening to updates from '{hl5channelname}' (id={hl5channelid}) ...",
        True
    )
    @client.on(events.NewMessage(chats=hl5channelid))
    async def callback_5(event):
        """Receive Telegram message."""

        await handle_hodloo_event("5", event)
        notification.send_notification()


if hl10channelid != -1:
    logger.info(
        f"Listening to updates from '{hl10channelname}' (id={hl10channelid}) ...",
        True
    )
    @client.on(events.NewMessage(chats=hl10channelid))
    async def callback_10(event):
        """Receive Telegram message."""

        await handle_hodloo_event("10", event)
        notification.send_notification()


# Start telegram client
client.start()
logger.info(
    "Client started listening to updates on mentioned channels...",
    True
)
notification.send_notification()

client.run_until_disconnected()
