"""Unit Tests for Multi-Sensor Consensus Fusion Engine"""

import pytest
from src.engine.fusion import MultiSensorFusionEngine


def test_fusion_full_agreement():
    """All 3 channels in exact agreement should produce high confidence consensus."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=48,
        vision_confidence=0.98,
        rfid_count=48,
        rfid_confidence=0.95,
        weight_estimated_units=48,
        weight_confidence=0.90,
    )
    assert result.consensus_units == 48
    assert result.consensus_method == "weighted_vote_v2"
    assert result.disagreement_detected is False
    assert result.disagreement_type is None


def test_fusion_rfid_attenuation():
    """RFID attenuation should be detected and penalized in consensus."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=60,
        vision_confidence=0.98,
        rfid_count=50,  # 10 tags missing due to metal box shielding
        rfid_confidence=0.90,
        weight_estimated_units=60,
        weight_confidence=0.90,
    )
    # Majority consensus (Vision + Scale) overrides attenuated RFID
    assert result.consensus_units == 59 or result.consensus_units == 60
    assert result.disagreement_detected is True
    assert result.disagreement_type == "RFID_ATTENUATION"
    assert result.channel_readings["rfid"]["status"] == "ATTENUATED"


def test_fusion_partial_channels():
    """System should gracefully fuse when only vision channel is online."""
    result = MultiSensorFusionEngine.fuse(
        vision_count=36,
        vision_confidence=0.92,
        rfid_count=None,
        weight_estimated_units=None,
    )
    assert result.consensus_units == 36
    assert result.channel_readings["rfid"]["status"] == "OFFLINE"
    assert result.channel_readings["scale"]["status"] == "OFFLINE"

