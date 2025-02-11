import pytest
from muistot.database import Databases, Database, OperationalError, DatabaseProvider


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def db_instance(anyio_backend) -> DatabaseProvider:
    inst = Databases.default.database
    while True:
        try:
            await inst.connect()
            break
        except OperationalError:
            pass
    try:
        yield inst
    finally:
        await inst.disconnect()
        del inst


@pytest.fixture(scope="function")
async def db(db_instance) -> Database:
    async with db_instance() as c:
        await c.execute('ROLLBACK')
        await c.execute('SET autocommit = 1')
        yield c
        # Return to right state
        await c.execute('SET autocommit = 0')


@pytest.fixture(scope="function")
async def rollback(db):
    await db.execute('COMMIT')
    await db.execute('SET autocommit = 0')
    await db.execute('BEGIN')
    yield db
    await db.execute('ROLLBACK')
