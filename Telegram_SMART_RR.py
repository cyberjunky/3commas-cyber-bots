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
    smart_lev_trades_risk_reward,
    smart_spot_trades_risk_reward,
    panic_close_smart,
    get_active_smart_trades,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser()
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Africa/Cairo",
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "accounts": 0000000,
        "risk-per-trade": 50,
        "risk_reward-1": 1.0,
        "risk_reward-2": 2.4,
        "vol1": 2.0,
        "vol2": 98,
        "break_even": True,
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


def smart_trade(cfg, side, pair, price, inputstoploss):
    accounts = (cfg.get("settings", "accounts")).split(",")
    risk = float(cfg.get("settings", "risk-per-trade"))
    lev = int(cfg.get("settings", "leverage"))
    rr1 = float(cfg.get("settings", "risk_reward-1"))
    rr2 = float(cfg.get("settings", "risk_reward-2"))
    side = side
    inputstoploss = inputstoploss
    coin = pair
    try:
        check_price = clients.get_symbol_ticker(symbol=binance_pair(pair))["price"]
        pair_price = price
        print(pair_price)
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
            tp1 = float(pair_price) - ((float(stoploss) - float(pair_price)) * rr1)
            tp2 = float(pair_price) - ((float(stoploss) - float(pair_price)) * rr2)

        else:
            types = "buy"
            if stop:
                stoploss = 0
            else:
                stoploss = float(pair_price) - (float(pair_price) * (inputstoploss / 100))
            tp1 = float(pair_price) - ((float(stoploss) - float(pair_price)) * rr1)
            tp2 = float(pair_price) - ((float(stoploss) - float(pair_price)) * rr2)

        for account in accounts:
            market_code = get_threecommas_account_marketcode(logger, api, account)
            capital = float(get_threecommas_account_balance(logger, api, account)["usd_amount"])
            if stop:
                capital_per_trade = risk * 10
            else:
                capital_per_trade = risk / inputstoploss * 100

            if market_code == "binance_futures":
                posvalue = capital_per_trade / float(pair_price) / lev
                pair = futures_pair(coin)
                smart_lev_trades_risk_reward(config, logger, api, pair, posvalue, lev, account, types, stoploss, tp1,
                                             tp2, pair_price)
            elif market_code == "binance_futures_coin":
                continue
            else:
                # no SHORT for SPOT
                if types == "sell":
                    logger.error("Selling SPOT is not available ")
                    continue

                else:
                    posvalue = capital_per_trade / float(pair_price)
                    pair = spot_pair(coin)
                    smart_spot_trades_risk_reward(config, logger, api, pair, posvalue, account, stoploss,
                                                  tp1, tp2, pair_price)


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Zcrypto Smart-Trade telegram.")
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
            "settings", "timezone", fallback="Africa/Cairo"
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
                price = 0
                stop = 0
            else:

                coin = trigger[1]
                price = float(trigger[2])
                stop = float(trigger[3])
            smart_trade(config, trigger[0], coin, price, stop)

        except IndexError:
            logger.info("--- Invalid trigger message format! ---\n\nMessage format "
                        "LONG/SELL\n"
                        "COIN\n"
                        "PRICE\n"
                        "STOPLOSS\n"
                        "\n------------\n"
                        "Example\n"
                        "------------\n"
                        "LONG\n"
                        "BNB\n"
                        "250\n"
                        "2",
                        True,
                        )
            return
        except ValueError:
            logger.info("--- Invalid trigger message format! ---\n\nMessage format "
                        "LONG/SELL\n"
                        "COIN\n"
                        "PRICE\n"
                        "STOPLOSS\n"
                        "\n------------\n"
                        "Example\n"
                        "------------\n"
                        "LONG\n"
                        "BNB\n"
                        "250\n"
                        "2",
                        True,
                        )
            return

        if trigger[0] not in ('LONG', 'SELL', 'CLOSE'):
            logger.debug(f"Trade type '{trigger[0]}' is not supported yet!")
            return
    else:
        logger.info("--- Not a crypto trigger message ---\n\nMessage format "
                    "LONG/SELL\n"
                    "COIN\n"
                    "PRICE\n"
                    "STOPLOSS "
                    "\n------------\n"
                    "Example\n"
                    "------------\n"
                    "LONG\n"
                    "BNB\n"
                    "250\n"
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
