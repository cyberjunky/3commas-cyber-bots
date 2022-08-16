"""Cyberjunky's 3Commas bot helpers."""

from math import isnan


def is_valid_smarttrade(logger, price, entries, targets, stoploss):
    """Validate smarttrade data"""

    isvalid = True

    if not isnan(stoploss) and stoploss >= price:
        logger.warning(f"Current price {price} equal or below stoploss {stoploss}!")
        isvalid = False

    if not len(targets):
        logger.warning(f"No targets set!")
        isvalid = False

    return isvalid


def construct_smarttrade_position(position_type, order_type, value):
    """Create the position content for a smarttrade"""

    position = {
        "type": position_type,
        "order_type": order_type,
        "units": {
            "value": value
        },
    }

    return position


def construct_smarttrade_takeprofit(enabled, order_type, step_list):
    """Create the take_profit content for a smarttrade"""

    steps = []
    for stepentry in step_list:
        step = {
            "order_type": order_type,
            "price": {
                "value": float(stepentry["price"]),
                "type": "bid"
            },
            "volume": float(stepentry["volume"])
        }
        steps.append(step)

    take_profit = {
        "enabled": enabled,
        "steps": steps,
    }

    return take_profit


def construct_smarttrade_stoploss(order_type, price):
    """Create the stop_loss content for a smarttrade"""

    stop_loss = {
        "enabled": False
    }

    if not isnan(price):
        stop_loss = {
            "enabled": True,
            "order_type": order_type,
            "price": {
                "value": float(price)
            },
            "conditional": {
                "price": {
                    "value": float(price),
                    "type":"bid",
                },
            },
        }

    return stop_loss
