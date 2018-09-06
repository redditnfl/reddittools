#!/usr/bin/env python
from ago import human
import pytz
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse

def log(*args, **kwargs):
    logging.getLogger(__name__).info(*args, **kwargs)

def run(countdown_date, countdown_timezone, *args, **kwargs):
    log("Running countdown with countdown_date=<%s>, countdown_timezone=<%s>, kwargs=<%r>", countdown_date, countdown_timezone, kwargs)
    tz = pytz.timezone(countdown_timezone)
    now = tz.fromutc(datetime.utcnow())
    then = tz.localize(parse(countdown_date))
    future = kwargs.get('countdown_future', '{0}')
    past = kwargs.get('countdown_past', '{0}')
    precision = int(kwargs.get('countdown_precision', 2))
    log("Human config: future=<%s>, past=<%s>, precision=<%d>", future, past, precision)
    result = human(now-then, past_tense = past, future_tense = future, precision = precision)
    log("Result: %s", result)
    return result
