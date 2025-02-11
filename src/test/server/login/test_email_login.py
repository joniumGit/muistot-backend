from urllib.parse import urlencode

import pytest
from fastapi import HTTPException, status
from headers import AUTHORIZATION

from login_urls import EMAIL_LOGIN, STATUS, EMAIL_EXCHANGE
from muistot.login.logic.email import create_email_verifier, fetch_user_by_email, can_send_email
from muistot.login.logic.email import send_login_email as send_email, hash_token
from muistot.config import Config


@pytest.mark.anyio
async def test_email(mail, db, user):
    await send_email(user.username, db, lang="en")
    email, data = mail.sends[0]

    assert email == user.email, f'{email}-{data}'
    assert "token" in data
    assert data["user"] == user.username
    assert not data["verified"]


@pytest.mark.anyio
async def test_email_timeout(mail, db, user):
    await send_email(user.username, db, lang="en")
    assert not await can_send_email(user.email, db)
    await db.execute(
        """
        UPDATE user_email_verifiers 
            SET created_at =  TIMESTAMPADD(MINUTE,-5,created_at) 
        WHERE user_id = (SELECT id FROM users WHERE username = :user)
        """,
        values=dict(user=user.username)
    )
    assert await can_send_email(user.email, db)


@pytest.mark.anyio
async def fetch_user(db, user):
    assert (await fetch_user_by_email(user.email, db)) == user.username
    assert (await fetch_user_by_email('a', db)) is None
    assert (await fetch_user_by_email(None, db)) is None


@pytest.mark.anyio
async def test_verifier(db, user):
    email, token, verified = await create_email_verifier(user.username, db)
    assert not verified
    assert email == user.email
    assert token is not None
    assert (await db.fetch_val(
        "SELECT COUNT(*) FROM user_email_verifiers WHERE verifier = :token",
        values=dict(token=token)
    )) == 0
    assert (await db.fetch_val(
        "SELECT COUNT(*) FROM user_email_verifiers WHERE verifier = :token",
        values=dict(token=hash_token(token))
    )) == 1


@pytest.mark.anyio
async def test_create_503(db, user):
    """If generation fails

    Although the email will fail here, the username should work too
    """
    from muistot.login.logic.login import try_create_user
    with pytest.raises(HTTPException) as e:
        await try_create_user(user.email, db, lang="en")
    assert e.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.anyio
async def test_email_login_timeout(non_existent_email, client, db):
    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    await db.execute("DELETE FROM user_email_verifiers")

    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.anyio
async def test_email_login_timeout_no_cache(non_existent_email, client):
    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    client.app.state.FastStorage.redis.flushdb()

    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.anyio
async def test_email_login_new_user(non_existent_email, client):
    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.anyio
async def test_email_login_full(non_existent_email, client, capture_mail):
    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    mail = capture_mail[("login", non_existent_email)]
    token = mail["token"]
    user = mail["user"]

    r = await client.post(f"{EMAIL_EXCHANGE}?{urlencode(dict(user=user, token=token))}")
    assert r.status_code == status.HTTP_200_OK
    assert AUTHORIZATION in r.headers
    auth = r.headers[AUTHORIZATION]

    r = await client.get(STATUS, headers={AUTHORIZATION: auth})
    assert r.status_code == status.HTTP_200_OK


@pytest.mark.anyio
async def test_email_token_not_exists(client, non_existent_email, capture_mail):
    r = await client.post(f"{EMAIL_LOGIN}?email={non_existent_email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    mail = capture_mail[("login", non_existent_email)]
    token = mail["token"]
    user = mail["user"]

    r = await client.post(f"{EMAIL_EXCHANGE}?{urlencode(dict(user=user, token=token[:-2]))}")
    assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_email_token_not_exists_not_unicode(client, user, capture_mail):
    r = await client.post(f"{EMAIL_EXCHANGE}?{urlencode(dict(user=user.username, token='ööööööääääää'))}")
    assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_namegen_no_more_names(client, user, non_existent_email, capture_mail):
    import httpx
    from muistot.config import Config

    with httpx.Client(base_url=Config.namegen.url) as c:
        c.post(f"/lock?{urlencode(dict(username=user.username))}")
        try:
            r = await client.post(f"{EMAIL_LOGIN}?{urlencode(dict(email=non_existent_email))}")
            assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        finally:
            c.post("/lock")


@pytest.mark.anyio
async def test_namegen_failure(client, non_existent_email, capture_mail):
    import httpx
    from muistot.config import Config

    with httpx.Client(base_url=Config.namegen.url) as c:
        c.post(f"/disable")
        try:
            r = await client.post(f"{EMAIL_LOGIN}?{urlencode(dict(email=non_existent_email))}")
            assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        finally:
            c.post("/disable")


@pytest.mark.anyio
async def test_email_login_non_verified_verifies(user, client, capture_mail, db):
    r = await client.post(f"{EMAIL_LOGIN}?email={user.email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    assert not await db.fetch_val(f"SELECT verified FROM users WHERE id = {user.id}")

    mail = capture_mail[("login", user.email)]
    token = mail["token"]

    r = await client.post(f"{EMAIL_EXCHANGE}?{urlencode(dict(user=user.username, token=token))}")
    assert r.status_code == status.HTTP_200_OK

    assert await db.fetch_val(f"SELECT verified FROM users WHERE id = {user.id}")


@pytest.mark.anyio
async def test_email_login_verified_ok(user, client, capture_mail, db):
    """Sanity check"""
    r = await client.post(f"{EMAIL_LOGIN}?email={user.email}")
    assert r.status_code == status.HTTP_204_NO_CONTENT

    await db.execute(f"UPDATE users SET verified = 1 WHERE id = {user.id}")

    token = capture_mail[("login", user.email)]["token"]
    r = await client.post(f"{EMAIL_EXCHANGE}?{urlencode(dict(user=user.username, token=token))}")
    assert r.status_code == status.HTTP_200_OK

    assert await db.fetch_val(f"SELECT verified FROM users WHERE id = {user.id}")


@pytest.mark.anyio
@pytest.mark.parametrize("lang, expected", [
    ("en-US,en;q=0.5", "en"),
    ("fi", "fi"),
    ("xwadwadwa", Config.localization.default),
])
async def test_email_templating_lang(user, client, capture_mail, lang, expected):
    from headers import CONTENT_LANGUAGE

    r = await client.post(f"{EMAIL_LOGIN}?email={user.email}", headers={CONTENT_LANGUAGE: lang})
    assert r.status_code == status.HTTP_204_NO_CONTENT

    assert capture_mail[("login", user.email)]["lang"] == expected
