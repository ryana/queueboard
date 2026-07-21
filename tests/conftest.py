import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:///./tmp/queueboard-test.db"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

import pytest
from fastapi.testclient import TestClient

from queueboard.database import Base, engine
from queueboard.main import app


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
