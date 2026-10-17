import pytest
import os

os.environ["ENVIRONMENT"] = "test"
os.environ["BOOTSTRAP_OWNER_EMAIL"] = "ces@gmail.com"
os.environ["BOOTSTRAP_OWNER_PASSWORD"] = "SecOps@2026MasterKey!"
os.environ["SECOPS_ENCRYPTION_KEYS"] = "eE1yNFZ2Q0U3clg1T2k5UFZ2cUZXTVpDSEU3YUJvV2M="
os.environ["SECRET_KEY"] = "SecOpsRemediationSecretKey2026ForTestingPurposesOnly32Bytes"

from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Base
from src.db.platform_models import PlatformBase, PlatformSuperAdmin, PlatformSubscriptionTier, PlatformTenant, PlatformStoreSubscription, PlatformBillingInvoice
from src.security import get_password_hash
from src.api.deps import get_db
import src.db.session
import src.core.multi_tenant
from src.core.config import settings
from httpx import AsyncClient, ASGITransport

TEST_DB_FILE = Path(__file__).resolve().parent / "test_temp.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

PLATFORM_TEST_DB_FILE = Path(__file__).resolve().parent / "test_platform_temp.db"
PLATFORM_TEST_DATABASE_URL = f"sqlite+aiosqlite:///{PLATFORM_TEST_DB_FILE}"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

platform_test_engine = create_async_engine(PLATFORM_TEST_DATABASE_URL, echo=False)
PlatformTestingSessionLocal = async_sessionmaker(bind=platform_test_engine, class_=AsyncSession, expire_on_commit=False)

# Override operational db session
src.db.session.engine = test_engine
src.db.session.async_engine = test_engine
src.db.session.AsyncSessionLocal = TestingSessionLocal
settings.DATABASE_URL = TEST_DATABASE_URL

# Override platform control-plane db session
src.core.multi_tenant.platform_engine = platform_test_engine
src.core.multi_tenant.PlatformAsyncSessionLocal = PlatformTestingSessionLocal
src.core.multi_tenant.PLATFORM_DATABASE_URL = PLATFORM_TEST_DATABASE_URL

from src.main import app


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with platform_test_engine.begin() as conn:
        await conn.run_sync(PlatformBase.metadata.drop_all)
        await conn.run_sync(PlatformBase.metadata.create_all)

    # Bootstrap default tiers and software owner in platform test DB
    async with PlatformTestingSessionLocal() as session:
        # Tiers
        t1 = PlatformSubscriptionTier(
            tier_id="tier_starter_01",
            name="Starter",
            max_cameras=4,
            price_cents=499900,
            currency="INR",
        )
        t2 = PlatformSubscriptionTier(
            tier_id="tier_pro_01",
            name="Professional",
            max_cameras=16,
            price_cents=1499900,
            currency="INR",
        )
        t3 = PlatformSubscriptionTier(
            tier_id="tier_enterprise_01",
            name="Enterprise",
            max_cameras=64,
            price_cents=4999900,
            currency="INR",
        )
        session.add_all([t1, t2, t3])

        # Software Owner ces@gmail.com
        owner = PlatformSuperAdmin(
            admin_id="admin_test_001",
            username="ces",
            email="ces@gmail.com",
            password_hash=get_password_hash("Ces@1234"),
            role="SUPER_ADMIN",
            is_active=True,
        )
        session.add(owner)
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with platform_test_engine.begin() as conn:
        await conn.run_sync(PlatformBase.metadata.drop_all)


@pytest.fixture(scope="session", autouse=True)
def cleanup_temp_db():
    yield
    for f in [TEST_DB_FILE, PLATFORM_TEST_DB_FILE]:
        if f.exists():
            try:
                os.remove(f)
            except Exception:
                pass


@pytest.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
