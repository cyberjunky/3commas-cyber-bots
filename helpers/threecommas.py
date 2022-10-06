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
            "retry_status_codes": [502, 429],
            "retry_backoff_factor": 1,
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


def get_threecommas_accounts(logger, api):
    """Get all data for an account."""

    # Fetch all account data, in real mode
    error, data = api.request(
        entity="accounts",
        action="",
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        return data

    if error and "msg" in error:
        logger.error("Fetching 3Commas accounts data failed error: %s" % error["msg"])
    else:
        logger.error("Fetching 3Commas accounts data failed")

    return None


def get_threecommas_account(logger, api, accountid):
    """Get account details."""

    # Find account data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="account_info",
        action_id=str(accountid),
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        return data

    if error and "msg" in error:
        logger.error(
            "Fetching 3Commas account data failed for id %s error: %s"
            % (accountid, error["msg"])
        )
    else:
        logger.error("Fetching 3Commas account data failed for id %s", accountid)

    return None


def get_threecommas_account_marketcode(logger, api, accountid):
    """Get market_code for account."""

    # get account data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="account_info",
        action_id=str(accountid),
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        marketcode = data["market_code"]
        logger.info(
            "Fetched 3Commas account market code in real mode OK (%s)" % marketcode
        )
        return marketcode
    if error and "status_code" in error:
        if error["status_code"] == 404:
            logger.error(
                "Error occurred fetching 3Commas account market code: accountid '%s' was not found" % accountid
            )
    elif error and "msg" in error:
        logger.error(
            "Fetching 3Commas account market code failed for id '%s' error: %s"
            % (accountid, error["msg"])
        )
    else:
        logger.error("Fetching 3Commas account market code failed for id %s", accountid)

    return None


def get_threecommas_account_balance(logger, api, accountid):
    """Get account balances."""

    # Fetch account balance data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="load_balances",
        action_id=str(accountid),
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        return data

    if error and "msg" in error:
        logger.error(
            "Fetching 3Commas account balances data failed for id %s error: %s"
            % (accountid, error["msg"])
        )
    else:
        logger.error(
            "Fetching 3Commas account balances data failed for id %s", accountid
        )

    return None



def get_threecommas_account_table_balance(logger, api, accountid):
    """Get complete account balances."""

    # Fetch account balance data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="account_table_data",
        action_id=str(accountid),
        additional_headers={"Forced-Mode": "real"},
    )
    if data:
        return data

    if error and "msg" in error:
        logger.error(
            "Fetching 3Commas account table balances data failed for id %s error: %s"
            % (accountid, error["msg"])
        )
    else:
        logger.error(
            "Fetching 3Commas account table balances data failed for id %s", accountid
        )

    return None


def get_threecommas_account_balance_chart_data(
    logger, api, accountid, begindate, enddate
):
    """Get account balance chart data."""

    # Fetch account balance chart data for accountid, in real mode
    error, data = api.request(
        entity="accounts",
        action="balance_chart_data",
        action_id=str(accountid),
        additional_headers={"Forced-Mode": "real"},
        payload={"date_from": begindate, "date_to": enddate},
    )
    if data:
        return data

    if error and "msg" in error:
        logger.error(
            "Fetching 3Commas account balance chart data failed for id %s error: %s"
            % (accountid, error["msg"])
        )
    else:
        logger.error("Fetching 3Commas account balance chart data for id %s", accountid)

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
                "Fetching 3Commas market data failed for market code %s with error: %s"
                % (market_code, error["msg"])
            )
        else:
            logger.error(
                "Fetching 3Commas market data failed for market code %s", market_code
            )

    return tickerlist


def set_threecommas_bot_pairs(logger, api, thebot, newpairs, newmaxdeals, notify=True, notify_uptodate=True):
    """Update bot with new pairs."""

    # Do we already use these pairs?
    if newpairs == thebot["pairs"]:
        logger.info(
            "Bot '%s' with id '%s' is already using the new pair(s)"
            % (thebot["name"], thebot["id"]),
            notify_uptodate,
        )
        return

    if not newmaxdeals:
        maxactivedeals = thebot["max_active_deals"]
    else:
        maxactivedeals = newmaxdeals

    logger.debug("Current pair(s): %s\nNew pair(s): %s" % (thebot["pairs"], newpairs))

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
            "max_active_deals": int(maxactivedeals),
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
        logger.debug("Bot pair(s) updated: %s" % data)
        if len(newpairs) == 1:
            logger.info(
                "Bot '%s' with id '%s' updated with pair '%s'"
                % (thebot["name"], thebot["id"], newpairs[0]),
                notify,
            )
        else:
            if len(newpairs) < 10:
                logger.info(
                "Bot '%s' with id '%s' updated with %d pairs (%s)"
                % (
                    thebot["name"],
                    thebot["id"],
                    len(newpairs),
                    newpairs,
                ),
                notify,
            )
            else:
                logger.info(
                    "Bot '%s' with id '%s' updated with %d pairs (%s ... %s)"
                    % (
                        thebot["name"],
                        thebot["id"],
                        len(newpairs),
                        newpairs[0],
                        newpairs[-1],
                    ),
                    notify,
                )
        if newmaxdeals:
            logger.info(
                "Max active deals changed to %s" % newmaxdeals,
                notify,
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
    """Trigger bot to start deal asap."""

    error, data = api.request(
        entity="bots",
        action="start_new_deal",
        action_id=str(thebot["id"]),
        payload={"pair": pair, "skip_signal_checks": skip_checks, "bot_id": thebot["id"]},
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


def control_threecommas_bots(logger, api, thebot, cmd):
    """Enable or disable a bot."""

    error, data = api.request(
        entity="bots",
        action=cmd,
        action_id=str(thebot["id"]),
    )
    if data:
        logger.debug(f"Bot {cmd}: {data}")
        logger.info(
            "Bot '%s' is %sd" % (thebot["name"], cmd),
            True,
        )
    else:
        if error and "msg" in error:
            logger.error(
                "Error occurred while '%s' bot was %sd error: %s"
                % (thebot["name"], cmd, error["msg"]),
            )
        else:
            logger.error(
                "Error occurred while '%s' bot was %sd" % (thebot["name"], cmd),
            )


def get_threecommas_deals(logger, api, botid, actiontype="finished"):
    """Get all deals from 3Commas linked to a bot."""

    data = None
    if actiontype == "finished":
        payload = {
            "scope": "finished",
            "bot_id": str(botid),
            "limit": 100,
            "order": "closed_at",
        }
    else:
        payload = {
            "scope": "active",
            "bot_id": str(botid),
            "limit": 100,
        }

    error, data = api.request(
        entity="deals",
        action="",
        payload=payload,
    )
    if error:
        if "msg" in error:
            logger.error(
                "Error occurred while fetching deals error: %s" % error["msg"],
            )
        else:
            logger.error("Error occurred while fetching deals")
    else:
        logger.debug("Fetched the deals for bot %s OK (%s deals)" % (botid, len(data)))

    return data


def close_threecommas_deal(logger, api, dealid, pair):
    """Close deal with certain id."""

    data = None
    error, data = api.request(
        entity="deals",
        action="panic_sell",
        action_id=str(dealid),
    )
    if error:
        if "msg" in error:
            logger.error(
                "Error occurred while closing deal error: %s" % error["msg"],
            )
        else:
            logger.error("Error occurred while closing deal")
    else:
        logger.info(
            "Closed deal (panic_sell) for deal with id '%s' and pair '%s'"
            % (dealid, pair),
            True,
        )

    return data


def get_threecommas_bots(logger, api, accountid):
    """Get account details."""

    # Find bots data for accountid
    error, data = api.request(
        entity="bots",
        action="",
        payload= {
            "account_id": accountid
        }
    )

    if data:
        return data

    if error and "msg" in error:
        logger.error(
            "Fetching 3Commas bots data failed for id %s error: %s"
            % (accountid, error["msg"])
        )
    # No else, there are just no bots for the account

    return None


def smart_trades(cfg, logger, api, pair, posvalue, stoploss, accountid, notify=True, notify_uptodate=True):
    """Get all data for an account."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload={
            "account_id": accountid,
            "pair": pair,
            "position": {
                "type": "buy",
                "units": {
                    "value": posvalue
                },
                "order_type": "market"
            },
            "take_profit": {
                "enabled": "false"
            },
            "stop_loss": {
                "enabled": "true",
                "order_type": "market",
                "conditional": {
                    "price": {
                        "value": stoploss,
                        "type": "bid"
                    }
                }
            }
        }
    )
    if data:
        logger.info(
            "Opening a deal for '%s' successes "
            % pair,
            notify
        )

    elif error and "msg" in error:
        logger.error(f"Opening a deal for :  failed error: %s" % error["msg"], notify)

    return None


def update_smart_trades(cfg, logger, api, accountid, notify=True, notify_uptodate=True):
    """Get all data for an account."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="",
        payload={
            "account_id": accountid})
    if data:
        print(data)

    elif error and "msg" in error:
        logger.error(f"Opening a deal for :  failed error: %s" % error["msg"], notify)

    return None


def smart_spot_trades(cfg, logger, api, pair, posvalue, accountid, stoploss, tp1, tp2, tp3, tp4, tp5, notify=True,
                      notify_uptodate=True):
    """Get all data for an account."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload={
            "account_id": accountid,
            "pair": pair,
            "position": {
                "type": "buy",
                "units": {
                    "value": posvalue
                },
                "order_type": "market"
            },
            "take_profit": {
                "enabled": "true",
                "steps": [
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp1,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol1"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp2,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol2"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp3,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol3"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp4,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol4"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp5,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol5"))
                    }
                ]
            },
            "stop_loss": {
                "enabled": "true",
                "breakeven": "true",
                "order_type": "market",
                "conditional": {
                    "price": {
                        "value": stoploss,
                        "type": "bid"
                    }
                }
            }
        }
    )
    if data:
        logger.info(
            f"\ndeal for pair {pair}\nposition size: {round(posvalue, 2)}\n "
            f"successfully opened from Smart Trade account : {accountid}",
            True
        )

    elif error:
        if "msg" in error:
            logger.error(f"Order has Invalid parameters\n{error['msg']}",
                         True
                         )
        else:
            logger.error("UNKNOWN ERROR")
    return None


def smart_lev_trades(cfg, logger, api, pair, posvalue, lev, accountid, side, stoploss, tp1, tp2, tp3, tp4, tp5,
                     true=True,
                     notify=True,
                     notify_uptodate=True):
    """Smart Trade with lev."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload={
            "account_id": accountid,
            "pair": pair,
            "position": {
                "type": side,
                "units": {
                    "value": posvalue
                },
                "order_type": "market"
            },
            "take_profit": {
                "enabled": "true",
                "steps": [
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp1,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol1"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp2,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol2"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp3,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol3"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp4,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol4"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp5,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol5"))
                    }
                ]
            },
            "leverage": {
                "enabled": true,
                "type": "cross",
                "value": lev,
            },
            "stop_loss": {
                "enabled": "true",
                "breakeven": "true",
                "order_type": "market",
                "conditional": {
                    "price": {
                        "value": stoploss,
                        "type": "bid"
                    }
                }
            }
        }
    )
    if data:
        logger.info(
            f"\ndeal for pair {pair} \n, position size: {round(posvalue, 2)} \n "
            f"successfully opened from Smart Trade account : {accountid}",
            True
        )
    elif error:
        if "msg" in error:
            logger.error(f"Order has Invalid parameters\n{error['msg']}",
                         True
                         )
        else:
            logger.error("UNKNOWN ERROR")
    return None


#
def get_active_smart_trades(cfg, logger, api):
    dealsid = []
    """Get all data for an account."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="",
        payload={

            "status": "active"
        }
    )
    if data:
        for deal in data:
            dealsid.append(deal["id"])
    elif error:
        logger.error("NO Active Deals",
                     True,
                     )
    else:
        logger.error("NO Active Deals",
                     True,
                     )
    return dealsid


def panic_close_smart(cfg, logger, api, deals):
    for deal in deals:
        error, data = api.request(
            entity="smart_trades_v2",
            action="close_by_market",
            action_id=str(deal),
        )
        if data:
            logger.info(f"Deal : {deal} has been closed",
                        True,
                        )
        elif error:
            logger.error(f"NO Active Deals or any other errors f{error}",
                         True,
                         )
        else:
            logger.error(f"NO Active Deals or any other errors f{error}",
                         True,
                         )


# lev Smart Trades with RR strategy


def smart_lev_trades_risk_reward(cfg, logger, api, pair, posvalue, lev, accountid, side, stoploss, tp1, tp2, price,
                                 true=True,
                                 notify=True,
                                 notify_uptodate=True):
    """Smart Trade with lev."""
    # Fetch all account data, in real mode
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload={
            "account_id": accountid,
            "pair": pair,
            "position": {
                "type": side,
                "units": {
                    "value": posvalue
                },
                "price": {
                    "value": price
                },
                "order_type": "limit"
            },
            "take_profit": {
                "enabled": "true",
                "steps": [
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp1,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol1"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp2,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol2"))
                    },
                ]
            },
            "leverage": {
                "enabled": true,
                "type": "cross",
                "value": lev,
            },
            "stop_loss": {
                "enabled": "true",
                "breakeven": "true",
                "order_type": "market",
                "conditional": {
                    "price": {
                        "value": stoploss,
                        "type": "bid"
                    }
                }
            }
        }
    )
    if data:
        logger.info(
            f"\ndeal for pair {pair} \n, position size: {round(posvalue, 2)} \n "
            f"successfully opened from Smart Trade account : {accountid}",
            True
        )
    elif error:
        if "msg" in error:
            logger.error(f"Order has Invalid parameters\n{error['msg']}",
                         True
                         )
        else:
            logger.error("UNKNOWN ERROR")
    return None


# SPOT Smart trade with RR strategy


def smart_spot_trades_risk_reward(cfg, logger, api, pair, posvalue, accountid, stoploss, tp1, tp2, price,
                                  notify=True,
                                  notify_uptodate=True):
    """Get all data for an account."""
    # Fetch all account data, in real mode
    print(f"price from {price}")
    error, data = api.request(
        entity="smart_trades_v2",
        action="new",
        payload={
            "account_id": accountid,
            "pair": pair,
            "position": {
                "type": "buy",
                "units": {
                    "value": posvalue
                },
                "price": {
                    "value": price
                },
                "order_type": "limit"
            },
            "take_profit": {
                "enabled": "true",
                "steps": [
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp1,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol1"))
                    },
                    {
                        "order_type": "limit",
                        "price": {
                            "value": tp2,
                            "type": "bid"
                        },
                        "volume": float(cfg.get("settings", "vol2"))
                    },
                ]
            },
            "stop_loss": {
                "enabled": "true",
                "breakeven": cfg.get("settings", "break_even"),
                "order_type": "market",
                "conditional": {
                    "price": {
                        "value": stoploss,
                        "type": "bid"
                    }
                }
            }
        }
    )
    if data:
        logger.info(
            f"\ndeal for pair {pair}\nposition size: {round(posvalue, 2)}\n "
            f"successfully opened from Smart Trade account : {accountid}",
            True
        )

    elif error:
        if "msg" in error:
            logger.error(f"Order has Invalid parameters\n{error['msg']}",
                         True
                         )
        else:
            logger.error("UNKNOWN ERROR")
    return None

