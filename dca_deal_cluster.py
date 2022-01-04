#!/usr/bin/env python3
"""Cyberjunky's 3Commas bot helpers."""
import argparse
import configparser
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from helpers.logging import Logger, NotificationHandler
from helpers.misc import check_deal, wait_time_interval
from helpers.threecommas import init_threecommas_api


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
        "3c-apikey": "Your 3Commas API Key",
        "3c-apisecret": "Your 3Commas API Secret",
        "notifications": False,
        "notify-urls": ["notify-url1"],
    }

    cfg["cluster_default"] = {
        "botids": [12345, 67890],
        "max-same-deals": "1",
    }

    with open(f"{datadir}/{program}.ini", "w") as cfgfile:
        cfg.write(cfgfile)

    return None


def upgrade_config(thelogger, cfg):
    """Upgrade config file if needed."""

    return cfg


def init_coin_db():
    """Create or open database to store cluster and coin data."""
    try:
        dbname = f"{program}.sqlite3"
        dbpath = f"file:{datadir}/{dbname}?mode=rw"
        dbconnection = sqlite3.connect(dbpath, uri=True)
        dbconnection.row_factory = sqlite3.Row

        logger.info(f"Database '{datadir}/{dbname}' opened successfully")

    except sqlite3.OperationalError:
        dbconnection = sqlite3.connect(f"{datadir}/{dbname}")
        dbconnection.row_factory = sqlite3.Row
        dbcursor = dbconnection.cursor()
        logger.info(f"Database '{datadir}/{dbname}' created successfully")

        dbcursor.execute(
            "CREATE TABLE deals (dealid INT Primary Key, pair STRING, clusterid STRING, botid INT, active BIT)"
        )

        dbcursor.execute(
            "CREATE TABLE cluster_pairs (clusterid STRING, pair STRING, number_active INT, PRIMARY KEY(clusterid, pair))"
        )

        dbcursor.execute(
            "CREATE TABLE bot_pairs (botid INT, pair STRING, enabled BIT, PRIMARY KEY(botid, pair))"
        )

        logger.info("Database tables created successfully")

    return dbconnection


def clean_bot_db_data(thebot):
    """Cleanup old bot data in the db."""

    bot_id = thebot["id"]

    logger.info(f"Cleaning previous data for bot {bot_id}")
    db.execute(
        f"DELETE FROM deals WHERE botid = {bot_id} AND active = {0}"
    )
    db.execute(
        f"DELETE FROM bot_pairs WHERE botid = {bot_id} and enabled = {1}"
    )

    db.commit()


def process_bot_deals(cluster_id, thebot):
    """Check deals from bot and update deals in db."""

    deals = thebot["active_deals"]

    if deals:
        bot_id = thebot["id"]

        # Process current deals and deals which have been closed after the last processing time
        current_deals = ""
        for deal in deals:
            deal_id = deal["id"]

            if current_deals:
                current_deals += ","
            current_deals += str(deal_id)

            existing_deal = check_deal(cursor, deal_id)
            if not existing_deal:
                deal_pair = deal['pair']

                db.execute(
                    f"INSERT INTO deals (dealid, pair, clusterid, botid, active) "
                    f"VALUES ({deal_id}, '{deal_pair}', '{cluster_id}', {bot_id}, {1})"
                )
                logger.info(
                    f"New deal found {deal_id}/{deal['pair']} on bot \"{thebot['name']}"
                )
            else:
                logger.info(
                    f"Deal {deal_id} already registered and still active"
                )

        # Mark all other deals as not active anymore. Required later in the process and will be cleaned
        # during next processing round
        if current_deals:
            logger.info(f"Mark all deals from {bot_id} as inactive except {current_deals}")
            db.execute(
                f"UPDATE deals SET active = {0} WHERE botid = {bot_id} AND dealid NOT IN ({current_deals})"
            )
        
        # Save all pairs used by the bot currently
        botpairs = thebot["pairs"]
        if botpairs:
            logger.info(
                f"Saving {len(botpairs)} pairs for bot {bot_id}"
            )

            for pair in botpairs:
                db.execute(
                    f"INSERT OR IGNORE INTO bot_pairs (botid, pair, enabled) VALUES ({bot_id}, '{pair}', {1})"
                )

        db.commit()

    dealsdata = cursor.execute(f"SELECT dealid, pair, clusterid, botid, active FROM deals WHERE clusterid = '{cluster_id}'").fetchall()
    if dealsdata:
        logger.info(f"Printing deals for cluster '{cluster_id}':")
        for entry in dealsdata:
            logger.info(
                f"{entry[0]}: {entry[1]} ({entry[4]})"
            )
    else:
        logger.info(
            f"No deals data for cluster '{cluster_id}'"
        )


def aggregrate_cluster(cluster_id):
    """Aggregate deals within cluster."""

    logger.info(f"Cleaning and aggregating data for cluster '{cluster_id}'")

    db.execute(
        f"DELETE from cluster_pairs WHERE clusterid = '{cluster_id}'"
    )

    db.execute(
        f"INSERT INTO cluster_pairs (clusterid, pair, number_active) "
        f"SELECT clusterid, pair, COUNT(pair) FROM deals "
        f"WHERE clusterid = '{cluster_id}' GROUP BY pair"
    )

    clusterdata = cursor.execute(f"SELECT clusterid, pair, number_active FROM cluster_pairs WHERE clusterid = '{cluster_id}'").fetchall()
    if clusterdata:
        logger.info(f"Printing cluster_pairs for cluster '{cluster_id}':")
        for entry in clusterdata:
            logger.info(
                f"{entry[1]}: {entry[2]}"
            )
    else:
        logger.info(
            f"No cluster_pair data for cluster '{cluster_id}'"
        )


def process_cluster_deals(cluster_id):
    """Process deals within cluster and update bots."""

    clusterdata = db.execute(f"SELECT clusterid, pair, number_active FROM cluster_pairs WHERE clusterid = '{cluster_id}'")
    if clusterdata and clusterdata.rowcount > 0:
        logger.info(f"Processing cluster_pairs for cluster '{cluster_id}':")
        for entry in clusterdata:
            pair = entry[1]
            numberofdeals = int(entry[2])

            logger.info(
                f"Pair {pair} has {numberofdeals} deals active"
            )

            #if numberofdeals >= int(cfg.get(cluster_id, "max-same-deals")):
                # Found a pair which should be suspended
            #else:
                # Found a pair which can be activated again
    else:
        logger.info(
            f"No cluster_pair data for cluster '{cluster_id}'"
        )


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
    config = upgrade_config(logger, config)

    logger.info(f"Loaded configuration from '{datadir}/{program}.ini'")

# Initialize 3Commas API
api = init_threecommas_api(config)

# Initialize or open the database
db = init_coin_db()
cursor = db.cursor()

# DCA Deal Cluster
while True:

    # Reload config files and refetch data to catch changes
    config = load_config()
    logger.info(f"Reloaded configuration from '{datadir}/{program}.ini'")

    # Configuration settings
    timeint = int(config.get("settings", "timeinterval"))

    for section in config.sections():
        if section.startswith("cluster_"):
            # Bot configuration for section
            botids = json.loads(config.get(section, "botids"))

            # Walk through all bots configured
            for bot in botids:
                boterror, botdata = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(bot),
                )
                if botdata:
                    clean_bot_db_data(botdata)
                    process_bot_deals(section, botdata)
                else:
                    if boterror and "msg" in boterror:
                        logger.error("Error occurred updating bots: %s" % boterror["msg"])
                    else:
                        logger.error("Error occurred updating bots")
            
            # Aggregate deals to cluster level
            aggregrate_cluster(section)

            # Update the bots in this cluster


    if not wait_time_interval(logger, notification, timeint):
        break
