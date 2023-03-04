"""Cyberjunky's 3Commas bot helpers."""

import decimal
from helpers.misc import round_decimals_up


def determine_profit_prefix(deal_data):
    """Determine the prefix of the profit for logging"""

    if deal_data["strategy"] == "long":
        return "-"

    return ""


def get_profit_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_profit WHERE dealid = {dealid}").fetchone()


def get_safety_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_safety WHERE dealid = {dealid}").fetchone()


def get_pending_order_db_data(cursor, dealid):
    """Check if order for deal was logged and get stored data."""

    return cursor.execute(f"SELECT * FROM pending_orders WHERE dealid = {dealid}").fetchone()


def check_float(potential_float):
    """Check if the passed argument is a valid float"""

    try:
        float(potential_float)
        return True
    except ValueError:
        return False


def is_new_deal(cursor, dealid):
    """Return True if the deal is not know yet, otherwise False"""

    if cursor.execute(f"SELECT * FROM deal_profit WHERE dealid = {dealid}").fetchone():
        return False

    return True


def calculate_slpercentage_base_price_short(sl_price, base_price):
    """Calculate the SL percentage of the base price for a short deal"""

    return round(
        ((sl_price / base_price) * 100.0) - 100.0,
        2
    )


def calculate_slpercentage_base_price_long(sl_price, base_price):
    """Calculate the SL percentage of the base price for a long deal"""

    return round(
        100.0 - ((sl_price / base_price) * 100.0),
        2
    )


def calculate_average_price_sl_percentage_short(sl_price, average_price):
    """Calculate the SL percentage based on the average price for a short deal"""

    return round(
        100.0 - ((sl_price / average_price) * 100.0),
        2
    )


def calculate_average_price_sl_percentage_long(sl_price, average_price):
    """Calculate the SL percentage based on the average price for a long deal"""

    return round(
        ((sl_price / average_price) * 100.0) - 100.0,
        2
    )


def calculate_sl_percentage(logger, deal_data, config, activation_diff):
    """Calculate the SL percentage in 3C and TP range"""

    currentslpercentage = (
        float(deal_data["stop_loss_percentage"]) if deal_data["stop_loss_percentage"] else 0.0
    )
    initialstoplosspercentage = float(config.get("initial-stoploss-percentage"))
    slincrementfactor = float(config.get("sl-increment-factor"))

    # If there is no SL configured for this config, return default values
    if initialstoplosspercentage == 0.0:
        return currentslpercentage, 0.0, 0.0, 0.0

    # SL is calculated by 3C on base order price. Because of filled SO's,
    # we must first calculate the SL price based on the average price
    averageprice = 0.0
    if deal_data["strategy"] == "short":
        averageprice = float(deal_data["sold_average_price"])
    else:
        averageprice = float(deal_data["bought_average_price"])

    # Calculate the amount we need to substract or add to the average price based
    # on the configured increments and activation
    percentageprice = averageprice * ((initialstoplosspercentage / 100.0)
                                        + ((activation_diff / 100.0) * slincrementfactor))

    slprice = averageprice
    if deal_data["strategy"] == "short":
        slprice -= percentageprice
    else:
        slprice += percentageprice

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: SL price {slprice} calculated based on average "
        f"price {averageprice}, initial SL of {initialstoplosspercentage}, "
        f"activation diff of {activation_diff} and sl factor {slincrementfactor}"
    )

    # Now we know the SL price, let's calculate the percentage from
    # the base order price so we have the desired SL for 3C
    baseprice = float(deal_data["base_order_average_price"])
    basepriceslpercentage = 0.0
    # And also the readable percentage for the user (on the TP axis)
    understandableslpercentage = 0.0

    if deal_data["strategy"] == "short":
        basepriceslpercentage = calculate_slpercentage_base_price_short(
                slprice, baseprice
            )
        understandableslpercentage = calculate_average_price_sl_percentage_short(
                slprice, averageprice
            )
    else:
        basepriceslpercentage = calculate_slpercentage_base_price_long(
                slprice, baseprice
            )
        understandableslpercentage = calculate_average_price_sl_percentage_long(
                slprice, averageprice
            )

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: "
        f"3C SL of {basepriceslpercentage}% calculated (which is "
        f"{understandableslpercentage}% for understandig) based "
        f"on base price {baseprice} and SL price {slprice}."
    )

    return currentslpercentage, basepriceslpercentage, understandableslpercentage


def calculate_tp_percentage(logger, deal_data, config, activation_diff, last_profit_percentage):
    """Calculate the TP percentage TP range"""

    # Closing strategy means 3C will monitor the condition and manage the TP
    if len(deal_data["close_strategy_list"]) > 0:
        minprofitpercentage = float(deal_data["min_profit_percentage"])
        logger.info(
            f"Deal data: {deal_data}. "
        )
        return minprofitpercentage, minprofitpercentage

    tpincrementfactor = float(config.get("tp-increment-factor"))

    currenttppercentage = float(deal_data["take_profit"])
    if tpincrementfactor <= 0.0:
        # TP will not be changed, so return immediatly
        return currenttppercentage, currenttppercentage

    newtppercentage = currenttppercentage
    if last_profit_percentage > 0.0:
        newtppercentage = round(
            currenttppercentage + (
                (float(deal_data["actual_profit_percentage"]) - last_profit_percentage)
                * tpincrementfactor
            ), 2
        )
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: "
            f"Updated TP to {newtppercentage}% calculated based on current profit of "
            f"{currenttppercentage}%, new profit of {deal_data['actual_profit_percentage']}%, "
            f"last profit of {last_profit_percentage}% and factor {tpincrementfactor}."
        )
    else:
        newtppercentage = round(
            currenttppercentage + (activation_diff * tpincrementfactor), 2
        )

        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: "
            f"Initial TP of {newtppercentage}% calculated based on last profit of "
            f"{last_profit_percentage}% and current {currenttppercentage}%, "
            f"using activation_diff {activation_diff}% and factor {tpincrementfactor}."
        )

    return currenttppercentage, newtppercentage


# # TODO: optimize and improve readability of this function
def calculate_safety_order(logger, bot_data, deal_data, filled_so_count, current_profit):
    """Calculate the next safety order."""

    # Number of SO to buy
    sobuycount = 0

    # Volume to buy
    sobuyvolume = 0.0

    # Price to buy the volume on
    sobuyprice = 0.0

    # Percentage for next SO to monitor the deal on
    sonextdroppercentage = 0.0

    # Default values for calculationloop below
    sovolume = totalvolume = 0.0
    sopercentagedropfrombaseprice = totaldroppercentage = 0.0
    sobuyprice = 0.0

    socounter = 0
    while socounter < deal_data['max_safety_orders']:
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: "
            f"at SO {socounter}/{deal_data['max_safety_orders']}, "
            f"Volume: {sovolume}/{totalvolume}, "
            f"Drop: {sopercentagedropfrombaseprice}/{totaldroppercentage}, "
            f"Price: {sobuyprice}."
        )

        nextsovolume = 0.0
        nextsopercentagedropfrombaseprice = 0.0

        # First SO takes the default values, following SO are multiplied with the configured factors
        if socounter == 0:
            nextsovolume = float(bot_data["safety_order_volume"])
            nextsopercentagedropfrombaseprice = float(bot_data["safety_order_step_percentage"])
        else:
            nextsovolume = float(sovolume) * float(bot_data["martingale_volume_coefficient"])
            nextsopercentagedropfrombaseprice = (
                float(sopercentagedropfrombaseprice) *
                float(bot_data["martingale_step_coefficient"])
            )

        nextsototalvolume = totalvolume + nextsovolume
        nextsopercentagetotaldrop = totaldroppercentage + nextsopercentagedropfrombaseprice
        nextsobuyprice = (
            float(deal_data["base_order_average_price"]) *
            ((100.0 - nextsopercentagetotaldrop) / 100.0)
        )

        # Print data for next SO
        logger.debug(
            f"{deal_data['pair']}/{deal_data['id']}: calculated next SO {socounter + 1}, "
            f"Volume: {nextsovolume}/{nextsototalvolume}, "
            f"Drop: {nextsopercentagedropfrombaseprice}/{nextsopercentagetotaldrop}, "
            f"Price: {nextsobuyprice}"
        )

        # Descision making :)
        if socounter < filled_so_count:
            logger.debug(f"SO {socounter} already filled!")

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            totaldroppercentage = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice
        elif nextsopercentagetotaldrop <= current_profit:
            logger.debug(
                f"{deal_data['pair']}/{deal_data['id']}: next SO {socounter + 1} "
                f"not filled and required based on (negative) profit."
            )

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            totaldroppercentage = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice

            sobuycount += 1
            sobuyvolume += nextsovolume
        elif nextsopercentagetotaldrop > current_profit:
            logger.debug(
                f"{deal_data['pair']}/{deal_data['id']}: next SO {socounter + 1} "
                f"not filled and not required! Stop at SO {socounter}"
            )

            sonextdroppercentage = nextsopercentagetotaldrop
            break

        socounter += 1

    logger.info(
        f"{deal_data['pair']}/{deal_data['id']}: SO level {socounter} reached. "
        f"Need to buy {sobuycount} - {sobuyvolume}/{sobuyprice}! "
        f"Next SO at {sonextdroppercentage}."
    )

    return sobuycount, sobuyvolume, sobuyprice, totaldroppercentage, sonextdroppercentage


def determine_price_quantity(logger, bot_data, deal_data, limit_data, calc_price, calc_quantity):
    """Determine the correct price and quantity for the Add Funds order"""

    limitprice = calc_price
    quantity = calc_quantity

    if deal_data["strategy"] == "long" and calc_price > float(deal_data["current_price"]):
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"current price {deal_data['current_price']} lower than "
            f"calculated price {calc_price}, so using the current price."
        )
        limitprice = float(deal_data["current_price"])
    elif deal_data["strategy"] == "short" and calc_price < float(deal_data["current_price"]):
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"current price {deal_data['current_price']} higher than "
            f"calculated price {calc_price}, so using the current price."
        )
        limitprice = float(deal_data["current_price"])

    if deal_data["safety_order_volume_type"] == "quote_currency":
        quantity = calc_quantity / limitprice
        logger.debug(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"calculated quantity {quantity} based on "
            f"volume {calc_quantity} and price {limitprice}."
        )
    else:
        logger.info(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"using quantity {quantity} based on 'base_currency' volume "
            f"order type."
        )

    limitvalue = limit_data["limits"]["lotStep"].split(".")

    decimals = 0
    if int(limitvalue[1]) > 0:
        decimals = len(limitvalue[1])
    quantity = round_decimals_up(quantity, decimals)

    logger.debug(
        f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
        f"changed quantity to {quantity} based on "
        f"lotStep {limit_data['limits']['lotStep']} and value {limitvalue}."
    )

    return limitprice, quantity


def validate_add_funds_data(logger, bot_data, deal_data, limit_data, quantity):
    """Validate the Add Funds data against the limits"""

    valid = True

    #TODO: below is only debugging. Incorperate when it's clear how this works
    if ("marketBuyMinTotal" in limit_data["limits"] and
        quantity <= float(limit_data["limits"]["marketBuyMinTotal"]) > quantity
    ):
        valid = False

        logger.error(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"buy amount of {quantity} lower than "
            f"{limit_data['limits']['marketBuyMinTotal']}!"
        )

    if ("maxMarketBuyAmount" in limit_data["limits"] and
        quantity >= float(limit_data["limits"]["maxMarketBuyAmount"])
    ):
        valid = False

        logger.error(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"buy amount of {quantity} higher than "
            f"{limit_data['limits']['maxMarketBuyAmount']}!"
        )

    # Modulo executed with Decimal and string to prevent rounding and
    # floating point issues.
    sizemodulo = decimal.Decimal(
        str(quantity - float(limit_data["limits"]["minLotSize"]))
    ) % decimal.Decimal(str(limit_data["limits"]["lotStep"]))

    if sizemodulo != 0.0:
        valid = False

        logger.error(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']}: "
            f"quantity {quantity} not a multiply of stepsize "
            f"{limit_data['limits']['lotStep']}, taking min size of "
            f"{limit_data['limits']['minLotSize']} into account! Remaining "
            f"is {sizemodulo}"
        )

    return valid


def is_valid_deal(logger, bot_data, deal_data):
    """Validate the deal and determine if we can process it"""

    valid = True

    if deal_data['active_safety_orders_count'] != 0:
        logger.warning(
            f"\"{bot_data['name']}\": {deal_data['pair']}/{deal_data['id']} "
            f"has active Safety Orders by bot configuration which will break the "
            f"functionality of this script. Not processing this deal!"
        )
        valid = False

    return valid
