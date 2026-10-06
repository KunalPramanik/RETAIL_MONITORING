"""Automated Tests for Degraded-Mode Multi-Sensor Fusion Engine

Validates:
1. Single-channel degraded mode: confidence mathematically capped at <= 0.75.
2. Occlusion detection: rfid > vision flags VISION_OCCLUSION.
3. Faraday attenuation: rfid < vision flags RFID_ATTENUATION with majority consensus fallback.
4. Scale & vision concordant agreement overriding attenuated RFID.
5. All three channels in full parity consensus.
"""

from src.engine.fusion import MultiSensorFusionEngine


def test_single_channel_vision_degraded_capping():
    """When only Computer Vision is online (no RFID gate, no Scale), confidence must be capped at <= 0.75."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=10,
        vision_confidence=0.99,  # High raw vision confidence
        rfid_count=None,
        weight_estimated_units=None,
    )
    assert result.consensus_units == 10
    assert result.confidence <= 0.75, f"Expected confidence capped at <= 0.75, got {result.confidence}"
    assert result.channel_readings["rfid"]["status"] == "OFFLINE"
    assert result.channel_readings["scale"]["status"] == "OFFLINE"


def test_vision_occlusion_flagged():
    """When RFID tag count exceeds visible boxes, flag VISION_OCCLUSION."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=8,
        vision_confidence=0.85,
        rfid_count=12,  # 4 items obscured behind other boxes
        rfid_confidence=0.95,
    )
    assert result.disagreement_detected is True
    assert result.disagreement_type == "VISION_OCCLUSION"


def test_rfid_attenuation_majority_override():
    """When RFID is shielded (e.g. metallic or liquid), vision and floor scale override RFID."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=20,
        vision_confidence=0.90,
        rfid_count=14,  # 6 tags failed to read due to liquid shielding
        rfid_confidence=0.90,
        weight_estimated_units=20,  # Floor scale confirms 20 units
        weight_confidence=0.90,
    )
    assert result.consensus_units == 20
    assert result.disagreement_detected is True
    assert result.disagreement_type == "RFID_ATTENUATION"
    assert result.confidence >= 0.95


def test_full_tri_sensor_parity():
    """When all three channels agree identically, high confidence full consensus."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=15,
        vision_confidence=0.95,
        rfid_count=15,
        rfid_confidence=0.95,
        weight_estimated_units=15,
        weight_confidence=0.95,
    )
    assert result.consensus_units == 15
    assert result.disagreement_detected is False
    assert result.disagreement_type is None
    assert result.confidence >= 0.99
