import datetime
import re

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
