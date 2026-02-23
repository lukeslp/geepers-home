"""Base sensor class for Sensor Playground.

All sensor implementations should inherit from BaseSensor and implement
the required methods. This formalises the interface documented in
sensors/__init__.py and provides shared retry/error-handling logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import time
import logging

logger = logging.getLogger(__name__)


class BaseSensor(ABC):
    """Abstract base class for all sensor modules.

    Subclasses must implement:
        _init_hardware()  — attempt to initialise the physical sensor
        _read_hardware()  — return a dict of field→value from real hardware
        _simulate()       — return a dict of realistic fake data

    The base class provides:
        read(demo)        — unified read with retry logic and error handling
        simulated         — property indicating whether hardware is available
        close()           — release resources (override if needed)
    """

    # Subclasses can override these for sensor-specific tuning
    MAX_RETRIES: int = 2
    RETRY_DELAY: float = 0.1  # seconds between retries

    def __init__(self, pin: int, cfg: Optional[Dict[str, Any]] = None):
        self.pin = pin
        self._cfg = cfg or {}
        self._hw_available = False
        self._consecutive_failures = 0
        self._total_reads = 0
        self._failed_reads = 0

        try:
            self._init_hardware()
        except Exception as exc:
            logger.warning(
                "%s: hardware init failed on pin %s — %s",
                self.__class__.__name__, pin, exc,
            )
            self._hw_available = False

    # ------------------------------------------------------------------
    # Abstract methods — subclasses MUST implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _init_hardware(self) -> None:
        """Attempt to initialise hardware. Set self._hw_available = True on success."""
        ...

    @abstractmethod
    def _read_hardware(self) -> Optional[Dict[str, Any]]:
        """Read from real hardware. Return dict of field→value, or None on failure."""
        ...

    @abstractmethod
    def _simulate(self) -> Dict[str, Any]:
        """Return realistic simulated data for demo mode."""
        ...

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def simulated(self) -> bool:
        """True when hardware is not available."""
        return not self._hw_available

    @property
    def reliability(self) -> float:
        """Percentage of successful reads (0.0–100.0)."""
        if self._total_reads == 0:
            return 100.0
        return ((self._total_reads - self._failed_reads) / self._total_reads) * 100.0

    def read(self, demo: bool = False) -> Optional[Dict[str, Any]]:
        """Read sensor data with retry logic.

        Args:
            demo: If True, return simulated data regardless of hardware state.

        Returns:
            Dict of field→value on success, None on failure.
        """
        if demo:
            return self._simulate()

        if not self._hw_available:
            return None

        self._total_reads += 1

        # Retry loop
        last_exc = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                result = self._read_hardware()
                if result is not None:
                    self._consecutive_failures = 0
                    return result
            except Exception as exc:
                last_exc = exc
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)

        # All retries exhausted
        self._failed_reads += 1
        self._consecutive_failures += 1

        if self._consecutive_failures == 1 or self._consecutive_failures % 50 == 0:
            logger.warning(
                "%s: read failed (%d consecutive) — %s",
                self.__class__.__name__,
                self._consecutive_failures,
                last_exc or "returned None",
            )

        return None

    def close(self) -> None:
        """Release hardware resources. Override in subclasses that hold GPIO lines."""
        pass

    def __repr__(self) -> str:
        status = "live" if self._hw_available else "simulated"
        return f"<{self.__class__.__name__} pin={self.pin} {status}>"
