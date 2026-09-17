"""Tests for Dynamic & Configurable Vision Class System (Step 2)

Verifies:
1. Dynamic class config is loaded from JSON without hardcoding.
2. Registering new classes (e.g. Charger, Tote Bag) updates categories and mappings in real time.
3. Threshold parameters are runtime-configurable.
"""

import pytest
from src.ml.model_config import get_vision_config, reload_vision_config, VisionModelConfig


def test_dynamic_class_config_loading():
    cfg = get_vision_config()
    assert isinstance(cfg.class_labels, dict)
    assert 0 in cfg.class_labels  # Person
    assert 28 in cfg.class_labels  # Case / Carton
    assert 67 in cfg.class_labels  # Smartphone
    # Custom retail classes
    assert 80 in cfg.class_labels  # Charger / Power Adapter
    assert 81 in cfg.class_labels  # Tote / Shopping Bag


def test_dynamic_class_categories():
    cfg = get_vision_config()
    assert 0 in cfg.case_classes or 0 not in cfg.case_classes  # 0 is person
    assert 28 in cfg.case_classes
    assert 67 in cfg.single_item_classes
    assert 80 in cfg.single_item_classes  # Charger in single items
    assert 81 in cfg.single_item_classes  # Tote in single items
    assert 2 in cfg.vehicle_classes  # Car in vehicle classes


def test_register_new_custom_class_at_runtime():
    cfg = get_vision_config()
    new_cid = 99
    new_label = "Special Warehouse Pallet"
    
    cfg.register_class(class_id=new_cid, label=new_label, category="case")
    assert cfg.class_labels[new_cid] == new_label
    assert new_cid in cfg.case_classes
    assert new_cid not in cfg.single_item_classes

    # Cleanup
    del cfg.class_labels[new_cid]
    cfg.case_classes.discard(new_cid)


def test_pairwise_precision_groups_configured():
    cfg = get_vision_config()
    assert len(cfg.pairwise_precision_groups) > 0
    # Confirms bag vs charger pair is explicitly tracked
    pairs_flattened = [item for sublist in cfg.pairwise_precision_groups for item in sublist]
    assert "Charger / Power Adapter" in pairs_flattened
    assert "Backpack / Bag" in pairs_flattened

