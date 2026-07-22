"""Canonical business-day calendar with exchange extension points."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class BusinessCalendar:
    exchange: str = "GENERIC"
    weekend_days: frozenset[int] = frozenset({5, 6})
    holidays: frozenset[date] = field(default_factory=frozenset)

    @classmethod
    def for_year(
        cls,
        year: int,
        *,
        exchange: str = "NYSE",
        additional_holidays: Iterable[date] = (),
    ) -> "BusinessCalendar":
        exchange_key = str(exchange or "GENERIC").upper()
        holidays = set(additional_holidays)
        if exchange_key in {"NYSE", "NASDAQ", "US"}:
            holidays.update(_us_market_holidays(year))
        return cls(exchange=exchange_key, holidays=frozenset(holidays))

    def is_business_day(self, value: date | datetime) -> bool:
        day = value.date() if isinstance(value, datetime) else value
        return day.weekday() not in self.weekend_days and day not in self.holidays

    def business_days_between(
        self,
        start: date | datetime,
        end: date | datetime,
        *,
        inclusive: bool = True,
    ) -> int:
        first = start.date() if isinstance(start, datetime) else start
        last = end.date() if isinstance(end, datetime) else end
        if last < first:
            return 0
        if not inclusive:
            first += timedelta(days=1)
            last -= timedelta(days=1)
        count = 0
        current = first
        while current <= last:
            count += int(self.is_business_day(current))
            current += timedelta(days=1)
        return count

    def business_days(self, start: date, end: date) -> tuple[date, ...]:
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_business_day(current):
                days.append(current)
            current += timedelta(days=1)
        return tuple(days)

    def next_business_day(self, value: date | datetime) -> date:
        current = (value.date() if isinstance(value, datetime) else value) + timedelta(days=1)
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current


def _us_market_holidays(year: int) -> set[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday(year, 5, 0),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    return holidays


def _observed(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    value = date(year, month, 1)
    value += timedelta(days=(weekday - value.weekday()) % 7)
    return value + timedelta(weeks=occurrence - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    value = date(year + int(month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return value - timedelta(days=(value.weekday() - weekday) % 7)


def _good_friday(year: int) -> date:
    # Anonymous Gregorian computus; Good Friday is two days before Easter.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    length = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * length) // 451
    month = (h + length - 7 * m + 114) // 31
    day = ((h + length - 7 * m + 114) % 31) + 1
    return date(year, month, day) - timedelta(days=2)


__all__ = ["BusinessCalendar"]
