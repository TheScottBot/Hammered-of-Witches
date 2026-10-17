import os

os.environ["HAMMERED_NO_DOTENV"] = "1"  # Never read a real .env (or token) in the tests.

import pytest  # noqa: E402

from hammered import db, malleus  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.init(":memory:")
    malleus.recent.clear()
    yield
    db.conn.close()
