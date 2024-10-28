from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

@dataclass
class DateRange:
    # range of time
    start_date: date
    end_date: Optional[date] = None

    def __post_init__(self) -> None:
        if isinstance(self.start_date, datetime):
            self.start_date = self.start_date.date()

        if isinstance(self.end_date, datetime):
            self.end_date = self.end_date.date()

    def is_date_in_range(self, date: date) -> bool:
        if self.end_date is None:
            # Check only start_date
            return date == self.start_date

        return date >= self.start_date and date < self.end_date