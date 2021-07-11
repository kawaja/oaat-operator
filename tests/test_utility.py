import unittest
from datetime import timedelta as td
from datetime import datetime as dt
import datetime
import oaatoperator.utility
from oaatoperator.utility import (TimeWindow, date_from_isostr, my_name,
                                  now_iso, parse_duration, parse_time)


UTC = datetime.timezone.utc


class TestDateFromIsoStr(unittest.TestCase):
    def test_with_tz(self):
        retdate = date_from_isostr("2020-08-15T03:03:15.950209+00:00")
        self.assertEqual(retdate.timestamp(), 1597460595.950209, retdate)

    def test_with_z(self):
        retdate = date_from_isostr("2020-08-15T03:03:15.950209Z")
        self.assertEqual(retdate.timestamp(), 1597460595.950209, retdate)

    def test_with_notz(self):
        retdate = date_from_isostr("2020-08-15T03:03:15.950209")
        self.assertEqual(retdate.timestamp(), 1597460595.950209, retdate)

    def test_with_wrong_tz(self):
        retdate = date_from_isostr("2020-08-15T04:03:15.950209+01:00")
        self.assertEqual(retdate.timestamp(), 1597460595.950209, retdate)

    def test_with_invalid_str(self):
        with self.assertRaises(ValueError):
            date_from_isostr("nothing")


class ParseTimeTests(unittest.TestCase):
    def test_badtz(self):
        self.assertEqual(parse_time({
            'time': '0:00',
            'tz': 'Y'
        }), td(0))

    def test_None_time(self):
        self.assertEqual(parse_time({'time': None}), td(0))

    def test_bad_time(self):
        self.assertEqual(parse_time({'time': 'none'}), td(0))

    def test_with_seconds(self):
        self.assertEqual(parse_time({'time': '00:00:00'}), td(0))

    def test_naked_times(self):  # naked times should be equivalent to UTC
        self.assertEqual(
            parse_time({'time': '0:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '00:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '01:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '01:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '00:01'}), td(minutes=1))

    def test_utc_times(self):
        self.assertEqual(
            parse_time({'time': '0:00', 'tz': 'Z'}), td(0))
        self.assertEqual(
            parse_time({'time': '00:00', 'tz': 'Z'}), td(0))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': 'Z'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': 'Z'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '00:01', 'tz': 'Z'}), td(minutes=1))

    def test_tz_advance_times(self):
        self.assertEqual(
            parse_time({'time': '0:00', 'tz': '+1:00'}), td(hours=23))
        self.assertEqual(
            parse_time({'time': '00:00', 'tz': '+1:00'}), td(hours=23))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': '+1:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': '+1:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '02:00', 'tz': '+1:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '02:00', 'tz': '+1:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '00:01', 'tz': '+1:00'}),
            td(hours=23, minutes=1))

    def test_tz__times(self):
        self.assertEqual(
            parse_time({'time': '0:00', 'tz': '+1:00'}), td(hours=23))
        self.assertEqual(
            parse_time({'time': '00:00', 'tz': '+1:00'}), td(hours=23))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': '+1:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '01:00', 'tz': '+1:00'}), td(0))
        self.assertEqual(
            parse_time({'time': '02:00', 'tz': '+1:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '02:00', 'tz': '+1:00'}), td(hours=1))
        self.assertEqual(
            parse_time({'time': '00:01', 'tz': '+1:00'}),
            td(hours=23, minutes=1))


class TimeWindowTests(unittest.TestCase):
    def test_init(self):
        tw = TimeWindow('02:00', '05:00')
        self.assertEqual(tw.start, td(hours=2))
        self.assertEqual(tw.end, td(hours=5))

    def run_in_tests(self, tw, clean, testvals):
        for testval in testvals:
            self.assertEqual(
                dt.now().replace(hour=testval[0], **clean) in tw,
                testval[1],
                testval[0])

    def test_regular(self):
        tw = TimeWindow('02:00', '05:00')
        clean = {'minute': 0, 'second': 0, 'microsecond': 0, 'tzinfo': UTC}
        testvals = [
            (0, False),
            (1, False),
            (2, True),
            (4, True),
            (5, True),
            (6, False),
            (12, False),
            (23, False)
        ]
        self.run_in_tests(tw, clean, testvals)

    def test_irregular(self):
        tw = TimeWindow('15:00', '05:00')
        clean = {'minute': 0, 'second': 0, 'microsecond': 0, 'tzinfo': UTC}
        testvals = [
            (0, True),
            (1, True),
            (2, True),
            (4, True),
            (5, True),
            (6, False),
            (12, False),
            (15, True),
            (19, True),
            (23, True)
        ]
        self.run_in_tests(tw, clean, testvals)


class ParseDurationTests(unittest.TestCase):
    def test_seconds_only(self):
        self.assertFalse(parse_duration('0s'))
        self.assertEqual(parse_duration('1s'), td(seconds=1))
        self.assertEqual(parse_duration('1000s'), td(seconds=1000))
        self.assertEqual(parse_duration('1sec'), td(seconds=1))
        self.assertEqual(parse_duration('1secs'), td(seconds=1))
        self.assertEqual(parse_duration('1second'), td(seconds=1))
        self.assertEqual(parse_duration('1seconds'), td(seconds=1))
        self.assertEqual(parse_duration('1 seconds'), td(seconds=1))
        self.assertEqual(parse_duration('1 s'), td(seconds=1))

    def test_seconds_only_negative(self):
        self.assertFalse(parse_duration('0s'))
        self.assertFalse(parse_duration('1ss'))
        self.assertFalse(parse_duration('1sond'))
        self.assertFalse(parse_duration('1sonds'))
        self.assertFalse(parse_duration('1 ss'))
        self.assertFalse(parse_duration('1 sond'))
        self.assertFalse(parse_duration('1 sonds'))

    def test_minutes_only(self):
        self.assertFalse(parse_duration('0m'))
        self.assertEqual(parse_duration('1m'), td(minutes=1))
        self.assertEqual(parse_duration('1000m'), td(minutes=1000))
        self.assertEqual(parse_duration('1min'), td(minutes=1))
        self.assertEqual(parse_duration('1mins'), td(minutes=1))
        self.assertEqual(parse_duration('1minute'), td(minutes=1))
        self.assertEqual(parse_duration('1minutes'), td(minutes=1))
        self.assertEqual(parse_duration('1 minutes'), td(minutes=1))
        self.assertEqual(parse_duration('1 m'), td(minutes=1))

    def test_minutes_only_negative(self):
        self.assertFalse(parse_duration('0m'))
        self.assertFalse(parse_duration('1ms'))
        self.assertFalse(parse_duration('1mute'))
        self.assertFalse(parse_duration('1mutes'))
        self.assertFalse(parse_duration('1 ms'))
        self.assertFalse(parse_duration('1 mute'))
        self.assertFalse(parse_duration('1 mutes'))

    def test_hours_only(self):
        self.assertFalse(parse_duration('0h'))
        self.assertEqual(parse_duration('1h'), td(hours=1))
        self.assertEqual(parse_duration('1000h'), td(hours=1000))
        self.assertEqual(parse_duration('1hr'), td(hours=1))
        self.assertEqual(parse_duration('1hrs'), td(hours=1))
        self.assertEqual(parse_duration('1hour'), td(hours=1))
        self.assertEqual(parse_duration('1hours'), td(hours=1))
        self.assertEqual(parse_duration('1 hours'), td(hours=1))
        self.assertEqual(parse_duration('1 h'), td(hours=1))

    def test_hours_only_negative(self):
        self.assertFalse(parse_duration('0h'))
        self.assertFalse(parse_duration('1hs'))
        self.assertFalse(parse_duration('1hou'))
        self.assertFalse(parse_duration('1hous'))
        self.assertFalse(parse_duration('1 hs'))
        self.assertFalse(parse_duration('1 hou'))
        self.assertFalse(parse_duration('1 hous'))

    def test_days_only(self):
        self.assertFalse(parse_duration('0d'))
        self.assertEqual(parse_duration('1d'), td(days=1))
        self.assertEqual(parse_duration('1000d'), td(days=1000))
        self.assertEqual(parse_duration('1day'), td(days=1))
        self.assertEqual(parse_duration('1days'), td(days=1))
        self.assertEqual(parse_duration('1dy'), td(days=1))
        self.assertEqual(parse_duration('1dys'), td(days=1))
        self.assertEqual(parse_duration('1 day'), td(days=1))
        self.assertEqual(parse_duration('1 d'), td(days=1))

    def test_days_only_negative(self):
        self.assertFalse(parse_duration('0d'))
        self.assertFalse(parse_duration('1ds'))
        self.assertFalse(parse_duration('1 ds'))

    def test_weeks_only(self):
        self.assertFalse(parse_duration('0w'))
        self.assertEqual(parse_duration('1w'), td(weeks=1))
        self.assertEqual(parse_duration('1000w'), td(weeks=1000))
        self.assertEqual(parse_duration('1wk'), td(weeks=1))
        self.assertEqual(parse_duration('1wks'), td(weeks=1))
        self.assertEqual(parse_duration('1week'), td(weeks=1))
        self.assertEqual(parse_duration('1weeks'), td(weeks=1))
        self.assertEqual(parse_duration('1 weeks'), td(weeks=1))
        self.assertEqual(parse_duration('1 w'), td(weeks=1))

    def test_weeks_only_negative(self):
        self.assertFalse(parse_duration('0w'))
        self.assertFalse(parse_duration('1ws'))
        self.assertFalse(parse_duration('1we'))
        self.assertFalse(parse_duration('1wes'))
        self.assertFalse(parse_duration('1 ws'))
        self.assertFalse(parse_duration('1 we'))
        self.assertFalse(parse_duration('1 wes'))

    def test_mins_secs(self):
        self.assertFalse(parse_duration('0s0m'))
        self.assertEqual(parse_duration('0s1m'), td(minutes=1))
        self.assertEqual(parse_duration('0s11m'), td(minutes=11))
        self.assertEqual(parse_duration('1m0s'), td(minutes=1))
        self.assertEqual(parse_duration('11m0s'), td(minutes=11))
        self.assertEqual(parse_duration('1m 0s'), td(minutes=1))
        self.assertEqual(parse_duration('0s 11m'), td(minutes=11))
        self.assertEqual(parse_duration('0s 1m'), td(minutes=1))
        self.assertEqual(parse_duration('11m 0s'), td(minutes=11))
        self.assertEqual(parse_duration('1m 0s'), td(minutes=1))
        self.assertEqual(parse_duration('11m 0s'), td(minutes=11))
        self.assertEqual(parse_duration('0 s 1 m'), td(minutes=1))
        self.assertEqual(parse_duration('0 s 11 m'), td(minutes=11))
        self.assertFalse(parse_duration('0s0m'))
        self.assertEqual(parse_duration('0sec1min'), td(minutes=1))
        self.assertEqual(parse_duration('0sec11min'), td(minutes=11))
        self.assertEqual(parse_duration('1min0secs'), td(minutes=1))
        self.assertEqual(parse_duration('11min0secs'), td(minutes=11))
        self.assertEqual(parse_duration('0secs 1min'), td(minutes=1))
        self.assertEqual(parse_duration('0secs 11min'), td(minutes=11))
        self.assertEqual(parse_duration('1min 0sec'), td(minutes=1))
        self.assertEqual(parse_duration('11min 0sec'), td(minutes=11))
        self.assertEqual(parse_duration('0 sec 1 min'), td(minutes=1))
        self.assertEqual(parse_duration('0 sec 11 min'),
                         td(minutes=11))
        self.assertEqual(parse_duration('1 m 0 sec'), td(minutes=1))
        self.assertEqual(parse_duration('11 m 0 sec'), td(minutes=11))

        self.assertEqual(parse_duration('1s1m'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1m1s'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1s 1m'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1m 1s'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1 s 1 m'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1sec1min'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1min1secs'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1secs 1min'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1min 1sec'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1 sec 1 min'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1 m 1 sec'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1 min 1 sec'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('1 min 1 sec'),
                         td(minutes=1, seconds=1))
        self.assertEqual(parse_duration('11 min 1 sec'),
                         td(minutes=11, seconds=1))
        self.assertEqual(parse_duration('1 min 11 sec'),
                         td(minutes=1, seconds=11))
        self.assertEqual(parse_duration('11 min 11 sec'),
                         td(minutes=11, seconds=11))

    def test_hours_mins_secs(self):
        self.assertFalse(parse_duration('0s0m0h'))
        self.assertEqual(parse_duration('0s1h1m'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('1m1h0s'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('0s 1m 1h'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('1h 1m 0s'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('0 s 1 h 1 m'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('0sec1hr1min'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('1min1hr0secs'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('0secs 1hr 1min'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('1hr 1min 0sec'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('0 sec 1 min 1 hr'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('1 hour 1 m 0 sec'),
                         td(minutes=1, hours=1))
        self.assertEqual(parse_duration('5 hour 6 m 7 sec'),
                         td(seconds=7, minutes=6, hours=5))

    def test_extra_hours_mins_secs(self):
        self.assertFalse(parse_duration('0s0m0h'))
        self.assertEqual(parse_duration('0s1h65m'),
                         td(minutes=5, hours=2))
        self.assertEqual(parse_duration('65m1h0s'),
                         td(minutes=5, hours=2))
        self.assertEqual(parse_duration('0s 65m 1h'),
                         td(minutes=5, hours=2))
        self.assertEqual(parse_duration('0sec1hr65min'),
                         td(minutes=5, hours=2))
        self.assertEqual(parse_duration('5 hour 6 m 100 sec'),
                         td(seconds=40, minutes=7, hours=5))


class MiscTests(unittest.TestCase):
    def test_now(self):
        self.assertIsInstance(oaatoperator.utility.now(), dt)
        self.assertIsInstance(now_iso(), str)

    def test_myname(self):
        self.assertEqual(my_name(), 'test_myname')


if __name__ == '__main__':
    unittest.main()
