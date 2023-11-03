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
from constants.pair import PAIREXCLUDE_EXT

from helpers.logging import (
    Logger,
    NotificationHandler
)
from helpers.misc import (
    check_deal,
    remove_excluded_pairs,
    wait_time_interval
)
from helpers.threecommas import (
    get_threecommas_account_marketcode,
    init_threecommas_api,
    init_threecommas_websocket,
    prefetch_marketcodes,
    set_threecommas_bot_pairs
)


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
        "3c-apikey-path": "Path to your own generated RSA private key, or empty",
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


def upgrade_config(cfg):
    """Upgrade config file if needed."""

    if not cfg.has_option("settings", "3c-apikey-path"):
        cfg.set("settings", "3c-apikey-path", "")

        with open(f"{datadir}/{program}.ini", "w+") as cfgfile:
            cfg.write(cfgfile)

        logger.info("Upgraded the configuration file (3c-apikey-path)")

    return cfg


def init_cluster_db():
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
            "CREATE TABLE IF NOT EXISTS deals ("
            "dealid INT Primary Key, "
            "coin STRING, "
            "clusterid STRING, "
            "botid INT, "
            "active BIT"
            ")"
        )

        dbcursor.execute(
            "CREATE TABLE IF NOT EXISTS cluster_coins ("
            "clusterid STRING, "
            "coin STRING, "
            "number_active INT, "
            "PRIMARY KEY(clusterid, coin)"
            ")"
        )

        logger.info("Database tables created successfully")

    return dbconnection


def init_thread_db():
    """Open connection with database for usage in thread"""

    dbname = f"{program}.sqlite3"
    dbpath = f"file:{datadir}/{dbname}?mode=rw"
    dbconnection = sqlite3.connect(dbpath, uri=True)
    dbconnection.row_factory = sqlite3.Row

    return dbconnection


def upgrade_cluster_db():
    """Upgrade database if needed."""

    try:
        try:
            # DROP column supported from sqlite 3.35.0 (2021.03.12)
            cursor.execute("ALTER TABLE deals DROP COLUMN pair")
        except sqlite3.OperationalError:
            logger.debug("Older SQLite version; not used columns not removed")

        cursor.execute("ALTER TABLE deals ADD COLUMN coin STRING")

        cursor.execute("DROP TABLE cluster_pairs")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS cluster_coins ("
            "clusterid STRING, "
            "coin STRING, "
            "number_active INT, "
            "PRIMARY KEY(clusterid, coin)"
            ")"
        )

        cursor.execute("DROP TABLE bot_pairs")

        logger.info("Database schema upgraded (pair to coins)")
    except sqlite3.OperationalError:
        logger.debug("Database schema is up-to-date")


def add_cluster_deal(db_connection, deal_data, cluster_id):
    """Add a new deal within the cluster"""

    deal_id = deal_data["id"]

    existing_deal = check_deal(db_connection.cursor(), deal_id)

    if not existing_deal:
        coin = deal_data['pair'].split("_")[1]

        db_connection.execute(
            f"INSERT INTO deals (dealid, coin, clusterid, botid, active) "
            f"VALUES ({deal_id}, '{coin}', '{cluster_id}', {deal_data['bot_id']}, {1})"
        )
        # db.commit() on higher level

        logger.info(
            f"New deal found {deal_id}/{deal_data['pair']} on bot \"{deal_data['bot_name']}",
            True
        )
    else:
        logger.debug(
            f"Deal {deal_id} already registered and still active"
        )


def process_bot_deals(cluster_id, bot_data):
    """Check deals from bot and update deals in db."""

    bot_id = bot_data["id"]

    # Process current deals and deals which have been closed since the last processing time
    current_deals = []
    if bot_data["active_deals"]:
        for dealdata in bot_data["active_deals"]:
            current_deals.append(dealdata["id"])
            add_cluster_deal(db, dealdata, cluster_id)

        # Remove all other deals as not active anymore.
        if current_deals:
            # Remove start and end square bracket so we can properly use it
            current_deals_str = str(current_deals)[1:-1]

            logger.debug(f"Delete finished deals from {bot_id} except {current_deals_str}")

            db.execute(
                f"DELETE FROM deals "
                f"WHERE botid = {bot_id} AND dealid NOT IN ({current_deals_str})"
            )

    # No deals for this bot anymore, so remove them all (if any left)
    if not current_deals:
        logger.debug(f"No deals active for {bot_id}")
        db.execute(
            f"DELETE FROM deals "
            f"WHERE botid = {bot_id}"
        )

    # Commit the added and removed deals to the db
    db.commit()


def aggregrate_cluster(db_connection, cluster_id, bot_list):
    """Aggregate deals within cluster."""

    logger.debug(f"Cleaning and aggregating data for '{cluster_id}'")

    # Get the current cluster data and pair numbers
    oldclusterdata = [c[0] for c in db_connection.execute(
        f"SELECT coin FROM cluster_coins "
        f"WHERE clusterid = '{cluster_id}' AND "
        f"number_active >= {int(config.get(cluster_id, 'max-same-deals'))} "
        f"ORDER BY coin ASC"
    ).fetchall()]

    # Remove current data
    db_connection.execute(
        f"DELETE from cluster_coins WHERE clusterid = '{cluster_id}'"
    )

    # Create the cluster data, how many of the same coins are active within the
    # cluster based on the active deals
    db_connection.execute(
        f"INSERT INTO cluster_coins (clusterid, coin, number_active) "
        f"SELECT clusterid, coin, "
        f"SUM ( CASE WHEN active = {1} THEN 1 ELSE 0 END) AS number_active "
        f"FROM deals "
        f"WHERE clusterid = '{cluster_id}' "
        f"GROUP BY coin"
    )

    db_connection.commit()

    # Get the new cluster data and pair numbers
    newclusterdata = [c[0] for c in db_connection.execute(
        f"SELECT coin FROM cluster_coins "
        f"WHERE clusterid = '{cluster_id}' AND "
        f"number_active >= {int(config.get(cluster_id, 'max-same-deals'))} "
        f"ORDER BY coin ASC"
    ).fetchall()]

    log_cluster_changes(cluster_id, oldclusterdata, newclusterdata)

    # Write the exclude file for the coins, to be used for updating bot
    # pairs (this, and other, scripts)
    write_cluster_exclude_files(bot_list, newclusterdata)


def log_cluster_changes(cluster_id, old_data, new_data):
    """Log the changes in the cluster"""

    logger.debug(
        f"Old cluster data: {old_data}. New cluster data: {new_data}"
    )

    # Check which coins have gone from the data (will be enabled)
    enabledcoins = [x for x in old_data if x not in new_data]

    if enabledcoins:
        logger.info(
            f"Enabling coin(s) {enabledcoins} for cluster: {cluster_id}",
            True
        )

    # Check which coins are new in the data (will be disabled)
    disabledcoins = [x for x in new_data if x not in old_data]

    if disabledcoins:
        logger.info(
            f"Disabling coin(s) {disabledcoins} for cluster: {cluster_id}",
            True
        )


def write_cluster_exclude_files(bot_list, disabled_coins):
    """Write exclude files for each bot in the specified cluster"""

    for botid in bot_list:
        write_bot_exclude_file(botid, disabled_coins)


def write_bot_exclude_file(bot_id, coins):
    """Write the exclude file for the specified bot"""

    excludefilename = f"{sharedir}/{bot_id}.{PAIREXCLUDE_EXT}"

    logger.debug(
        f"Writing coins {coins} to file {excludefilename}"
    )

    with open(excludefilename, 'w') as filehandle:
        for coin in coins:
            filehandle.write('%s\n' % coin)


def websocket_update(deal_data):
    """Handle the received deal data from the websocket"""

    # Indicator if the cluster should be aggregrated again. Updates over the websocket
    # also contain filled SO's which don't have impact on the cluster
    aggregrate = False
    clusterid = ""

    threaddb = init_thread_db()
    existingdeal = check_deal(threaddb.cursor(), deal_data["id"])

    if existingdeal and deal_data["finished?"]:
        # Deal is finished, remove it from the db
        threaddb.execute(
            f"DELETE FROM deals "
            f"WHERE botid = {deal_data['bot_id']} AND dealid = {deal_data['id']}"
        )
        threaddb.commit()

        logger.info(
            f"Deal {deal_data['id']}/{deal_data['pair']} on "
            f"bot \"{deal_data['bot_name']} finished!",
            True
        )

        # Finished deal, get the cluster the bot belongs to
        clusterid = get_bot_cluster(deal_data["bot_id"])

        aggregrate = True
    else:
        if not existingdeal:
            # New deal, check if the bot is part of any cluster
            clusterid = get_bot_cluster(deal_data["bot_id"])

            if clusterid:
                add_cluster_deal(threaddb, deal_data, clusterid)

                threaddb.commit()

                aggregrate = True
            #else:
                # Here we could inform the user about opened deals outside any cluster
        #else:
            # Here we could inform the user about deal updates (filled SO, trailing activated)

    if aggregrate:
        if clusterid:
            # Get Bot list
            botlist = json.loads(config.get(clusterid, "botids"))
            aggregrate_cluster(threaddb, clusterid, botlist)
            process_cluster_bots(clusterid, botlist, "update")
        else:
            logger.error(
                f"Deal {deal_data['id']}/{deal_data['pair']} needs "
                f"to be aggregated but cluster is unknown!"
            )

    # Send notifications, if there are any
    notification.send_notification()


def process_cluster_bots(cluster_id, bot_list, action):
    """Update the bots in the cluster with the enabled/disabled pairs"""

    for bot in bot_list:
        boterror, botdata = api.request(
            entity="bots",
            action="show",
            action_id=str(bot),
        )
        if botdata:
            if action == "deals":
                process_bot_deals(cluster_id, botdata)
            elif action == "update":
                update_bot_config(botdata)
            else:
                logger.error(
                    f"Cannot handle unknown action '{action}'!"
                )
        else:
            if boterror and "msg" in boterror:
                logger.error("Error occurred updating bots: %s" % boterror["msg"])
            else:
                logger.error("Error occurred updating bots")


def get_bot_cluster(bot_id):
    """Find the cluster the bot belongs to"""

    clusterid = ""

    for sectionid in config.sections():
        if sectionid.startswith("cluster_"):
            # Bot configuration for section
            botlist = json.loads(config.get(sectionid, "botids"))

            if bot_id in botlist:
                # Cluster (section) found
                clusterid = sectionid
                break

    return clusterid


def update_bot_config(bot_data):
    """Update bots at 3C"""

    marketcode = marketcodecache.get(bot_data["id"])
    if not marketcode:
        marketcode = get_threecommas_account_marketcode(logger, api, bot_data["account_id"])
        marketcodecache[bot_data["id"]] = marketcode

        logger.info(
            f"Marketcode for bot {bot_data['id']} was not cached. Cache updated "
            f"with marketcode {marketcode}."
        )

    # If sharedir is set, other scripts could provide a file with pairs to exclude
    if marketcode:
        newpairs = bot_data["pairs"].copy()
        botbase = newpairs[0].split("_")[0]

        logger.debug(
            f"Pairs before excluding: {newpairs}"
        )
        remove_excluded_pairs(logger, sharedir, bot_data["id"], marketcode, botbase, newpairs)
        logger.debug(
            f"Pairs after excluding: {newpairs}"
        )

        set_threecommas_bot_pairs(logger, api, bot_data, newpairs, False, True, False)
    else:
        logger.error(
            f"Marketcode not found for bot {bot_data['id']}. Cannot update pairs!"
        )


def create_marketcode_cache():
    """Create the cache met MarketCode per bot"""

    allbotids = []

    logger.info("Prefetching marketcodes for all configured bots...")

    for initialsection in config.sections():
        if initialsection.startswith("cluster_"):
            allbotids += json.loads(config.get(initialsection, "botids"))

    return prefetch_marketcodes(logger, api, allbotids)


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
    print("This script requires the sharedir to be used (-s option)!")
    sys.exit(0)

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

# Initialize or open the database
db = init_cluster_db()
cursor = db.cursor()

# Upgrade the database if needed
upgrade_cluster_db()

# Prefetch all Marketcodes to reduce API calls and improve speed
# New bot(s) will also be added later, for example when the configuration
# has been changed after starting this script
marketcodecache = create_marketcode_cache()

# Initialize 3Commas WebSocket connection
websocket = init_threecommas_websocket(logger, config, websocket_update)
if not websocket:
    sys.exit(0)
websocket.start_listener(seperate_thread = True)

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

            # Walk through all bots configured and check deals
            process_cluster_bots(section, botids, "deals")

            # Aggregrate data on cluster level. Will also take care of writing .pairexclude file
            aggregrate_cluster(db, section, botids)

            # Update the bots in this cluster with the enabled/disabled pairs
            process_cluster_bots(section, botids, "update")

            # Send notifications for the processed cluster, otherwise the message can
            # become too long resulting in a bad request in apprise
            notification.send_notification()
        elif section not in ("settings"):
            logger.warning(
                f"Section '{section}' not processed (prefix 'cluster_' missing)!",
                False
            )

    if not wait_time_interval(logger, notification, timeint, False):
        break
