"""Cyberjunky's 3Commas bot helpers."""

from math import nan


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
                "value": stepentry["price"],
                "type": "bid"
            },
            "volume": stepentry["volume"]
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
        "enabled": True if price != nan else False,
        "order_type": order_type,
        "price": {
            "value": price
        },
        "conditional": {
            "price": {
                "value": price,
                "type":"bid",
            },
        },
    }

    return stop_loss
