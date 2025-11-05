"""
Resource monitoring for FileArchitect.

Monitors system resources like memory, disk space, and I/O during processing.
"""

import time
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from threading import Thread, Event
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """Resource usage metrics."""
    timestamp: float
    memory_used_mb: float
    memory_percent: float
    disk_free_gb: float
    disk_percent_used: float
    io_read_mb: Optional[float] = None
    io_write_mb: Optional[float] = None


class ResourceMonitor:
    """
    Monitor system resources during processing.

    Tracks memory usage, disk space, and I/O statistics.
    Can trigger callbacks when thresholds are exceeded.
    """

    def __init__(
        self,
        destination_path: Path,
        check_interval: float = 5.0,
        low_space_threshold_gb: float = 5.0,
        memory_threshold_percent: float = 90.0
    ):
        """
        Initialize resource monitor.

        Args:
            destination_path: Destination path to monitor
            check_interval: Check interval in seconds
            low_space_threshold_gb: Trigger warning below this (GB)
            memory_threshold_percent: Trigger warning above this (%)
        """
        self.destination_path = destination_path
        self.check_interval = check_interval
        self.low_space_threshold_gb = low_space_threshold_gb
        self.memory_threshold_percent = memory_threshold_percent

        # Monitoring state
        self.running = False
        self.stop_event = Event()
        self.monitor_thread: Optional[Thread] = None

        # Callbacks
        self.on_low_space: Optional[Callable] = None
        self.on_high_memory: Optional[Callable] = None

        # Try to import psutil for advanced monitoring
        try:
            import psutil
            self.psutil = psutil
            self.has_psutil = True
        except ImportError:
            self.psutil = None
            self.has_psutil = False
            logger.warning("psutil not available - advanced monitoring disabled")

    def start(self):
        """Start monitoring in background thread."""
        if self.running:
            return

        self.running = True
        self.stop_event.clear()

        self.monitor_thread = Thread(
            target=self._monitor_loop,
            name="ResourceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop(self):
        """Stop monitoring."""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

        logger.info("Resource monitoring stopped")

    def get_metrics(self) -> ResourceMetrics:
        """
        Get current resource metrics.

        Returns:
            ResourceMetrics object
        """
        import shutil

        timestamp = time.time()

        # Get disk space
        disk_stat = shutil.disk_usage(str(self.destination_path))
        disk_free_gb = disk_stat.free / (1024 ** 3)
        disk_percent_used = (disk_stat.used / disk_stat.total) * 100 if disk_stat.total > 0 else 0

        # Get memory if psutil available
        memory_used_mb = 0.0
        memory_percent = 0.0
        io_read_mb = None
        io_write_mb = None

        if self.has_psutil and self.psutil:
            # Memory
            mem = self.psutil.virtual_memory()
            memory_used_mb = mem.used / (1024 ** 2)
            memory_percent = mem.percent

            # I/O stats
            try:
                process = self.psutil.Process()
                io_counters = process.io_counters()
                io_read_mb = io_counters.read_bytes / (1024 ** 2)
                io_write_mb = io_counters.write_bytes / (1024 ** 2)
            except Exception:
                pass  # I/O stats not available on all platforms

        return ResourceMetrics(
            timestamp=timestamp,
            memory_used_mb=memory_used_mb,
            memory_percent=memory_percent,
            disk_free_gb=disk_free_gb,
            disk_percent_used=disk_percent_used,
            io_read_mb=io_read_mb,
            io_write_mb=io_write_mb
        )

    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.debug("Resource monitor loop started")

        while not self.stop_event.is_set():
            try:
                metrics = self.get_metrics()

                # Check disk space
                if metrics.disk_free_gb < self.low_space_threshold_gb:
                    logger.warning(
                        f"Low disk space: {metrics.disk_free_gb:.2f}GB "
                        f"(threshold: {self.low_space_threshold_gb:.2f}GB)"
                    )
                    if self.on_low_space:
                        try:
                            self.on_low_space(metrics)
                        except Exception as e:
                            logger.error(f"Error in low_space callback: {e}")

                # Check memory
                if self.has_psutil and metrics.memory_percent > self.memory_threshold_percent:
                    logger.warning(
                        f"High memory usage: {metrics.memory_percent:.1f}% "
                        f"(threshold: {self.memory_threshold_percent:.1f}%)"
                    )
                    if self.on_high_memory:
                        try:
                            self.on_high_memory(metrics)
                        except Exception as e:
                            logger.error(f"Error in high_memory callback: {e}")

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            # Sleep for interval
            self.stop_event.wait(self.check_interval)

        logger.debug("Resource monitor loop stopped")

    def format_metrics(self, metrics: ResourceMetrics) -> str:
        """
        Format metrics as human-readable string.

        Args:
            metrics: ResourceMetrics object

        Returns:
            Formatted string
        """
        lines = [
            "Resource Metrics:",
            f"  Disk: {metrics.disk_free_gb:.2f}GB free ({metrics.disk_percent_used:.1f}% used)",
        ]

        if self.has_psutil:
            lines.append(f"  Memory: {metrics.memory_used_mb:.0f}MB ({metrics.memory_percent:.1f}%)")

            if metrics.io_read_mb is not None and metrics.io_write_mb is not None:
                lines.append(
                    f"  I/O: {metrics.io_read_mb:.1f}MB read, "
                    f"{metrics.io_write_mb:.1f}MB write"
                )

        return "\n".join(lines)


class AutoPauseMonitor(ResourceMonitor):
    """
    Resource monitor that can auto-pause processing on low resources.

    Extends ResourceMonitor with auto-pause functionality.
    """

    def __init__(
        self,
        destination_path: Path,
        pause_callback: Optional[Callable] = None,
        **kwargs
    ):
        """
        Initialize auto-pause monitor.

        Args:
            destination_path: Destination path to monitor
            pause_callback: Callback to pause processing
            **kwargs: Additional arguments for ResourceMonitor
        """
        super().__init__(destination_path, **kwargs)
        self.pause_callback = pause_callback
        self.paused_by_monitor = False

        # Set up auto-pause on low space
        self.on_low_space = self._handle_low_space

    def _handle_low_space(self, metrics: ResourceMetrics):
        """Handle low space condition."""
        if self.paused_by_monitor:
            return  # Already paused

        logger.warning(
            f"Auto-pausing due to low disk space: {metrics.disk_free_gb:.2f}GB"
        )

        if self.pause_callback:
            try:
                self.pause_callback()
                self.paused_by_monitor = True
            except Exception as e:
                logger.error(f"Error pausing processing: {e}")

    def reset_pause_flag(self):
        """Reset the pause flag (call this when resuming)."""
        self.paused_by_monitor = False
