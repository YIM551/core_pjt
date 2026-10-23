from datetime import date

from fastapi import HTTPException


def validate_date_range(start: date | None, end: date | None) -> None:
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="end_date cannot be earlier than start_date")
