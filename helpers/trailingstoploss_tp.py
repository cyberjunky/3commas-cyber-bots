"""Cyberjunky's 3Commas bot helpers."""


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


def calculate_sl_percentage(logger, deal_data, profit_config, activation_diff):
    """Calculate the SL percentage in 3C and TP range"""

    currentslpercentage = float(deal_data["stop_loss_percentage"])
    initialstoplosspercentage = float(profit_config.get("initial-stoploss-percentage"))
    slincrementfactor = float(profit_config.get("sl-increment-factor"))

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


def calculate_tp_percentage(logger, deal_data, profit_config, activation_diff, last_profit_percentage):
    """Calculate the TP percentage TP range"""

    tpincrementfactor = float(profit_config.get("tp-increment-factor"))

    currenttppercentage = float(deal_data["take_profit"])
    if tpincrementfactor <= 0.0:
        # TP will not be changed, so return immediatly
        return currenttppercentage

    newtppercentage = currenttppercentage
    if last_profit_percentage > 0.0:
        newtppercentage = round(
            currenttppercentage + (
                (float(deal_data["actual_profit_percentage"]) - last_profit_percentage)
                * tpincrementfactor
            ), 2
        )
    else:
        newtppercentage = round(
            currenttppercentage + (activation_diff * tpincrementfactor), 2
        )

    logger.debug(
        f"{deal_data['pair']}/{deal_data['id']}: "
        f"TP of {newtppercentage}% calculated based on last profit of "
        f"{last_profit_percentage} and current {deal_data['actual_profit_percentage']}%, "
        f"using activation_diff {activation_diff} and factor {tpincrementfactor}."
    )

    return currenttppercentage, newtppercentage


def calculate_safety_order(logger, bot_data, deal_data, filled_so_count, current_profit, merge_so):
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
            f"{deal_data['pair']}/{deal_data['id']}: at SO {socounter}/{deal_data['max_safety_orders']}, "
            f"Volume: {sovolume}/{totalvolume}, "
            f"Drop: {sopercentagedropfrombaseprice}/{totaldroppercentage}, "
            f"Price: {sobuyprice}"
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

        # Descision making :) Optimize later...
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
                f"not filled and required based on (negative) profit!"
            )

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            totaldroppercentage = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice

            sobuycount += 1
            sobuyvolume += nextsovolume

            # Stop here if only one SO must be calculated, instead of merging all SO's
            # up and until the current profit
            if not merge_so:
                sonextdroppercentage = nextsopercentagetotaldrop
                break
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
