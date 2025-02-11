import pytest
from fastapi import status
from headers import LOCATION, ACCEPT_LANGUAGE

from utils import *


@pytest.fixture(name="setup")
async def setup(repo_config, db):
    pid = await create_project(db, repo_config)
    yield Setup(pid)
    await db.execute("DELETE FROM projects WHERE name = :project", dict(project=pid))


@pytest.fixture
async def pid(db):
    from passlib.pwd import genword
    id_ = genword(length=25)
    yield id_
    await db.execute("DELETE FROM projects WHERE name = :id", values=dict(id=id_))


@pytest.mark.anyio
async def make_project(pid, client, superuser, **props):
    """Create project with given props and ensure it shows up
    """
    m = NewProject(
        id=pid,
        info=ProjectInfo(
            lang="en",
            name=" Test Project ",
            abstract=" Test Abstract ",
            description=" Test Description "
        ),
        **props
    )
    r = await client.post(PROJECTS, json=m.dict(), headers=superuser)
    check_code(status.HTTP_201_CREATED, r)

    # Check project
    p = to(Project, await client.get(r.headers[LOCATION], headers=superuser))
    assert any(map(lambda prj: prj.id == p.id, to(Projects, await client.get(PROJECTS, headers=superuser)).items))
    assert p.id == m.id  # Cool id
    assert p.info.name == m.info.name.strip()  # Properties without whitespace
    assert p.info.abstract == m.info.abstract.strip()
    assert p.info.description == m.info.description.strip()
    return p


#        ___           ___           ___           ___           ___
#       /\  \         /\  \         /\  \         /\  \         /\  \
#      /::\  \        \:\  \       /::\  \       /::\  \        \:\  \
#     /:/\ \  \        \:\  \     /:/\:\  \     /:/\:\  \        \:\  \
#    _\:\~\ \  \       /::\  \   /::\~\:\  \   /::\~\:\  \       /::\  \
#   /\ \:\ \ \__\     /:/\:\__\ /:/\:\ \:\__\ /:/\:\ \:\__\     /:/\:\__\
#   \:\ \:\ \/__/    /:/  \/__/ \/__\:\/:/  / \/_|::\/:/  /    /:/  \/__/
#    \:\ \:\__\     /:/  /           \::/  /     |:|::/  /    /:/  /
#     \:\/:/  /     \/__/            /:/  /      |:|\/__/     \/__/
#      \::/  /                      /:/  /       |:|  |
#       \/__/                       \/__/         \|__|


@pytest.mark.anyio
async def test_project_406_edge_case(pid, client, username, db):
    """
    It is possible to insert bad values to the database manually.

    This tests they are correctly handled.
    """
    await db.execute(
        """
        INSERT INTO projects (
            name, 
            published, 
            default_language_id
        ) 
        VALUE (
            :pname,
             1, 
             1
        )
        """,
        values=dict(pname=pid),
    )
    r = await client.get(PROJECT.format(pid))
    check_code(status.HTTP_406_NOT_ACCEPTABLE, r)


@pytest.mark.anyio
async def test_project_create(pid, client, superuser, auto_publish):
    """Simple creation test
    """
    await make_project(pid, client, superuser)


@pytest.mark.anyio
async def test_project_delete(pid, client, superuser, db, auto_publish):
    """Tests soft delete
    """
    await make_project(pid, client, superuser)

    r = await client.delete(PROJECT.format(pid), headers=superuser)
    assert r.status_code == status.HTTP_204_NO_CONTENT

    loc = r.headers[LOCATION]
    assert loc.endswith("projects")
    for p in Projects(**(await client.get(loc)).json()).items:
        assert p.id != pid

    r = await client.get(PROJECT.format(pid))
    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
    assert await db.fetch_val(
        "SELECT NOT published FROM projects WHERE name = :project",
        values=dict(project=pid)
    )


@pytest.mark.anyio
async def test_project_superuser_fetch_deleted_ok(setup, client, superuser, db):
    """Superusers can fetch deleted projects
    """
    pid = setup.project

    await db.execute("UPDATE projects SET published = 0 WHERE name = :project", values=dict(project=pid))
    r = await client.get(PROJECT.format(pid))

    assert r.status_code == status.HTTP_404_NOT_FOUND, r.text
    r = await client.get(PROJECT.format(pid), headers=superuser)
    assert r.status_code == status.HTTP_200_OK, r.text


@pytest.mark.anyio
async def test_project_admin_double_add_fail(client, setup, superuser, username):
    """Admin double add should fail with proper code
    """
    pid = setup.project

    r = await client.post(ADMINS.format(pid), params=dict(username=username), headers=superuser)
    assert r.status_code == status.HTTP_201_CREATED, r.text

    r = await client.post(ADMINS.format(pid), params=dict(username=username), headers=superuser)
    assert r.status_code == status.HTTP_409_CONFLICT, r.text
    assert to(Project, await client.get(PROJECT.format(pid))).admins == [username]


@pytest.mark.anyio
async def test_project_admin_double_delete_ok(client, setup, superuser, username):
    """Deletion says ok always
    """
    await test_project_admin_double_add_fail(client, setup, superuser, username)
    pid = setup.project

    r = await client.delete(ADMINS.format(pid), params=dict(username=username), headers=superuser)
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text

    r = await client.delete(ADMINS.format(pid), params=dict(username=username), headers=superuser)
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text
    assert to(Project, await client.get(PROJECT.format(pid))).admins == []


@pytest.mark.anyio
async def test_project_image_delete(pid, client, superuser, image, auto_publish):
    """Images should be fetched and saved properly

    And deleted upon setting null
    """
    # Create
    p = await make_project(pid, client, superuser, image=image)
    assert p.image is not None

    # Modify to null
    r = await client.patch(PROJECT.format(p.id), json={"image": None}, headers=superuser)
    check_code(status.HTTP_204_NO_CONTENT, r)

    # Check deleted
    assert to(Project, await client.get(r.headers[LOCATION])).image is None, r.text


@pytest.mark.anyio
async def test_project_localize_no_auth(setup, client, superuser):
    """Fail on missing auth
    """
    data = ModifiedProject(
        info=ProjectInfo(name="a", lang="eng", description="a", abstract="b")
    ).json(exclude_unset=True)

    # No Auth
    r = await client.patch(PROJECT.format(setup.project), content=data)
    check_code(status.HTTP_401_UNAUTHORIZED, r)


@pytest.mark.anyio
async def test_project_localize_new(setup, client, superuser):
    """Create new localization
    """
    data = ModifiedProject(
        info=ProjectInfo(name="awaddawda", lang="fi", description="adaw", abstract="bdwadw")
    ).dict(exclude_unset=True)

    headers = dict()
    headers[ACCEPT_LANGUAGE] = "fi"

    r = await client.patch(PROJECT.format(setup.project), json=data, headers=superuser)
    check_code(status.HTTP_204_NO_CONTENT, r)
    assert to(Project, await client.get(r.headers[LOCATION], headers=headers)).info.dict() == data["info"]


@pytest.mark.anyio
async def test_porject_unknown_locale(setup, client):
    """Test unsupported locale
    """
    r = await client.get(PROJECT.format(setup.project), headers={ACCEPT_LANGUAGE: "az"})
    check_code(status.HTTP_406_NOT_ACCEPTABLE, r)


@pytest.mark.anyio
async def test_project_bad_language(client, superuser):
    """Test unsupported language
    """
    r = await client.post(PROJECTS, json=NewProject(
        id=genword(length=10),
        info=ProjectInfo.construct(lang="az", name="test"),
    ).dict(), headers=superuser)
    check_code(status.HTTP_406_NOT_ACCEPTABLE, r)


@pytest.mark.anyio
async def test_project_publish_admin_another_project_fails(db, pid, client, setup, users):
    """All admin calls go through to publish but should reject if admin is not from current project
    """
    user = users[1]

    _id = await db.fetch_val(
        """
        INSERT INTO projects (name, default_language_id) VALUE (:id, 1) RETURNING id
        """,
        values=dict(id=pid)
    )
    await db.execute(
        """
        INSERT INTO project_admins (project_id, user_id) SELECT :pid, id FROM users WHERE username = :user
        """,
        values=dict(pid=_id, user=user.username)
    )

    auth_header = await authenticate(client, user.username, user.password)

    r = await client.post(
        PUBLISH,
        json={
            "type": "project",
            "identifier": setup.project
        },
        headers=auth_header
    )

    check_code(status.HTTP_403_FORBIDDEN, r)


@pytest.mark.anyio
async def test_project_publish(pid, client, superuser):
    await make_project(pid, client, superuser)

    r = await client.post(PUBLISH_PROJECT.format(pid, True), headers=superuser)
    check_code(status.HTTP_204_NO_CONTENT, r)

    r = await client.get(PROJECT.format(pid))
    check_code(status.HTTP_200_OK, r)

    r = await client.post(PUBLISH_PROJECT.format(pid, False), headers=superuser)
    check_code(status.HTTP_204_NO_CONTENT, r)

    r = await client.get(PROJECT.format(pid))
    check_code(status.HTTP_404_NOT_FOUND, r)


@pytest.mark.anyio
async def test_project_double_publish_no_change(pid, client, superuser, db):
    await make_project(pid, client, superuser)

    r = await client.post(PUBLISH_PROJECT.format(pid, True), headers=superuser)
    check_code(status.HTTP_204_NO_CONTENT, r)
    assert await db.fetch_val("SELECT published FROM projects WHERE name =:pid", values=dict(pid=pid))
    r = await client.post(PUBLISH_PROJECT.format(pid, True), headers=superuser)
    check_code(status.HTTP_304_NOT_MODIFIED, r)


@pytest.mark.anyio
async def test_admin_sees_unpublished(pid, client, superuser, users):
    u2 = users[2]
    await make_project(pid, client, superuser, admins=[u2.username])

    aauth = await authenticate(client, u2.username, u2.password)
    r = await client.get(PROJECT.format(pid), headers=aauth)
    check_code(status.HTTP_200_OK, r)
    assert any(map(lambda prj: prj.id == pid, to(Projects, await client.get(PROJECTS, headers=aauth)).items))


@pytest.mark.anyio
async def test_user_does_not_see_unpublished(pid, client, superuser, users):
    u2 = users[2]
    await make_project(pid, client, superuser)

    aauth = await authenticate(client, u2.username, u2.password)
    r = await client.get(PROJECT.format(pid), headers=aauth)
    check_code(status.HTTP_404_NOT_FOUND, r)
    assert all(map(lambda prj: prj.id != pid, to(Projects, await client.get(PROJECTS, headers=aauth)).items))


@pytest.mark.anyio
async def test_admin_not_exists_fails(pid, client, superuser):
    m = NewProject(
        id=pid,
        info=ProjectInfo(
            lang="en",
            name=" Test Project ",
            abstract=" Test Abstract ",
            description=" Test Description "
        ),
        admins=["wadwdawdawdawdawdawdaddawda"]
    )
    r = await client.post(PROJECTS, json=m.dict(), headers=superuser)
    check_code(status.HTTP_404_NOT_FOUND, r)


@pytest.mark.anyio
async def test_admin_not_exists_fails_on_add(pid, client, superuser):
    await make_project(pid, client, superuser)
    r = await client.post(ADMINS.format(pid), params=dict(username="adadwadwadawdawdadw"), headers=superuser)
    check_code(status.HTTP_404_NOT_FOUND, r)


@pytest.mark.anyio
async def test_admin_not_exists_fails_on_delete(pid, client, superuser):
    await make_project(pid, client, superuser)
    r = await client.delete(ADMINS.format(pid), params=dict(username="adadwadwadawdawdadw"), headers=superuser)
    check_code(status.HTTP_404_NOT_FOUND, r)
