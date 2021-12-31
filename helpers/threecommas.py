"""Cyberjunky's 3Commas bot helpers."""
from py3cw.request import Py3CW


def load_blacklist(logger, api, blacklistfile):
    """Return blacklist data to be used."""

    # Return file based blacklist
    if blacklistfile:
        newblacklist = []
        try:
            with open(blacklistfile, "r") as file:
                newblacklist = file.read().splitlines()
            if newblacklist:
                logger.info(
                    "Reading local blacklist file '%s' OK (%s pairs)"
                    % (blacklistfile, len(newblacklist))
                )
        except FileNotFoundError:
            logger.error(
                "Reading local blacklist file '%s' failed with error: File not found"
                % blacklistfile
            )

        return newblacklist

    # Return defined blacklist from 3Commaas
    return get_threecommas_blacklist(logger, api)


def init_threecommas_api(cfg):
    """Init the 3commas API."""
    return Py3CW(
        key=cfg.get("settings", "3c-apikey"),
        secret=cfg.get("settings", "3c-apisecret"),
        request_options={
            "request_timeout": 10,
            "nr_of_retries": 3,
            "retry_status_codes": [502],
        },
    )


def get_threecommas_blacklist(logger, api):
    """Get the pair blacklist from 3Commas."""

    newblacklist = list()
    error, data = api.request(
        entity="bots",
        action="pairs_black_list",
    )
    if data:
        logger.info(
            "Fetched 3Commas pairs blacklist OK (%s pairs)" % len(data["pairs"])
        )
        newblacklist = data["pairs"]
    else:
        if "msg" in error:
            logger.error(
                "Fetching 3Commas pairs blacklist failed with error: %s" % error["msg"]
            )
        else:
            logger.error("Fetching 3Commas pairs blacklist failed")

    return newblacklist


def get_threecommas_btcusd(logger, api):
    """Get current USDT_BTC value to calculate BTC volume24h in USDT."""

    price = 60000
    error, data = api.request(
        entity="accounts",
        action="currency_rates",
        payload={"market_code": "binance", "pair": "USDT_BTC"},
    )
    if data:
        logger.info("Fetched 3Commas BTC price OK (%s USDT)" % data["last"])
        price = data["last"]
    else:
        if error and "msg" in error:
            logger.error(
                "Fetching 3Commas BTC price in USDT failed with error: %s"
                % error["msg"]
            )
        else:
            logger.error("Fetching 3Commas BTC price in USDT failed")

    logger.debug("Current price of BTC is %s USDT" % price)
    return price


def get_threecommas_account(logger, api, accountid):
    """Get account details."""

    # Find account data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="",
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        for account in data:
            if account["id"] == accountid:
                marketcode = account["market_code"]
                logger.info(
                    "Fetched 3Commas account market code in real mode OK (%s)"
                    % marketcode
                )
                return marketcode

    # Didn't find the account data for accountid, retrying in paper mode
    error, data = api.request(
        entity="accounts", action="", additional_headers={"Forced-Mode": "paper"}
    )
    if data:
        for account in data:
            if account["id"] == accountid:
                marketcode = account["market_code"]
                logger.info(
                    "Fetched 3Commas account market code in paper mode OK (%s)"
                    % marketcode
                )
                return marketcode
    else:
        if error and "msg" in error:
            logger.error(
                f"Fetching 3Commas account data failed for id {accountid} error: %s"
                % error["msg"]
            )
        else:
            logger.error(f"Fetching 3Commas account data failed for id {accountid}")

    return None


def get_threecommas_market(logger, api, market_code):
    """Get all the valid pairs for market_code from 3Commas account."""

    tickerlist = []
    error, data = api.request(
        entity="accounts",
        action="market_pairs",
        payload={"market_code": market_code},
    )
    if data:
        tickerlist = data
        logger.info(
            "Fetched 3Commas market data for '%s' OK (%s pairs)"
            % (market_code, len(tickerlist))
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Fetching 3Commas market data failed with error: %s" % error["msg"]
            )
        else:
            logger.error("Fetching 3Commas market data failed")

    return tickerlist


def set_threecommas_bot_pairs(logger, api, thebot, newpairs):
    """Update bot with new pairs."""

    # Do we already use these pairs?
    if newpairs == thebot["pairs"]:
        logger.info(
            "Bot '%s' with id '%s' is already using the best pairs"
            % (thebot["name"], thebot["id"]),
            True,
        )
        return

    logger.debug("Current pairs: %s\nNew pairs: %s" % (thebot["pairs"], newpairs))

    error, data = api.request(
        entity="bots",
        action="update",
        action_id=str(thebot["id"]),
        payload={
            "name": str(thebot["name"]),
            "pairs": newpairs,
            "base_order_volume": float(thebot["base_order_volume"]),
            "take_profit": float(thebot["take_profit"]),
            "safety_order_volume": float(thebot["safety_order_volume"]),
            "martingale_volume_coefficient": float(
                thebot["martingale_volume_coefficient"]
            ),
            "martingale_step_coefficient": float(thebot["martingale_step_coefficient"]),
            "max_safety_orders": int(thebot["max_safety_orders"]),
            "max_active_deals": int(thebot["max_active_deals"]),
            "active_safety_orders_count": int(thebot["active_safety_orders_count"]),
            "safety_order_step_percentage": float(
                thebot["safety_order_step_percentage"]
            ),
            "take_profit_type": thebot["take_profit_type"],
            "strategy_list": thebot["strategy_list"],
            "leverage_type": thebot["leverage_type"],
            "leverage_custom_value": thebot["leverage_custom_value"],
            "bot_id": int(thebot["id"]),
        },
    )
    if data:
        logger.debug("Bot pairs updated: %s" % data)
        logger.info(
            "Bot '%s' with id '%s' updated with these pairs:\n%s"
            % (thebot["name"], thebot["id"], newpairs),
            True,
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred while updating bot '%s' error: %s"
                % (thebot["name"], error["msg"]),
                True,
            )
        else:
            logger.error(
                "Error occurred while updating bot '%s'" % thebot["name"],
                True,
            )


def trigger_threecommas_bot_deal(logger, api, thebot, pair, skip_checks=False):
    """Trigger bot to start deal asap for pair."""

    error, data = api.request(
        entity="bots",
        action="start_new_deal",
        action_id=str(thebot["id"]),
        payload={"pair": pair, "skip_signal_checks": skip_checks},
    )
    if data:
        logger.debug("Bot deal triggered: %s" % data)
        logger.info(
            "Bot '%s' with id '%s' triggered start_new_deal for: %s"
            % (thebot["name"], thebot["id"], pair),
            True,
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred while triggering start_new_deal bot '%s' error: %s"
                % (thebot["name"], error["msg"]),
            )
        else:
            logger.error(
                "Error occurred while triggering start_new_deal bot '%s'"
                % thebot["name"],
            )


def get_threecommas_deals(logger, api, botid):
    """Get all deals from 3Commas linked to a bot."""

    data = None
    error, data = api.request(
        entity="deals",
        action="",
        payload={
            "scope": "finished",
            "bot_id": str(botid),
            "limit": 100,
        },
    )
    if error:
        if "msg" in error:
            logger.error(
                "Error occurred while fetching deals error: %s"
                % error["msg"],
            )
        else:
            logger.error(
                "Error occurred while fetching deals")
    else:
        logger.info("Fetched the deals for bot OK (%s deals)" % len(data))
        return data
