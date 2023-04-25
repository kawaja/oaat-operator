"""
utility.py

Various stand-alone utility functions.
"""
from typing import Any, Optional
import datetime
import re
import sys
import inspect

UTC = datetime.timezone.utc

DURMATCH = re.compile(r'''
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

if not DURMATCH:
    raise SyntaxError('DURMATCH invalid regular expression')


def parse_time(inputtime: dict) -> datetime.timedelta:
    """
    From a dict which contains a 'time' attribute and an optional 'tz'
    attribute, return a timedelta object which represents the time from
    midnight.
    """
    base = datetime.datetime.strptime('Z', '%z')
    tz = inputtime.get('tz', 'Z')
    # +n:00 -> +0n:00
    if tz[0] == '+':
        if int(tz[1]) in range(10):
            if tz[2] == ':':
                tz = tz[0] + '0' + tz[1:]
    timestr = inputtime.get('time')
    if not timestr:
        return datetime.timedelta(0)

    timestr += tz

    try:
        timeval = datetime.datetime.strptime(timestr, '%H:%M%z') - base
    except ValueError:
        try:
            timeval = datetime.datetime.strptime(timestr, '%H%z') - base
        except ValueError:
            return datetime.timedelta(0)

    # remove the "days" component so time is in the range 00:00 - 23:59
    return timeval + datetime.timedelta(days=-timeval.days)


class TimeWindow:
    def __init__(self, start: Any, end: Any) -> None:
        if isinstance(start, str):
            start = {'time': start}
        if isinstance(end, str):
            end = {'time': end}
        self.start = parse_time(start)
        self.end = parse_time(end)

    def __contains__(self, testdate: datetime.datetime) -> bool:
        testtime = testdate.replace(year=1900, month=1, day=1)
        base = datetime.datetime(year=1900, month=1, day=1, tzinfo=UTC)
        start = base + self.start
        end = base + self.end
        if start > end:
            if testtime >= start or testtime <= end:
                return True
        if testtime >= start and testtime <= end:
            return True
        return False


def parse_duration(duration: str) -> Optional[datetime.timedelta]:
    """Calculate timedelta from a duration string."""
    if duration is None:
        return None
    units: dict[str, int] = {}
    start = 0
    while True:
        match = DURMATCH.search(duration[start:])
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
    if units:
        return datetime.timedelta(**units)
    else:
        return None


def date_from_isostr(datestr: str) -> datetime.datetime:
    """Convert a ISO-format date string to datetime, ensuring UTC."""
    if datestr:
        # fromisoformat() does not recognise trailing Z for UTC
        if datestr[-1:] == 'Z':
            datestr = datestr[:-1] + '+00:00'
        fromiso = datetime.datetime.fromisoformat(datestr)
        if fromiso.tzinfo is None:
            return datetime.datetime.fromisoformat(datestr).replace(tzinfo=UTC)
        else:
            return datetime.datetime.fromtimestamp(
                datetime.datetime.fromisoformat(datestr).timestamp(), tz=UTC)
    return datetime.datetime.fromtimestamp(0, tz=UTC)


def now() -> datetime.datetime:
    """Current time (in UTC) as datetime."""
    return datetime.datetime.now(tz=UTC)


def now_iso() -> str:
    """Current time (in UTC) as isoformat string."""
    return now().isoformat()


def my_name() -> str:
    """Return the name of the calling function."""
    return sys._getframe(1).f_code.co_name


def my_details(parents=0) -> Optional[str]:
    """Return details of the calling function."""
    frameinfo = inspect.stack()[parents+1]
    cframeinfo = inspect.stack()[parents+2]
    rval = f'{cframeinfo.filename}:{cframeinfo.lineno} {frameinfo.function}('
    if frameinfo is None:
        return None
    av = inspect.getargvalues(frameinfo.frame)
    args = []
    for arg in av.args:
        args.append(f'{arg}={repr(av.locals[arg])}')
    if av.varargs is not None:
        args.append(f'{av.varargs}={repr(av.locals[av.varargs])}')
    if av.keywords is not None:
        args.append(f'{av.keywords}={repr(av.locals[av.keywords])}')

    rval += ', '.join(args)
    return f'{rval})'
