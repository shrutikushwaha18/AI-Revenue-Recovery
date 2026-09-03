import os
import shutil
import tempfile


_test_database_dir = tempfile.mkdtemp(prefix="recoverai-tests-")
os.environ.pop("DATABASE_URL", None)
os.environ["SQLITE_DB_PATH"] = os.path.join(_test_database_dir, "recoverai-test.db")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_test_database_dir, ignore_errors=True)
