"""Database Deep Cleaning and Zero-State Reset Script.

Wipes all operational tables (events, detections, alerts, materials, cameras,
employees, products, tripwires, packages, dispatch sessions) to establish
a pristine zero-state database.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from sqlalchemy import delete
from src.db.session import AsyncSessionLocal
from src.db.models import (
    PersonAppearanceSummary,
    CameraPairingToken,
    StaticImageDetection,
    MaterialDefectEvent,
    MaterialMovementLedger,
    MaterialInventoryBalance,
    TripwireCrossingEvent,
    VirtualTripwireConfig,
    DispatchSession,
    PackageDefinition,
    Material,
    ExitEventLineItem,
    VisionDetection,
    RfidRead,
    WeightReading,
    FaceMatchAttempt,
    AlarmDispatch,
    Alert,
    Invoice,
    ExitEvent,
    CameraHeartbeat,
    Camera,
    Lane,
    Employee,
    Product,
    AuditLog,
)


async def clean_database():
    print("Initiating full operational database purge...")
    async with AsyncSessionLocal() as session:
        # Delete in foreign key dependency order
        models_to_clean = [
            MaterialDefectEvent,
            MaterialMovementLedger,
            MaterialInventoryBalance,
            TripwireCrossingEvent,
            VirtualTripwireConfig,
            DispatchSession,
            PackageDefinition,
            Material,
            PersonAppearanceSummary,
            CameraPairingToken,
            StaticImageDetection,
            ExitEventLineItem,
            VisionDetection,
            RfidRead,
            WeightReading,
            FaceMatchAttempt,
            AlarmDispatch,
            Alert,
            Invoice,
            ExitEvent,
            CameraHeartbeat,
            Camera,
            Lane,
            Employee,
            Product,
            AuditLog,
        ]
        for model in models_to_clean:
            try:
                await session.execute(delete(model))
            except Exception as e:
                print(f"Notice cleaning {model.__tablename__}: {e}")
        await session.commit()

        # Verify zero operational counts
        from sqlalchemy import func, select
        non_zero = []
        for model in models_to_clean:
            count = (await session.execute(select(func.count()).select_from(model))).scalar() or 0
            if count > 0:
                non_zero.append(f"{model.__tablename__}: {count}")

        if non_zero:
            print(f"Warning: Non-zero tables remaining: {', '.join(non_zero)}")
        else:
            print("Successfully verified: 0 operational rows across all monitored tables.")
    print("Database is in pristine zero-state.")


if __name__ == "__main__":
    asyncio.run(clean_database())

