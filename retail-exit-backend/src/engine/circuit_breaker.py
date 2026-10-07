"""Inference Circuit Breaker & Watchdog Engine

Protects background CV workers against ONNX runtime stalls, memory exhaustions,
and hanging hardware threads using a 3-state circuit breaker (CLOSED, OPEN, HALF_OPEN).
"""

import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("secops.engine.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class InferenceCircuitBreaker:
    """Per-resource / per-model sliding circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_cooldown_sec: float = 30.0,
        half_open_success_threshold: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_cooldown_sec = recovery_cooldown_sec
        self.half_open_success_threshold = half_open_success_threshold

        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.state: CircuitState = CircuitState.CLOSED
        self.last_state_change: float = time.time()
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        """Determines if a request should be allowed through."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_cooldown_sec:
                logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN (cooldown elapsed).")
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self.consecutive_successes = 0
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Records a successful execution."""
        now = time.time()
        self.consecutive_failures = 0
        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.half_open_success_threshold:
                logger.info("Circuit breaker transitioning from HALF_OPEN to CLOSED (recovered).")
                self.state = CircuitState.CLOSED
                self.last_state_change = now

    def record_failure(self, error: Optional[Exception] = None):
        """Records a failed execution or timeout."""
        now = time.time()
        self.last_failure_time = now
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and self.consecutive_failures >= self.failure_threshold:
            logger.warning(
                "Circuit breaker tripped to OPEN after %d consecutive failures (error: %s). Cooldown: %.1fs.",
                self.consecutive_failures,
                error,
                self.recovery_cooldown_sec,
            )
            self.state = CircuitState.OPEN
            self.last_state_change = now

