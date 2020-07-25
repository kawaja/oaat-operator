"""
utility.py

Various stand-alone utility functions.
"""
import datetime
import re
import sys

UTC = datetime.timezone.utc

FREQMATCH = re.compile(r'''
    \b
    (?P<val>\d+)
    \s*
    (?P<unit>(
        s(ec(ond)?s?)?|
        m(in(ute)?s?)?|
        h((ou)?rs?)?|
        d(a?ys?)?|
        w((ee)?ks?)?
    ))($|\b|\d)''', re.VERBOSE)

if not FREQMATCH:
    raise SyntaxError('FREQMATCH invalid regular expression')


def parse_frequency(freq: str) -> datetime.timedelta:
    """Calculate timedelta from a frequency string."""
    units = {}
    start = 0
    while True:
        match = FREQMATCH.search(freq[start:])
        if not match:
            break
        val = int(match.group('val'))
        unit = match.group('unit')
        start += match.end('unit')
        if val and unit:
            if unit[0] == 's':
                units['seconds'] = units.setdefault('seconds', 0) + val
            if unit[0] == 'm':
                units['minutes'] = units.setdefault('minutes', 0) + val
            if unit[0] == 'h':
                units['hours'] = units.setdefault('hours', 0) + val
            if unit[0] == 'd':
                units['days'] = units.setdefault('days', 0) + val
            if unit[0] == 'w':
                units['weeks'] = units.setdefault('weeks', 0) + val
    return datetime.timedelta(**units)


def date_from_isostr(datestr):
    """Convert a ISO-format date string to datetime, ensuring UTC."""
    if datestr:
        # fromisoformat() does not recognise trailing Z for UTC
        if datestr[-1:] == 'Z':
            datestr = datestr[:-1] + '+00:00'
        return datetime.datetime.fromisoformat(datestr).replace(tzinfo=UTC)
    return datetime.datetime.fromtimestamp(0, tz=UTC)


def now():
    """Current time (in UTC) as datetime."""
    return datetime.datetime.now(tz=UTC)


def now_iso():
    """Current time (in UTC) as isoformat string."""
    now().isoformat()


def my_name():
    """Return the name of the calling function."""
    return sys._getframe(1).f_code.co_name
