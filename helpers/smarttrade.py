"""Cyberjunky's 3Commas bot helpers."""

from math import isnan


def is_valid_smarttrade(logger, price, entries, targets, stoploss, direction):
    """Validate smarttrade data"""

    isvalid = True

    if not isnan(stoploss):
        if direction == "long" and price <= stoploss:
            logger.warning(f"Current price {price} for long equal or below stoploss {stoploss}!")
            isvalid = False
        elif direction == "short" and price >= stoploss:
            logger.warning(f"Current price {price} for short equal or above stoploss {stoploss}!")
            isvalid = False

    if not targets:
        logger.warning("No targets set!")
        isvalid = False

    return isvalid


def get_smarttrade_direction(targets):
    """Identify the direction of the smarttrade (long or short)"""

    direction = ""

    if len(targets) > 1:
        firsttp = float(targets[0]["price"])
        lasttp = float(targets[len(targets) - 1]["price"])

        if firsttp < lasttp:
            direction = "long"
        else:
            direction = "short"

    return direction


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


def construct_smarttrade_takeprofit(order_type, step_list):
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
        "enabled": True,
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
