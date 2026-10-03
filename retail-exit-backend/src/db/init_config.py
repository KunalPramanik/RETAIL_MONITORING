from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import ThresholdConfig, User
from src.security import get_password_hash
import uuid

async def init_baseline_configuration(session: AsyncSession):
    # Ensure SUPER_ADMIN exists
    result = await session.execute(select(User).where(User.username == "admin"))
    if not result.scalars().first():
        hashed_password = get_password_hash("admin123")  # In production, require reset on first login
        admin_user = User(
            id=str(uuid.uuid4()),
            username="admin",
            hashed_password=hashed_password,
            role="SUPER_ADMIN",
            is_active=True
        )
        session.add(admin_user)

    # Base Threshold Config
    cfg = await session.execute(select(ThresholdConfig).where(ThresholdConfig.is_active == True))
    if not cfg.scalars().first():
        new_cfg = ThresholdConfig(
            config_id="TCFG-DEFAULT",
            base_confidence_threshold=0.65,
            high_severity_threshold=0.85,
            is_active=True
        )
        session.add(new_cfg)
        
    await session.commit()
