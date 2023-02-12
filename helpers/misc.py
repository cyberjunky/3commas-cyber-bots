"""Cyberjunky's 3Commas bot helpers."""
import datetime
import math
import time

from constants.pair import PAIREXCLUDE_EXT


def wait_time_interval(logger, notification, time_interval, notify=True):
    """Wait for time interval."""

    if time_interval > 0:
        localtime = time.time()
        nexttime = localtime + int(time_interval)
        timeresult = time.strftime("%H:%M:%S", time.localtime(nexttime))
        logger.info(
            "Next update in %s at %s" % (str(datetime.timedelta(seconds = time_interval)), timeresult), notify
        )
        notification.send_notification()
        time.sleep(time_interval)
        return True

    notification.send_notification()
    time.sleep(2)

    return False


def populate_pair_lists(pair, blacklist, blackpairs, badpairs, newpairs, tickerlist):
    """Create pair lists."""

    # Check if pair is in tickerlist and on 3Commas blacklist
    if pair in tickerlist:
        if pair in blacklist:
            blackpairs.append(pair)
        else:
            newpairs.append(pair)
    else:
        badpairs.append(pair)


def check_deal(cursor, dealid):
    """Check if deal was already logged."""

    return cursor.execute(f"SELECT * FROM deals WHERE dealid = {dealid}").fetchone()


def format_pair(marketcode, base, coin):
    """Format pair depending on exchange."""

    # Construct pair based on bot settings (BTC stays BTC, but USDT can become BUSD)
    if marketcode == "binance_futures":
        pair = f"{base}_{coin}{base}"
    elif marketcode == "ftx_futures":
        pair = f"{base}_{coin}-PERP"
    else:
        pair = f"{base}_{coin}"

    return pair


def get_round_digits(pair):
    """Get the number of digits for the round function."""

    numberofdigits = 4

    if pair:
        base = pair.split("_")[0]

        if base in ("BTC", "BNB", "ETH"):
            numberofdigits = 8

    return numberofdigits


def remove_prefix(text, prefix):
    """Get the string without prefix, required for Python < 3.9."""

    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def remove_excluded_pairs(logger, share_dir, bot_id, marketcode, base, newpairs):
    """Remove pairs which are excluded by other script(s)."""

    excludedcoins = load_bot_excluded_coins(logger, share_dir, bot_id, PAIREXCLUDE_EXT)
    if excludedcoins:
        logger.info(
            f"Removing the following coin(s) for bot {bot_id}: {base}/{excludedcoins}"
        )

        for coin in excludedcoins:
            # Construct pair based on bot settings and marketcode
            # (BTC stays BTC, but USDT can become BUSD)
            pair = format_pair(marketcode, base, coin)
            if newpairs.count(pair) > 0:
                newpairs.remove(pair)


def load_bot_excluded_coins(logger, share_dir, bot_id, extension):
    """Load excluded coins from file, for the specified bot"""

    excludedlist = []
    excludefilename = f"{share_dir}/{bot_id}.{extension}"

    try:
        with open(excludefilename, "r") as file:
            excludedlist = file.read().splitlines()
        if excludedlist:
            logger.info(
                "Reading exclude file '%s' OK (%s coins)"
                % (excludefilename, len(excludedlist))
            )
    except FileNotFoundError:
        logger.info(
            "Exclude file (%s) not found for bot '%s'; no coins to exclude."
            % (excludefilename, bot_id)
        )

    return excludedlist


def unix_timestamp_to_string(timestamp, date_time_format):
    """Convert the given timestamp to a readable date/time in the specified format"""

    return datetime.datetime.fromtimestamp(timestamp).strftime(date_time_format)


def calculate_deal_funds(start_bo, start_so, max_so, martingale_volume_coefficient, count_from = 1, count_funds_for = 1):
    """Calculate the max fund usage of a deal based on the bot settings"""

    # Always add start_base_order_size
    totalusedperdeal = start_bo

    # Funds required for the specified next number of SO
    nextsofunds = 0.0
    nextsofundscounter = 0

    isafetyorder = 1
    while isafetyorder <= max_so:
        # For the first Safety Order, just use the startso
        if isafetyorder == 1:
            total_safety_order_volume = start_so

        # After the first SO, multiply the previous SO with the safety order volume scale
        if isafetyorder > 1:
            total_safety_order_volume *= martingale_volume_coefficient

        # Only calculated the funds if current SO is higher than the `count_from`. This
        # could be used to calculate the funds for an already started deal with
        # completed Safety Orders.
        if isafetyorder >= count_from:
            totalusedperdeal += total_safety_order_volume

            if nextsofundscounter < count_funds_for:
                nextsofunds += total_safety_order_volume
                nextsofundscounter += 1

        isafetyorder += 1

    return totalusedperdeal, nextsofunds


def round_decimals_up(number:float, decimals:int = 2):
    """Returns a value rounded up to a specific number of decimal places."""

    if decimals == 0:
        return math.ceil(number)

    factor = 10 ** decimals
    return math.ceil(number * factor) / factor
