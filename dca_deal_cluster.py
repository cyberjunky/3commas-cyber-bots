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
from helpers.threecommas import init_threecommas_api, set_threecommas_bot_pairs


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

    thelogger.info("Config does not require any upgrade at this moment")

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
            "CREATE TABLE deals (dealid INT Primary Key, pair STRING, clusterid STRING, "
            "botid INT, active BIT)"
        )

        dbcursor.execute(
            "CREATE TABLE cluster_pairs (clusterid STRING, pair STRING, number_active INT, "
            "PRIMARY KEY(clusterid, pair))"
        )

        dbcursor.execute(
            "CREATE TABLE bot_pairs (clusterid STRING, botid INT, botname STRING, pair STRING, enabled BIT, "
            "PRIMARY KEY(clusterid, botid, pair))"
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

    bot_id = thebot["id"]

    # Process current deals and deals which have been closed since the last processing time
    current_deals = ""
    deals = thebot["active_deals"]
    if deals:
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
                    f"New deal found {deal_id}/{deal['pair']} on bot \"{thebot['name']}",
                    True
                )
            else:
                logger.info(
                    f"Deal {deal_id} already registered and still active"
                )

        # Mark all other deals as not active anymore. Required later in the process and
        # will be cleaned during next processing round
        if current_deals:
            logger.info(f"Mark all deals from {bot_id} as inactive except {current_deals}")
            db.execute(
                f"UPDATE deals SET active = {0} "
                f"WHERE botid = {bot_id} AND dealid NOT IN ({current_deals})"
            )

    # No deals for this bot anymore, so mark them all (if any) as inactive
    if not current_deals:
        logger.info(f"Mark all deals from {bot_id} as inactive")
        db.execute(
            f"UPDATE deals SET active = {0} "
            f"WHERE botid = {bot_id}"
        )

    # Save all pairs used by the bot currently. Make sure not to overwrite disabled pairs
    botpairs = thebot["pairs"]
    if botpairs:
        botname = thebot["name"]

        logger.info(
            f"Saving {len(botpairs)} pairs for bot {botname} ({bot_id})"
        )

        for pair in botpairs:
            db.execute(
                f"INSERT OR IGNORE INTO bot_pairs (clusterid, botid, botname, pair, enabled) "
                f"VALUES ('{cluster_id}', {bot_id},'{botname}', '{pair}', {1})"
            )

    db.commit()


def log_deals(cluster_id):
    """Log the deals within this cluster"""
    dealdata = cursor.execute(
        f"SELECT dealid, pair, botid, active FROM deals "
        f"WHERE clusterid = '{cluster_id}'"
    ).fetchall()

    if dealdata:
        logger.info(f"Printing deals for cluster '{cluster_id}':")
        for entry in dealdata:
            logger.info(
                f"{entry[0]}: {entry[1]}, {entry[2]} => {entry[3]}"
            )
    else:
        logger.info(
            f"No deals data for cluster '{cluster_id}'"
        )


def aggregrate_cluster(cluster_id):
    """Aggregate deals within cluster."""

    logger.info(f"Cleaning and aggregating data for cluster '{cluster_id}'")

    # Remove old data
    db.execute(
        f"DELETE from cluster_pairs WHERE clusterid = '{cluster_id}'"
    )

    # Create the cluster data, how many of the same pairs are active within the
    # cluster based on the active deals
    db.execute(
        f"INSERT INTO cluster_pairs (clusterid, pair, number_active) "
        f"SELECT clusterid, pair, "
        f"SUM ( CASE WHEN active = {1} THEN 1 ELSE 0 END) AS number_active "
        f"FROM deals "
        f"WHERE clusterid = '{cluster_id}' "
        f"GROUP BY pair"
    )

    db.commit()


def log_cluster_data(cluster_id):
    """Log the aggregated data based on the deals for this cluster"""

    clusterdata = cursor.execute(
        f"SELECT clusterid, pair, number_active FROM cluster_pairs "
        f"WHERE clusterid = '{cluster_id}'"
    ).fetchall()

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
    """Process deals within cluster."""

    # Get the cluster data and pair numbers
    clusterdata = db.execute(
        f"SELECT clusterid, pair, number_active FROM cluster_pairs "
        f"WHERE clusterid = '{cluster_id}'"
    ).fetchall()

    if clusterdata:
        logger.info(f"Processing cluster_pairs for cluster '{cluster_id}':")

        enablepairs = ""
        disablepairs = ""

        for entry in clusterdata:
            pair = entry[1]
            numberofdeals = int(entry[2])

            logger.info(
                f"Pair {pair} has {numberofdeals} deal(s) active"
            )

            if numberofdeals >= int(config.get(cluster_id, "max-same-deals")):
                # Found a pair which should be suspended
                if disablepairs:
                    disablepairs += "\',\'"
                disablepairs += str(pair)

                log_disable_enable_pair(cluster_id, pair, 0)
            else:
                # Found a pair which can be activated again
                if enablepairs:
                    enablepairs += "\',\'"
                enablepairs += str(pair)

                log_disable_enable_pair(cluster_id, pair, 1)

        # Enable the found pairs (caused by finished deals)
        if enablepairs:
            logger.info(
                f"Enabling pairs for cluster {cluster_id}: {enablepairs}"
            )
            db.execute(
                f"UPDATE bot_pairs SET enabled = {1} "
                f"WHERE clusterid = '{cluster_id}' AND pair IN ('{enablepairs}')"
            )

        # Disable the found pairs (caused by new deals)
        if disablepairs:
            logger.info(
                f"Disabling pairs for cluster {cluster_id}: {disablepairs}"
            )
            db.execute(
                f"UPDATE bot_pairs SET enabled = {0} "
                f"WHERE clusterid = '{cluster_id}' AND pair IN ('{disablepairs}')"
            )

        db.commit()
    else:
        logger.info(
            f"No cluster_pair data for cluster '{cluster_id}'"
        )


def log_disable_enable_pair(cluster_id, pair, new_enabled_value):
    """Log the pairs which will be enabled or disabled"""

    pairdata = cursor.execute(
        f"SELECT botid, botname, pair, enabled FROM bot_pairs "
        f"WHERE clusterid = '{cluster_id}' AND pair = '{pair}'"
    ).fetchall()

    if pairdata:
        changedbots = ""

        for entry in pairdata:
            if entry[3] != new_enabled_value:
                if changedbots:
                    changedbots += ","
                changedbots += str(entry[1]) + " (" + str(entry[0]) + ")"

        if changedbots:
            if new_enabled_value:
                logger.info(
                    f"Enabling pair {pair} for the following bot(s): {changedbots}",
                    True
                )
            else:
                logger.info(
                    f"Disabling pair {pair} for the following bot(s): {changedbots}",
                    True
                )


def update_bot_pairs(cluster_id, thebot):
    """Update bots."""

    bot_id = thebot["id"]

    # Here rowid is used which is not defined in the init() function. Rowid
    # is a default column in SQLite when using an INT as primary key
    botpairs = cursor.execute(
        f"SELECT pair FROM bot_pairs "
        f"WHERE clusterid = '{cluster_id}' AND botid = {bot_id} AND enabled = {1} "
        f"ORDER BY rowid ASC"
    ).fetchall()

    if botpairs:
        pairlist = [row[0] for row in botpairs]
        set_threecommas_bot_pairs(logger, api, thebot, pairlist, False)
    else:
        logger.warning(
            f"Failed to get bot pairs for bot {bot_id}"
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
    debug = config.getboolean("settings", "debug")

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
                        logger.error("Error occurred reading bots: %s" % boterror["msg"])
                    else:
                        logger.error("Error occurred reading bots")

            # Aggregate deals to cluster level
            if debug:
                log_deals(section)

            aggregrate_cluster(section)

            if debug:
                log_cluster_data(section)

            # Enable and disable pairs
            process_cluster_deals(section)

            # Update the bots in this cluster with the enabled/disabled pairs
            for bot in botids:
                boterror, botdata = api.request(
                    entity="bots",
                    action="show",
                    action_id=str(bot),
                )
                if botdata:
                    update_bot_pairs(section, botdata)
                else:
                    if boterror and "msg" in boterror:
                        logger.error("Error occurred updating bots: %s" % boterror["msg"])
                    else:
                        logger.error("Error occurred updating bots")

    if not wait_time_interval(logger, notification, timeint, False):
        break
