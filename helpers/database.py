"""Cyberjunky's 3Commas bot helpers."""

import time


def get_next_process_time(database, table, column, value_id):
    """Get the next processing time for the specified bot."""

    dbrow = database.cursor().execute(
            f"SELECT next_processing_timestamp FROM {table} WHERE {column} = '{value_id}'"
        ).fetchone()

    # Start with initial time, and substract one second to allow direct processing
    # for sections that did'nt have any previous process time stored
    nexttime = int(time.time() - 1.0)
    if dbrow is not None:
        nexttime = dbrow["next_processing_timestamp"]
    else:
        # Record missing, create one
        set_next_process_time(database, table, column, value_id, nexttime)

    return nexttime


def set_next_process_time(database, table, column, value_id, new_time):
    """Set the next processing time for the specified bot."""

    database.execute(
        f"REPLACE INTO {table} ({column}, next_processing_timestamp) "
        f"VALUES ('{value_id}', {new_time})"
    )

    database.commit()
