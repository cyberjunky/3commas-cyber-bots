#!/usr/bin/env python3
"""Cyberjunky's 3commas helpers."""
import argparse
import configparser
import os
import sys
import time
from pathlib import Path
from telethon import TelegramClient, events
from binance.client import Client, BinanceAPIException
from helpers.misc import binance_pair, futures_pair, spot_pair
from helpers.logging import Logger, NotificationHandler
from helpers.threecommas import (
    get_threecommas_account_balance,
    get_threecommas_account_marketcode,
    init_threecommas_api,
    smart_lev_trades,
    smart_spot_trades,
    panic_close_smart,
    get_active_smart_trades,
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
        "accounts": 000000,
        "risk-of-trade": 1.0,
        "tp1": 2.5,
        "tp2": 5.0,
        "tp3": 7.5,
        "tp4": 10.0,
        "vol1": 20.0,
        "vol2": 20.0,
        "vol3": 20.0,
        "vol4": 20.0,
        "vol5": 20.0,
        "leverage": 1,
    }
    cfg["telegram"] = {
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


def smart_trade(cfg, side, inputstoploss, pair):
    accounts = (cfg.get("settings", "accounts")).split(",")
    risk = float(cfg.get("settings", "risk-of-trade"))
    lev = int(cfg.get("settings", "leverage"))
    take_profit1 = float(cfg.get("settings", "tp1"))
    take_profit2 = float(cfg.get("settings", "tp2"))
    take_profit3 = float(cfg.get("settings", "tp3"))
    take_profit4 = float(cfg.get("settings", "tp4"))
    take_profit5 = float(cfg.get("settings", "tp5"))
    side = side
    inputstoploss = inputstoploss
    coin = pair
    try:
        pair_price = clients.get_symbol_ticker(symbol=binance_pair(pair))["price"]
    except BinanceAPIException as e:
        logger.info(f"{e.message} is Invalid symbol {e.status_code}", True)
        return

    # Do we want Stop loss ?!
    if inputstoploss == 0:
        stop = True
    else:
        stop = False
    if side == "CLOSE":
        panic_close_smart(config, logger, api, get_active_smart_trades(config, logger, api))
    else:
        if side == "SELL":
            types = "sell"
            if stop:
                stoploss = 0
            else:
                stoploss = float(pair_price) + (float(pair_price) * (inputstoploss / 100))
            tp1 = float(pair_price) - (float(pair_price) * (take_profit1 / 100))
            tp2 = float(pair_price) - (float(pair_price) * (take_profit2 / 100))
            tp3 = float(pair_price) - (float(pair_price) * (take_profit3 / 100))
            tp4 = float(pair_price) - (float(pair_price) * (take_profit4 / 100))
            tp5 = float(pair_price) - (float(pair_price) * (take_profit5 / 100))

        else:
            types = "buy"
            if stop:
                stoploss = 0
            else:
                stoploss = float(pair_price) - (float(pair_price) * (inputstoploss / 100))
            tp1 = float(pair_price) + (float(pair_price) * (take_profit1 / 100))
            tp2 = float(pair_price) + (float(pair_price) * (take_profit2 / 100))
            tp3 = float(pair_price) + (float(pair_price) * (take_profit3 / 100))
            tp4 = float(pair_price) + (float(pair_price) * (take_profit4 / 100))
            tp5 = float(pair_price) + (float(pair_price) * (take_profit5 / 100))
        for account in accounts:
            market_code = get_threecommas_account_marketcode(logger, api, account)
            capital = float(get_threecommas_account_balance(logger, api, account)["usd_amount"])
            risk_percentage = capital * (risk / 100)
            if stop:
                capital_per_trade = risk_percentage * 10
            else:
                capital_per_trade = risk_percentage / inputstoploss * 100

            if market_code == "binance_futures":
                capital = capital * (risk / 100) / lev
                posvalue = capital_per_trade / float(pair_price)
                pair = futures_pair(coin)
                smart_lev_trades(config, logger, api, pair, posvalue, lev, account, types, stoploss, tp1, tp2, tp3, tp4,
                                 tp5)

            elif market_code == "binance_futures_coin":
                continue
            else:
                # no SHORT for SPOT
                if types == "sell":
                    logger.error("Selling SPOT is not available ")
                    continue

                else:
                    capital = capital * (risk / 100)
                    posvalue = capital_per_trade / float(pair_price)
                    pair = spot_pair(coin)
                    smart_spot_trades(config, logger, api, pair, posvalue, account, stoploss, tp1, tp2, tp3, tp4, tp5)


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky Zcrypto Smart-Trade telegram.")
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
        config.getboolean("telegram", "notifications"),
        config.get("telegram", "notify-urls"),
    )

    # Initialise logging
    logger = Logger(
        datadir,
        program,
        notification,
        int(config.get("settings", "logrotate", fallback=7)),
        config.getboolean("settings", "debug"),
        config.getboolean("telegram", "notifications"),
    )

# Initialize 3Commas API
api = init_threecommas_api(config)

# Watchlist telegram trigger
# noinspection PyTypeChecker
client = TelegramClient(
    f"{datadir}/{program}",
    config.get("telegram", "tgram-api-id"),
    config.get("telegram", "tgram-api-hash"),
).start(config.get("telegram", "tgram-phone-number"))


@client.on(events.NewMessage(chats=config.get("telegram", "tgram-channel")))
async def callback(event):
    """Parse Telegram message."""
    logger.info(
        "Received telegram message: '%s'" % event.message.text.replace("\n", " - "),
        True,
    )

    trigger = event.raw_text.splitlines()

    if trigger[0] == "LONG" or trigger[0] == "SELL" or trigger[0] == "CLOSE":
        try:
            if trigger[0] == "CLOSE":
                coin = "BNB"
                stop = 0
            else:

                coin = trigger[1]
                stop = float(trigger[2])
            smart_trade(config, trigger[0], stop, coin)

        except IndexError:
            logger.info("--- Invalid trigger message format! ---\n\nMessage format "
                        "LONG/SELL "
                        "COIN "
                        "STOPLOSS "
                        "\n------------\n"
                        "Example\n"
                        "------------\n"
                        "LONG\n"
                        "BNB\n"
                        "2",
                        True,
                        )
            return
        except ValueError:
            logger.info("--- Invalid trigger message format! ---\n\nMessage format "
                        "LONG/SELL "
                        "COIN "
                        "STOPLOSS "
                        "\n------------\n"
                        "Example\n"
                        "------------\n"
                        "LONG\n"
                        "BNB\n"
                        "2",
                        True,
                        )
            return

        if trigger[0] not in ('LONG', 'SELL', 'CLOSE'):
            logger.debug(f"Trade type '{trigger[0]}' is not supported yet!")
            return
    else:
        logger.info("--- Not a crypto trigger message ---\n\nMessage format "
                    "LONG/SELL "
                    "COIN "
                    "STOPLOSS "
                    "\n------------\n"
                    "Example\n"
                    "------------\n"
                    "LONG\n"
                    "BNB\n"
                    "2",
                    True,
                    )

    notification.send_notification()


clients = Client()
# Start telegram client
client.start()
logger.info(
    "Listening to telegram chat '%s' for triggers"
    % config.get("telegram", "tgram-channel"),
    True,
)

client.run_until_disconnected()
