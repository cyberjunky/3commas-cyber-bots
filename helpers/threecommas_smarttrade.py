"""Cyberjunky's 3Commas bot helpers."""

def open_threecommas_smarttrade(logger, api, accountid, pair, note, position, take_profit, stop_loss):
    """Open smarttrade with the given position, profit and stoploss."""

    payload = {
        "account_id": accountid,
        "pair": pair,
        "note": note,
        "leverage": {
            "enabled": "false",
        },
        "position": position,
        "take_profit": take_profit,
        "stop_loss": stop_loss
    }

    logger.debug(
        f"Sending new on smart_trades_v2 for pair {pair}: {payload}"
    )

    data = None
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload=payload,
        additional_headers={"Forced-Mode": "paper"},
    )

    if error:
        if "msg" in error:
            logger.error(
                f"Error occurred while opening smarttrade: {error['msg']}",
            )
        else:
            logger.error("Error occurred while opening smarttrade")

    return data


def close_threecommas_smarttrade(logger, api, smarttradeid):
    """Close smarttrade with the given id."""

    logger.debug(
        f"Closing smarttrades {smarttradeid}"
    )

    data = None
    error, data = api.request(
        entity="smart_trades_v2",
        action="close_by_market",
        action_id=str(smarttradeid),
        additional_headers={"Forced-Mode": "paper"},
    )

    if error:
        if "msg" in error:
            logger.error(
                f"Error occurred while closing smarttrade: {error['msg']}",
            )
        else:
            logger.error("Error occurred while closing smarttrade")
    else:
        logger.info(
            f"Closed smarttrade '{smarttradeid}'.",
            True
        )

    return data


def get_threecommas_smarttrades(logger, api, accountid, actiontype="finished"):
    """Get all trades from 3Commas linked to an account."""

    data = None
    if actiontype == "finished":
        payload = {
            "status": "finished",
            "account_id": str(accountid),
            "limit": 100,
            "per_page": 100,
            "order": "closed_at",
        }
    else:
        payload = {
            "status": "active",
            "account_id": str(accountid),
            "limit": 100,
            "per_page": 100
        }

    error, data = api.request(
        entity="smart_trades_v2",
        action="",
        payload=payload,
    )
    if error:
        if "msg" in error:
            logger.error(
                f"Error occurred while fetching smarttrades: {error['msg']}"
            )
        else:
            logger.error("Error occurred while fetching smarttrades")
    else:
        logger.debug(
            f"Fetched the smarttrades for account {accountid} OK ({len(data)} trades)"
        )

    return data