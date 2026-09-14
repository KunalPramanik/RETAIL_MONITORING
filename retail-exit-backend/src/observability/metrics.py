"""Observability & Telemetry Metrics Module

Exposes Prometheus formatted telemetry metrics for exit throughput, model latencies,
camera uptime ratio, model confidence drift, and alarm dispatch success rates.
Adheres strictly to the Zero-Hardcode policy (0 baseline mock constants).
"""

from typing import Dict, Any


class MetricsCollector:
    _instance = None
    events_total: int
    mismatches_total: int
    alarms_high_total: int
    vision_latency_sum_ms: float
    vision_inferences_total: int
    confidence_sum: float
    confidence_count: int
    dispatches_total: int
    dispatches_success: int
    cameras_online: int
    cameras_total: int
    silent_lanes_total: int

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Pure dynamic counters initialized to zero
            cls._instance.events_total = 0
            cls._instance.mismatches_total = 0
            cls._instance.alarms_high_total = 0
            cls._instance.vision_latency_sum_ms = 0.0
            cls._instance.vision_inferences_total = 0
            cls._instance.confidence_sum = 0.0
            cls._instance.confidence_count = 0
            cls._instance.dispatches_total = 0
            cls._instance.dispatches_success = 0
            cls._instance.cameras_online = 0
            cls._instance.cameras_total = 0
            cls._instance.silent_lanes_total = 0
        return cls._instance

    def record_event(
        self,
        is_mismatch: bool,
        is_high_alarm: bool,
        vision_latency_ms: float = 0.0,
        confidence: float = 0.0,
    ):
        """Records telemetry for an exit traversal event."""
        self.events_total += 1
        if is_mismatch:
            self.mismatches_total += 1
        if is_high_alarm:
            self.alarms_high_total += 1
        if vision_latency_ms > 0:
            self.vision_inferences_total += 1
            self.vision_latency_sum_ms += vision_latency_ms
        if confidence > 0:
            self.confidence_sum += confidence
            self.confidence_count += 1

    def record_dispatch(self, success: bool = True):
        """Records outcome of an actuator / alarm dispatch attempt."""
        self.dispatches_total += 1
        if success:
            self.dispatches_success += 1

    def update_camera_fleet(self, online: int, total: int):
        """Updates camera fleet health metrics."""
        self.cameras_online = online
        self.cameras_total = total

    def generate_prometheus_text(self) -> str:
        """Generates pure dynamic Prometheus text output with zero hardcoded values."""
        avg_vision_latency = (
            self.vision_latency_sum_ms / max(1, self.vision_inferences_total)
        )
        avg_confidence = (
            self.confidence_sum / max(1, self.confidence_count)
            if self.confidence_count > 0
            else 0.0
        )
        camera_uptime_ratio = (
            self.cameras_online / max(1, self.cameras_total)
            if self.cameras_total > 0
            else 0.0
        )
        dispatch_success_ratio = (
            self.dispatches_success / max(1, self.dispatches_total)
            if self.dispatches_total > 0
            else 1.0
        )

        lines = [
            "# HELP secops_events_total Total number of exit events processed",
            "# TYPE secops_events_total counter",
            f"secops_events_total {self.events_total}",
            "",
            "# HELP secops_mismatches_total Total number of detected inventory discrepancies",
            "# TYPE secops_mismatches_total counter",
            f"secops_mismatches_total {self.mismatches_total}",
            "",
            "# HELP secops_alarms_high_total High severity siren and turnstile lock alarms",
            "# TYPE secops_alarms_high_total counter",
            f"secops_alarms_high_total {self.alarms_high_total}",
            "",
            "# HELP secops_vision_inference_latency_ms Average YOLOv8 inference latency in ms",
            "# TYPE secops_vision_inference_latency_ms gauge",
            f"secops_vision_inference_latency_ms {avg_vision_latency:.2f}",
            "",
            "# HELP secops_model_confidence_average Rolling average detection confidence",
            "# TYPE secops_model_confidence_average gauge",
            f"secops_model_confidence_average {avg_confidence:.4f}",
            "",
            "# HELP secops_camera_uptime_ratio Online camera fraction across fleet",
            "# TYPE secops_camera_uptime_ratio gauge",
            f"secops_camera_uptime_ratio {camera_uptime_ratio:.4f}",
            "",
            "# HELP secops_alarm_dispatch_success_ratio Ratio of successful actuator dispatches",
            "# TYPE secops_alarm_dispatch_success_ratio gauge",
            f"secops_alarm_dispatch_success_ratio {dispatch_success_ratio:.4f}",
            "",
            "# HELP secops_silent_lanes_total Registered lanes exceeding heartbeat timeout",
            "# TYPE secops_silent_lanes_total gauge",
            f"secops_silent_lanes_total {self.silent_lanes_total}",
        ]
        return "\n".join(lines) + "\n"


metrics = MetricsCollector()
