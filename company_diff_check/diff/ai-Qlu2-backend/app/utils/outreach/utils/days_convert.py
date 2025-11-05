from typing import Tuple


async def days_to_years_months(total_days: int) -> Tuple[int, str]:
    """
    Convert a number of days into the largest whole units of years or months.

    This function calculates the total number of years and the remainder in months from the given days.
    It assumes a year has 365 days and a month has 30 days. The function returns either the number
    of years or months, depending on which is the largest unit that is greater than zero.

    Parameters:
    total_days (int): The total number of days to be converted.

    Returns:
    Tuple[int, str]: A tuple containing the number of years or months and the corresponding unit as a string.
                     If there are no full years, it returns the number of months. Otherwise, it returns the number of years.
    """
    years = total_days // 365
    remaining_days = total_days % 365
    months = remaining_days // 30  # Assuming 30 days in a month (adjust as needed)
    remaining_days %= 30

    if years == 0:
        return months, "months"
    return years, "years"
