"""Cyberjunky's 3Commas bot helpers."""

from helpers.misc import format_pair
from helpers.threecommas import(
    close_threecommas_deal,
    get_threecommas_account_marketcode,
    trigger_threecommas_bot_deal
)


def prefetch_marketcodes(logger, api, botids):
    """Gather and return marketcodes for all bots."""

    marketcodearray = {}

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


def process_botlist(logger, api, blacklistfile, blacklist, marketcodes, botidlist, coin, trade):
    """Process the list of bots and handle the coin and trade for each bot"""

    for botid in botidlist:
        if botid:
            error, data = api.request(
                entity="bots",
                action="show",
                action_id=str(botid),
            )

            if data:
                # Check number of deals, otherwise error will occur anyway (save some processing)
                if data["active_deals_count"] >= data["max_active_deals"]:
                    logger.info(
                        f"Bot '{data['name']}' reached maximum number of "
                        f"deals ({data['max_active_deals']}). "
                        f"Cannot start a new deal for {coin}!",
                        True
                    )
                else:
                    process_bot_deal(logger, api, blacklistfile, blacklist,
                        marketcodes, data, coin, trade)
            else:
                if error and "msg" in error:
                    logger.error(
                        "Error occurred fetching bot (%s) data: %s" % (str(botid), error["msg"])
                    )
                else:
                    logger.error(
                        "Error occurred fetching bot (%s) data" % str(botid)
                    )


def process_bot_deal(logger, api, blacklistfile, blacklist, marketcodes, thebot, coin, trade):
    """Check pair and trigger open or close the deal."""

    # Gather some bot values
    base = thebot["pairs"][0].split("_")[0]
    bot_exchange = thebot["account_name"]
    minvolume = thebot["min_volume_btc_24h"]
    alloweddealsonsamepair = thebot["allowed_deals_on_same_pair"]

    logger.debug("Base coin for this bot: %s" % base)
    logger.debug("Minimal 24h volume of %s BTC" % minvolume)
    logger.debug("Allowed same deals for pair: %s" % alloweddealsonsamepair)

    # Get marketcode from array
    marketcode = marketcodes.get(thebot["id"])
    if not marketcode:
        return
    logger.info("Bot: %s" % thebot["name"])
    logger.info("Exchange %s (%s) used" % (bot_exchange, marketcode))

    # Construct pair based on bot settings and marketcode (BTC stays BTC, but USDT can become BUSD)
    pair = format_pair(marketcode, base, coin)

    deals = thebot["active_deals"]
    if trade == "LONG":
        # Check active deal(s) for this bot
        dealcount = 0
        if deals:
            for deal in deals:
                if deal["pair"] == pair:
                    dealcount += 1

        if dealcount >= alloweddealsonsamepair:
            logger.debug("Open deals for %s reached max allowed open deals for same pair!" % pair)
            return

        # Check if pair is on 3Commas blacklist
        if pair in blacklist:
            logger.debug(
                f"Pair '{pair}' is on your 3Commas blacklist and was skipped",
                True
            )
            return

        # Check if pair is in bot's pairlist
        if pair not in thebot["pairs"]:
            logger.info(
                f"Pair '{pair}' is not in '{thebot['name']}' pairlist and was skipped",
                True
            )
            return

        # We have valid pair for our bot so we trigger an open asap action
        logger.info("Triggering your 3Commas bot for a start deal of '%s'" % pair)
        trigger_threecommas_bot_deal(logger, api, thebot, pair, (len(blacklistfile) > 0))
    else:
        # Find active deal(s) for this bot so we can close deal(s) for pair
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
