"""
Date and time utilities for FileArchitect.

This module provides utilities for parsing, formatting, and validating dates
from various sources including EXIF data, filenames, and folder paths.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List

from ..core.constants import DateSource
from ..core.exceptions import ValidationError


# Common date/time patterns for parsing filenames
FILENAME_PATTERNS = [
    # YYYY-MM-DD HH-MM-SS (most common export format)
    (r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2})-(\d{2})-(\d{2})", "%Y-%m-%d %H-%M-%S"),
    # YYYYMMDD_HHMMSS (compact format)
    (r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "%Y%m%d_%H%M%S"),
    # IMG_YYYYMMDD_HHMMSS (common camera format)
    (r"IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "IMG_%Y%m%d_%H%M%S"),
    # VID-YYYYMMDD-HHMMSS (WhatsApp video format)
    (r"VID-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", "VID-%Y%m%d-%H%M%S"),
    # YYYY-MM-DD (date only)
    (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
    # YYYYMMDD (date only, compact)
    (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
    # Screenshot_YYYYMMDD-HHMMSS
    (r"Screenshot_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", "Screenshot_%Y%m%d-%H%M%S"),
    # PXL_YYYYMMDD_HHMMSS (Pixel phone format)
    (r"PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "PXL_%Y%m%d_%H%M%S"),
]

# EXIF date format
EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# Output format for filenames
FILENAME_OUTPUT_FORMAT = "%Y-%m-%d %H-%M-%S"


def parse_exif_date(exif_date: str) -> Optional[datetime]:
    """
    Parse date from EXIF DateTimeOriginal field.

    Args:
        exif_date: Date string from EXIF data (format: "YYYY:MM:DD HH:MM:SS")

    Returns:
        datetime object if parsing successful, None otherwise

    Examples:
        >>> parse_exif_date("2023:11:05 14:30:45")
        datetime.datetime(2023, 11, 5, 14, 30, 45)
    """
    if not exif_date or not isinstance(exif_date, str):
        return None

    try:
        # Remove any timezone info if present
        exif_date = exif_date.split('+')[0].split('-')[0].strip()
        dt = datetime.strptime(exif_date, EXIF_DATE_FORMAT)
        return dt
    except (ValueError, AttributeError):
        return None


def parse_filename_date(filename: str, custom_patterns: Optional[List[Tuple[str, str]]] = None) -> Optional[datetime]:
    """
    Parse date from filename using pattern matching.

    Args:
        filename: Filename to parse
        custom_patterns: Optional list of (regex_pattern, format_string) tuples

    Returns:
        datetime object if parsing successful, None otherwise

    Examples:
        >>> parse_filename_date("2023-11-05 14-30-45.jpg")
        datetime.datetime(2023, 11, 5, 14, 30, 45)
        >>> parse_filename_date("IMG_20231105_143045.jpg")
        datetime.datetime(2023, 11, 5, 14, 30, 45)
    """
    if not filename:
        return None

    # Try custom patterns first if provided
    patterns = (custom_patterns or []) + FILENAME_PATTERNS

    for pattern, format_string in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                # Extract the matched portion
                matched_text = match.group(0)
                dt = datetime.strptime(matched_text, format_string)

                # Validate the date is reasonable (not in future, not too old)
                if validate_date(dt):
                    return dt
            except (ValueError, IndexError):
                continue

    return None


def parse_folder_date(folder_path: str) -> Optional[datetime]:
    """
    Parse date from folder path.

    Looks for year folders (YYYY) or year-month folders (YYYY-MM) in the path.

    Args:
        folder_path: Path to folder

    Returns:
        datetime object if parsing successful, None otherwise

    Examples:
        >>> parse_folder_date("/photos/2023/11/")
        datetime.datetime(2023, 11, 1, 0, 0, 0)
    """
    if not folder_path:
        return None

    path = Path(folder_path)
    parts = path.parts

    # Look for year patterns (4 digits)
    year_pattern = re.compile(r'^(\d{4})$')
    month_pattern = re.compile(r'^(\d{2})$')

    year = None
    month = None

    for i, part in enumerate(parts):
        year_match = year_pattern.match(part)
        if year_match:
            year = int(year_match.group(1))
            # Check if next part is a month
            if i + 1 < len(parts):
                month_match = month_pattern.match(parts[i + 1])
                if month_match:
                    month_val = int(month_match.group(1))
                    if 1 <= month_val <= 12:
                        month = month_val
            break

    if year and 1900 <= year <= datetime.now().year:
        try:
            return datetime(year, month or 1, 1)
        except ValueError:
            pass

    return None


def parse_date_with_fallback(
    exif_date: Optional[str] = None,
    filename: Optional[str] = None,
    folder_path: Optional[str] = None,
    custom_patterns: Optional[List[Tuple[str, str]]] = None
) -> Tuple[Optional[datetime], DateSource]:
    """
    Parse date using fallback chain: EXIF -> Filename -> Folder -> None.

    Args:
        exif_date: EXIF date string
        filename: Filename to parse
        folder_path: Folder path to parse
        custom_patterns: Optional custom filename patterns

    Returns:
        Tuple of (datetime object, DateSource) indicating where date came from

    Examples:
        >>> parse_date_with_fallback(exif_date="2023:11:05 14:30:45")
        (datetime.datetime(2023, 11, 5, 14, 30, 45), <DateSource.EXIF: 'exif'>)
    """
    # Try EXIF first
    if exif_date:
        dt = parse_exif_date(exif_date)
        if dt:
            return dt, DateSource.EXIF

    # Try filename
    if filename:
        dt = parse_filename_date(filename, custom_patterns)
        if dt:
            return dt, DateSource.FILENAME

    # Try folder path
    if folder_path:
        dt = parse_folder_date(folder_path)
        if dt:
            return dt, DateSource.FOLDER

    # No date found
    return None, DateSource.NONE


def format_datetime_for_filename(dt: datetime) -> str:
    """
    Format datetime for use in filenames.

    Args:
        dt: datetime object to format

    Returns:
        Formatted string in "YYYY-MM-DD HH-MM-SS" format

    Examples:
        >>> dt = datetime(2023, 11, 5, 14, 30, 45)
        >>> format_datetime_for_filename(dt)
        '2023-11-05 14-30-45'
    """
    return dt.strftime(FILENAME_OUTPUT_FORMAT)


def validate_date(dt: datetime, allow_future: bool = False, min_year: int = 1970) -> bool:
    """
    Validate that a date is reasonable.

    Args:
        dt: datetime object to validate
        allow_future: Whether to allow future dates
        min_year: Minimum valid year (default 1970)

    Returns:
        True if date is valid, False otherwise

    Examples:
        >>> validate_date(datetime(2023, 11, 5, 14, 30, 45))
        True
        >>> validate_date(datetime(2030, 1, 1))
        False
    """
    if not dt:
        return False

    now = datetime.now()

    # Check if date is in the future
    if not allow_future and dt > now:
        return False

    # Check minimum year
    if dt.year < min_year:
        return False

    # Check maximum year (allow up to current year + 1 for timezone differences)
    if dt.year > now.year + 1:
        return False

    return True


def normalize_timezone(dt: datetime, target_tz: Optional[timezone] = None) -> datetime:
    """
    Normalize datetime to a specific timezone.

    Args:
        dt: datetime object
        target_tz: Target timezone (default: UTC)

    Returns:
        datetime object in target timezone

    Examples:
        >>> dt = datetime(2023, 11, 5, 14, 30, 45)
        >>> normalize_timezone(dt)
        datetime.datetime(2023, 11, 5, 14, 30, 45, tzinfo=datetime.timezone.utc)
    """
    if target_tz is None:
        target_tz = timezone.utc

    # If datetime is naive (no timezone), assume it's in target timezone
    if dt.tzinfo is None:
        return dt.replace(tzinfo=target_tz)

    # Convert to target timezone
    return dt.astimezone(target_tz)


def get_year_from_date(dt: datetime) -> Optional[str]:
    """
    Extract year as string from datetime.

    Args:
        dt: datetime object

    Returns:
        Year as 4-digit string, or None if dt is None

    Examples:
        >>> get_year_from_date(datetime(2023, 11, 5))
        '2023'
    """
    if not dt:
        return None
    return str(dt.year)


def get_month_from_date(dt: datetime) -> Optional[str]:
    """
    Extract month as zero-padded string from datetime.

    Args:
        dt: datetime object

    Returns:
        Month as 2-digit string, or None if dt is None

    Examples:
        >>> get_month_from_date(datetime(2023, 11, 5))
        '11'
    """
    if not dt:
        return None
    return f"{dt.month:02d}"


def infer_date_from_nearby_files(
    file_dates: List[datetime],
    confidence_threshold: int = 3
) -> Optional[datetime]:
    """
    Infer date from nearby files using statistical analysis.

    Uses the median date from nearby files if there are enough samples.

    Args:
        file_dates: List of datetime objects from nearby files
        confidence_threshold: Minimum number of dates needed for confidence

    Returns:
        Inferred datetime, or None if not enough data

    Examples:
        >>> dates = [datetime(2023, 11, 5, i, 0, 0) for i in range(5)]
        >>> infer_date_from_nearby_files(dates)
        datetime.datetime(2023, 11, 5, 2, 0, 0)
    """
    if not file_dates or len(file_dates) < confidence_threshold:
        return None

    # Sort dates
    sorted_dates = sorted(file_dates)

    # Return median
    mid = len(sorted_dates) // 2
    if len(sorted_dates) % 2 == 0:
        # Even number of dates - average the two middle ones
        d1 = sorted_dates[mid - 1]
        d2 = sorted_dates[mid]
        avg_timestamp = (d1.timestamp() + d2.timestamp()) / 2
        return datetime.fromtimestamp(avg_timestamp)
    else:
        # Odd number - return middle one
        return sorted_dates[mid]


def parse_custom_pattern(date_string: str, pattern: str) -> Optional[datetime]:
    """
    Parse date using a custom strptime pattern.

    Args:
        date_string: String to parse
        pattern: strptime format pattern

    Returns:
        datetime object if successful, None otherwise

    Examples:
        >>> parse_custom_pattern("05-11-2023", "%d-%m-%Y")
        datetime.datetime(2023, 11, 5, 0, 0, 0)
    """
    if not date_string or not pattern:
        return None

    try:
        dt = datetime.strptime(date_string, pattern)
        if validate_date(dt):
            return dt
    except (ValueError, TypeError):
        pass

    return None
