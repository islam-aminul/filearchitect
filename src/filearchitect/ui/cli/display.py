"""
Progress display for CLI.

Provides real-time progress updates in the terminal.
"""

import sys
from datetime import datetime
from typing import Optional


class ProgressDisplay:
    """
    Display progress updates in the terminal.

    Shows real-time statistics during file processing.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize progress display.

        Args:
            verbose: Show detailed progress updates
        """
        self.verbose = verbose
        self.last_update = None
        self.update_interval = 1.0  # Update every second

    def update(self, progress):
        """
        Update progress display.

        Args:
            progress: ProcessingProgress object
        """
        # Throttle updates
        now = datetime.now()
        if self.last_update:
            elapsed = (now - self.last_update).total_seconds()
            if elapsed < self.update_interval:
                return

        self.last_update = now

        # Format progress
        self._display_progress(progress)

    def _display_progress(self, progress):
        """Display formatted progress."""
        # Calculate totals
        total = progress.files_scanned
        completed = (
            progress.files_processed +
            progress.files_skipped +
            progress.files_duplicates +
            progress.files_error
        )

        if total == 0:
            percent = 0
        else:
            percent = (completed / total) * 100

        # Format current file
        current_file = ""
        if progress.current_file:
            current_file = str(progress.current_file)
            # Truncate long paths
            if len(current_file) > 60:
                current_file = "..." + current_file[-57:]

        # Format speed
        speed_str = f"{progress.processing_speed:.1f} files/sec"

        # Format ETA
        eta_str = ""
        if progress.eta_seconds:
            if progress.eta_seconds < 60:
                eta_str = f"{progress.eta_seconds}s"
            elif progress.eta_seconds < 3600:
                minutes = progress.eta_seconds // 60
                eta_str = f"{minutes}m"
            else:
                hours = progress.eta_seconds // 3600
                minutes = (progress.eta_seconds % 3600) // 60
                eta_str = f"{hours}h {minutes}m"

        # Format bytes
        gb_processed = progress.bytes_processed / (1024 ** 3)
        gb_total = progress.bytes_total / (1024 ** 3)

        # Build progress line
        if self.verbose:
            # Detailed progress
            lines = [
                f"\r\033[K",  # Clear line
                f"State: {progress.state.value}",
                f"Progress: {completed}/{total} files ({percent:.1f}%)",
                f"Processed: {progress.files_processed} | Skipped: {progress.files_skipped} | "
                f"Duplicates: {progress.files_duplicates} | Errors: {progress.files_error}",
                f"Data: {gb_processed:.2f} GB / {gb_total:.2f} GB",
                f"Speed: {speed_str}",
            ]

            if eta_str:
                lines.append(f"ETA: {eta_str}")

            if current_file:
                lines.append(f"Current: {current_file}")

            # Print each line
            for i, line in enumerate(lines):
                if i == 0:
                    sys.stdout.write(line)
                else:
                    sys.stdout.write(f"\n{line}")

            # Move cursor back to first line
            if len(lines) > 1:
                sys.stdout.write(f"\033[{len(lines)-1}A")

        else:
            # Compact progress
            progress_bar = self._make_progress_bar(percent, width=30)

            line = (
                f"\r\033[K"  # Clear line
                f"{progress_bar} {percent:>5.1f}% | "
                f"{completed}/{total} files | "
                f"{speed_str}"
            )

            if eta_str:
                line += f" | ETA: {eta_str}"

            sys.stdout.write(line)

        sys.stdout.flush()

    def _make_progress_bar(self, percent: float, width: int = 30) -> str:
        """
        Make a text progress bar.

        Args:
            percent: Percentage (0-100)
            width: Width of bar in characters

        Returns:
            Progress bar string
        """
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"

    def clear(self):
        """Clear progress display."""
        if self.verbose:
            # Clear multiple lines
            for _ in range(10):
                sys.stdout.write("\r\033[K\n")
            sys.stdout.write("\033[10A")
        else:
            sys.stdout.write("\r\033[K")

        sys.stdout.flush()


def format_time(seconds: int) -> str:
    """
    Format seconds as human-readable time.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "2h 30m" or "45s"
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"


def format_bytes(bytes_count: int) -> str:
    """
    Format bytes as human-readable size.

    Args:
        bytes_count: Size in bytes

    Returns:
        Formatted string like "1.5 GB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"
