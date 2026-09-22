"""Tests for Automated Model Fine-Tuning & Step 5 Gate Verification Pipeline

Verifies:
1. FineTuningService initialization and status reporting.
2. Fine-tuning simulation with loss convergence and checkpoint generation.
3. Step 5 promotion gate verification on fine-tuned weights.
4. Candidate registration in ModelRegistry.
5. Endpoints /ml/train, /ml/train/status, /ml/train/cancel, and /ml/evaluate-checkpoint.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.ml.training.trainer import FineTuningService, fine_tuning_service
from src.ml.model_registry import ModelRegistry


@pytest.fixture
def clean_service():
    service = FineTuningService.get_instance()
    service._current_job = None
    service._cancel_requested = False
    return service


@pytest.mark.asyncio
async def test_fine_tuning_service_lifecycle(clean_service):
    """Verifies that start_training executes epochs, saves checkpoint, and registers candidate."""
    progress = await clean_service.start_training(
        epochs=3,
        learning_rate=0.002,
        batch_size=8,
        auto_promote=False,
        auto_shadow=False,
    )

    assert progress.status == "COMPLETED"
    assert progress.current_epoch == 3
    assert progress.total_epochs == 3
    assert progress.progress_pct == 100.0
    assert progress.train_loss < 2.0  # Loss should decrease
    assert progress.candidate_version is not None
    assert progress.passed_gates is True
    assert progress.metrics is not None
    assert progress.metrics["map_50"] >= 0.75
    assert progress.metrics["case_unit_recall"] >= 0.90
    assert progress.metrics["empty_scene_fp_rate"] <= 0.05
    assert progress.metrics["pairwise_precision"] >= 0.80

    # Verify model is registered in ModelRegistry
    registry = ModelRegistry.get_instance()
    assert progress.candidate_version in registry.models
    candidate = registry.models[progress.candidate_version]
    assert candidate.status == "candidate"
    assert candidate.metrics.map_50 >= 0.75


@pytest.mark.asyncio
async def test_fine_tuning_cancel(clean_service):
    """Verifies that cancel_job stops an active job."""
    import asyncio
    # When no job is active
    success, msg = clean_service.cancel_job()
    assert not success

    # Start a longer job and cancel it
    task = asyncio.create_task(clean_service.start_training(epochs=20))
    await asyncio.sleep(0.05)
    clean_service.cancel_job()
    result = await task

    assert result.status == "CANCELLED"


@pytest.mark.asyncio
async def test_training_api_endpoints():
    """Verifies REST API endpoints for training lifecycle."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Get initial status
        res_status = await ac.get("/api/ml/train/status")
        assert res_status.status_code == 200
        assert "status" in res_status.json()

        # 2. Launch training job
        res_train = await ac.post("/api/ml/train", json={
            "epochs": 2,
            "learning_rate": 0.001,
            "batch_size": 16,
            "auto_promote": False,
            "auto_shadow": True,
            "shadow_traffic_pct": 20.0,
        })
        assert res_train.status_code == 200
        assert res_train.json()["success"] is True

        # Wait briefly for execution
        import asyncio
        await asyncio.sleep(0.5)

        # 3. Check status
        res_status2 = await ac.get("/api/ml/train/status")
        assert res_status2.status_code == 200
        status_data = res_status2.json()
        assert status_data["status"] in ("PREPARING", "TRAINING", "EVALUATING", "COMPLETED")
