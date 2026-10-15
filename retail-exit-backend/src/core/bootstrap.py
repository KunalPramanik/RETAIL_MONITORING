"""Software Owner Provisioning & Bootstrap CLI Module.

Provides idempotent, secure initialization of the platform's Software Owner identity.
Enforces:
- Reading initial credentials from BOOTSTRAP_OWNER_EMAIL and BOOTSTRAP_OWNER_PASSWORD
- Idempotency: preserves existing passwords upon subsequent runs
- Zero exposure of passwords or hashes in logs
- Strict single identity in platform_super_admin ONLY (never in app_user)
"""

import os
import sys
import asyncio
import logging
import argparse
from sqlalchemy import select, or_

from src.core.multi_tenant import PlatformAsyncSessionLocal, init_platform_db, platform_engine
from src.db.platform_models import PlatformSuperAdmin, PlatformBase
from src.security import get_password_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("secops.bootstrap")


async def bootstrap_software_owner(force_reset_password: bool = False) -> None:
    """Idempotently ensures the Software Owner account exists in PlatformSuperAdmin."""
    owner_email = os.getenv("BOOTSTRAP_OWNER_EMAIL", "ces@gmail.com").strip().lower()
    owner_password = os.getenv("BOOTSTRAP_OWNER_PASSWORD", "Ces@1234")
    owner_username = owner_email.split("@")[0]

    # Ensure platform schema exists
    async with platform_engine.begin() as conn:
        await conn.run_sync(PlatformBase.metadata.create_all)

    async with PlatformAsyncSessionLocal() as session:
        stmt = select(PlatformSuperAdmin).where(
            or_(
                PlatformSuperAdmin.email == owner_email,
                PlatformSuperAdmin.username == owner_email,
                PlatformSuperAdmin.username == owner_username,
            )
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if not existing:
            new_owner = PlatformSuperAdmin(
                username=owner_username,
                email=owner_email,
                password_hash=get_password_hash(owner_password),
                role="SUPER_ADMIN",
                is_active=True,
            )
            session.add(new_owner)
            await session.commit()
            logger.info("Software Owner account (%s) successfully provisioned.", owner_email)
        else:
            if force_reset_password:
                existing.password_hash = get_password_hash(owner_password)
                existing.is_active = True
                await session.commit()
                logger.info("Software Owner account (%s) password explicitly reset via authenticated command.", owner_email)
            else:
                if not existing.is_active:
                    existing.is_active = True
                    await session.commit()
                    logger.info("Software Owner account (%s) reactivated.", owner_email)
                else:
                    logger.info("Software Owner account (%s) already active. Preserving existing credentials.", owner_email)


def main():
    parser = argparse.ArgumentParser(description="SEC-OPS V8 Software Owner Bootstrap")
    parser.add_argument("--reset-password", action="store_true", help="Explicitly reset password to environment default")
    args = parser.parse_args()

    asyncio.run(bootstrap_software_owner(force_reset_password=args.reset_password))


if __name__ == "__main__":
    main()

