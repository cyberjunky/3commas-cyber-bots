#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import ssl
import sys
import time
import uuid
from pathlib import Path

from aiohttp import web

from helpers.logging import Logger, NotificationHandler
from helpers.misc import format_pair
from helpers.threecommas import (
    close_threecommas_deal,
    control_threecommas_bots,
    get_threecommas_account_marketcode,
    get_threecommas_deals,
    init_threecommas_api,
    load_blacklist,
    trigger_threecommas_bot_deal,
)


def load_config():
    """Create default or load existing config file."""

    cfg = configparser.ConfigParser(allow_no_value=True)
    if cfg.read(f"{datadir}/{program}.ini"):
        return cfg

    cfg["settings"] = {
        "timezone": "Europe/Amsterdam",
        "debug": False,
        "logrotate": 7,
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "3c-apiselfsigned": "Your own generated API key, or empty",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["webserver"] = {
        "baseurl": uuid.uuid4(),
        "port": 8090,
        "; Use ssl certificates when connected to the internet!": None,
        "ssl": False,
        "certfile": "Full path to your fullchain.pem",
        "privkey": "Full path to your privkey.pem",
    }

    cfg[f"webhook_{uuid.uuid4()}"] = {
        "control-botids": [12345, 67890],
        "usdt-botids": [],
        "btc-botids": [],
        "comment": "Just a description of this section",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "3c-apiselfsigned"):
        cfg.set("settings", "3c-apiselfsigned", "")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded the configuration file (3c-apiselfsigned)")

    return cfg


# Start application
program = Path(__file__).stem

# Parse and interpret options.
parser = argparse.ArgumentParser(description="Cyberjunky's 3Commas bot helper.")
parser.add_argument(
    "-d", "--datadir", help="directory to use for config and logs files", type=str
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
if args.blacklist:
    blacklistfile = args.blacklist
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


def webhook_deal(thebot, coin, trade):
    """Check pair and trigger the bot deal."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    exchange = thebot["account_name"]
    minvolume = thebot["min_volume_btc_24h"]

    logger.debug("Base coin for this bot: %s" % base)
    logger.debug("Minimal 24h volume in BTC for this bot: %s" % minvolume)

    # Get marketcode (exchange) from account
    marketcode = get_threecommas_account_marketcode(logger, api, thebot["account_id"])
    if not marketcode:
        return

    logger.info("Bot exchange: %s (%s)" % (exchange, marketcode))

    skipchecks = False
    if blacklistfile:
        skipchecks = True

    # Construct pair based on bot settings and marketcode (BTC stays BTC, but USDT can become BUSD)
    pair = format_pair(marketcode, base, coin)

    # Check if pair is on 3Commas blacklist
    if pair in blacklist:
        logger.debug(
            "This pair is on your 3Commas blacklist and was skipped: %s" % pair, True
        )
        return

    # Check if pair is in bot's pairlist
    if pair not in thebot["pairs"]:
        logger.debug(
            "This pair is not in bot's pairlist, and was skipped: %s" % pair,
            True,
        )
        return

    if trade == "buy":
        # We have valid pair for our bot so we trigger an open asap action
        logger.info("Triggering your 3Commas bot for buy")
        trigger_threecommas_bot_deal(logger, api, thebot, pair, skipchecks)
    else:
        # Find active deal(s) for this bot so we can close deal(s) for pair
        deals = get_threecommas_deals(logger, api, thebot["id"], "active")
        if deals:
            for deal in deals:
                if deal["pair"] == pair:
                    if close_threecommas_deal(logger, api, deal["id"], pair):
                        logger.info(
                            f"Closed deal (panic_sell) for deal '{deal['id']}' and pair '{pair}'",
                            True
                        )
                    return

            logger.info(
                "No active deal(s) found for bot '%s' and pair '%s'"
                % (thebot["name"], pair)
            )
        else:
            logger.info("No active deal(s) found for bot '%s'" % thebot["name"])


# Initialize 3Commas API
api = init_threecommas_api(config)
blacklist = load_blacklist(logger, api, blacklistfile)

# Webserver app
app = web.Application(logger=logger)

# Webserver settings
baseurl = config.get("webserver", "baseurl")
httpport = config.get("webserver", "port")
# SSL
sslenabled = config.getboolean("webserver", "ssl")
certfile = config.get("webserver", "certfile")
privkey = config.get("webserver", "privkey")

# Fetch configured hooks
tokens = list()
for section in config.sections():
    if section.startswith("webhook_"):
        # Add token to list
        tokens.append(section.replace("webhook_", ""))

# Process webhook calls
async def handle(request):
    """Handle web requests."""

    data = await request.json()
    logger.debug("Webhook alert received: %s" % data)

    token = data.get("token")
    if token in tokens:
        logger.debug("Webhook alert token acknowledged")

        # Get and verify actions
        actiontype = data.get("action").lower()

        # Bot actions
        if actiontype in ["enable", "disable"]:
            logger.debug(f"Webhook bot command received: {actiontype}")
            botids = json.loads(config.get(f"webhook_{token}", "control-botids"))

            # Walk through the configured bot(s)
            for botid in botids:
                error, data = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(botid),
                )
                if data:
                    logger.debug(f"Webhook '{actiontype}' bot with id '{botid}'")
                    control_threecommas_bots(logger, api, data, actiontype)
                else:
                    if error and "msg" in error:
                        logger.error("Error occurred updating bots: %s" % error["msg"])
                    else:
                        logger.error("Error occurred updating bots")

        # Deal actions
        elif actiontype in ["buy", "sell"]:
            logger.debug(f"Webhook deal command received: {actiontype}")

            pair = data.get("pair")
            base = pair.split("_")[0]
            coin = pair.split("_")[1]

            logger.debug("Pair: %s" % pair)
            logger.debug("Base: %s" % base)
            logger.debug("Coin: %s" % coin)
            logger.debug("Trade type: %s" % actiontype)

            if base == "USDT":
                botids = json.loads(config.get(f"webhook_{token}", "usdt-botids"))
                if len(botids) == 0:
                    logger.debug(
                        "No valid usdt-botids configured for '%s', cannot execute %s"
                        % (base, actiontype)
                    )
                    return web.Response()
            elif base == "BTC":
                botids = json.loads(config.get(f"webhook_{token}", "btc-botids"))
                if len(botids) == 0:
                    logger.debug(
                        "No valid btc-botids configured for '%s', cannot execute %s"
                        % (base, actiontype)
                    )
                    return
            else:
                logger.error("Error the base of pair '%s' is not supported yet!" % pair)
                return web.Response()

            for botid in botids:
                if botid == 0:
                    logger.debug("No valid botid configured, skipping")
                    continue

                error, data = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(botid),
                )
                if data:
                    logger.debug(f"Webhook '{actiontype}' bot with id '{botid}'")
                    webhook_deal(data, coin, actiontype)
                else:
                    if error and "msg" in error:
                        logger.error(
                            "Error occurred triggering bots: %s" % error["msg"]
                        )
                    else:
                        logger.error("Error occurred triggering bots")
        else:
            logger.error(
                f"Webhook alert received ignored, unsupported type '{actiontype}'"
            )

        return web.Response()

    logger.error("Webhook alert received denied, token '%s' invalid" % token)
    return web.Response(status=403)


# Prepare webhook webserver
app.router.add_post(f"/{baseurl}", handle)
logger.info(f"Starting webserver listening to '/{baseurl}'")

# https
if sslenabled:
    # Build ssl context
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain(certfile, privkey)

    web.run_app(
        app, host="0.0.0.0", port=httpport, ssl_context=context, access_log=None
    )

# http
web.run_app(app, host="0.0.0.0", port=httpport, access_log=None)
