"""Select an owned test database before any test imports the application."""
import os
from pathlib import Path
from uuid import uuid4

import pytest

TEST_ROOT = Path("E:/BrainFusion-Runtime/tmp/pytest")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_DB = TEST_ROOT / ("suite_" + uuid4().hex + ".db")
os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()
os.environ["FEATURE_JOBS_DIR"] = str(TEST_ROOT / ("features_" + TEST_DB.stem))
# CLI child processes inherit this isolated root too; never leave fixture jobs
# in the registered runtime directory after persistent conversion was added.
CONVERSION_TEST_ROOT = TEST_ROOT / ("conversion_" + TEST_DB.stem)
CONVERSION_TEST_ROOT.mkdir()
os.environ["DICOM_CONVERSION_INDEX_FILE"] = str(CONVERSION_TEST_ROOT / "index.json")
os.environ["PACS_IMPORT_REGISTRY_FILE"] = str(TEST_ROOT / ("pacs_registry_" + TEST_DB.stem + '.json'))
os.environ["PACS_IMPORT_JOBS_DIR"] = str(TEST_ROOT / ("pacs_imports_" + TEST_DB.stem))


@pytest.fixture(scope="session", autouse=True)
def cleanup_owned_test_database():
    yield
    from app.database import engine
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)
