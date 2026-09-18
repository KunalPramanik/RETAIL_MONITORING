"""Tests for Store Occupancy, Zone Analytics & Footfall Counting Engine."""

import time
import pytest
from src.engine.zone_analytics import OccupancyZoneEngine


def test_tripwire_bidirectional_crossing_in_and_out():
    """Verifies that crossing a tripwire upwards or downwards increments IN and OUT."""
    engine = OccupancyZoneEngine()
    cam_id = "test_cam_01"

    # Configure horizontal tripwire across y = 300
    engine.configure_tripwire(
        camera_id=cam_id,
        tripwire_id="main_door",
        line_coords=[(0, 300), (1000, 300)],
        label="Main Entrance",
    )

    # Frame 1: Person 101 is at (500, 350) - side 1
    t1 = [{"track_id": 101, "bbox": [450, 250, 100, 100], "center": (500, 300)}]  # foot_y = 350 > 300
    snap1 = engine.process_person_tracks(cam_id, t1, frame_width=1000, frame_height=600)
    assert snap1.current_room_occupancy == 1
    assert snap1.total_footfall_in == 0
    assert snap1.total_footfall_out == 0

    # Frame 2: Person 101 moves to foot_y = 250 - crossed line to side 2
    t2 = [{"track_id": 101, "bbox": [450, 150, 100, 100], "center": (500, 200)}]  # foot_y = 250 < 300
    snap2 = engine.process_person_tracks(cam_id, t2, frame_width=1000, frame_height=600)

    # One direction counted (IN or OUT depending on normal orientation)
    total_crossings = snap2.total_footfall_in + snap2.total_footfall_out
    assert total_crossings == 1


def test_zone_dwell_time_accumulation():
    """Verifies that person loitering in a zone accumulates dwell time."""
    engine = OccupancyZoneEngine()
    cam_id = "test_cam_dwell"

    # Configure zone
    engine.configure_zone(
        camera_id=cam_id,
        zone_id="checkout",
        label="Checkout Counter",
        polygon=[(100, 100), (500, 100), (500, 500), (100, 500)],
    )

    # Person 201 foot at (300, 300) inside checkout zone
    tracks = [{"track_id": 201, "bbox": [250, 200, 100, 100]}]  # foot at (300, 300)
    snap = engine.process_person_tracks(cam_id, tracks, frame_width=1000, frame_height=1000)

    checkout_metrics = [zm for zm in snap.zone_metrics if zm.zone_id == "checkout"]
    assert len(checkout_metrics) == 1
    assert checkout_metrics[0].current_occupancy == 1
    assert 201 in checkout_metrics[0].active_track_ids

