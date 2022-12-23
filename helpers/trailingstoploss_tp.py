"""Cyberjunky's 3Commas bot helpers."""


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


def get_profit_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_profit WHERE dealid = {dealid}").fetchone()


def get_safety_db_data(cursor, dealid):
    """Check if deal was already logged and get stored data."""

    return cursor.execute(f"SELECT * FROM deal_safety WHERE dealid = {dealid}").fetchone()


def calculate_safety_order(logger, bot_data, deal_data, deal_db_data, current_profit):
    """Calculate the next SO order."""

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
            f"At SO {socounter} --- Volume: {sovolume}/{totalvolume}, Drop: {sopercentagedropfrombaseprice}/{totaldroppercentage}, Price: {sobuyprice}"
        )

        nextsovolume = 0.0
        nextsopercentagedropfrombaseprice = 0.0

        # First SO takes the default values, following SO are multiplied with the configured factors
        if socounter == 0:
            nextsovolume = float(bot_data["safety_order_volume"])
            nextsopercentagedropfrombaseprice = float(bot_data["safety_order_step_percentage"])
        else:
            nextsovolume = float(sovolume) * float(bot_data["martingale_volume_coefficient"])
            nextsopercentagedropfrombaseprice = float(sopercentagedropfrombaseprice) * float(bot_data["martingale_step_coefficient"])

        nextsototalvolume = totalvolume + nextsovolume
        nextsopercentagetotaldrop = totaldroppercentage + nextsopercentagedropfrombaseprice
        nextsobuyprice = float(deal_data["base_order_average_price"])  * ((100.0 - nextsopercentagetotaldrop) / 100.0)

        # Print data for next SO
        logger.debug(
            f"Calculated next SO {socounter + 1} --- Volume: {nextsovolume}/{nextsototalvolume}, Drop: {nextsopercentagedropfrombaseprice}/{nextsopercentagetotaldrop}, Price: {nextsobuyprice}"
        )

        # Descision making :) Optimize later...
        if socounter < deal_db_data["filled_so_count"]:
            logger.debug(f"SO {socounter} already filled!")

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            percentagetotaldrop = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice
        elif nextsopercentagetotaldrop <= current_profit:
            logger.debug(f"Next SO {socounter + 1} not filled and required based on (negative) profit!")

            sovolume = nextsovolume
            totalvolume = nextsototalvolume
            sopercentagedropfrombaseprice = nextsopercentagedropfrombaseprice
            percentagetotaldrop = nextsopercentagetotaldrop
            sobuyprice = nextsobuyprice

            sobuycount += 1
            sobuyvolume += nextsovolume
        elif nextsopercentagetotaldrop > current_profit:
            logger.debug(f"Next SO {socounter + 1} not filled and not required! Stop at SO {socounter}")

            sonextdroppercentage = nextsopercentagetotaldrop

            break

        socounter += 1

    logger.info(
        f"SO level {socounter} reached. Need to buy {sobuycount} - {sobuyvolume}/{sobuyprice}! Next SO at {sonextdroppercentage}"
    )

    return sobuycount, sobuyvolume, sobuyprice, percentagetotaldrop, sonextdroppercentage
