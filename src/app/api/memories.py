from .common_imports import *

router = APIRouter()


@router.get('/projects/{project}/sites/{site}/memories')
async def get_memories(r: Request, project: PID, site: SID, db: Database = Depends(dba)) -> List[Memory]:
    repo = MemoryRepo(db, project, site)
    repo.set_user(r.user)
    return await repo.all()


@router.get('/projects/{project}/sites/{site}/memories/{memory}')
async def get_memory(r: Request, project: PID, site: SID, memory: MID, db: Database = Depends(dba)) -> Memory:
    repo = MemoryRepo(db, project, site)
    repo.set_user(r.user)
    return await repo.one(memory)


@router.post('/projects/{project}/sites/{site}/memories')
async def new_memory(
        r: Request,
        project: PID,
        site: SID,
        model: NewMemory,
        db: Database = Depends(dba)
) -> JSONResponse:
    repo = MemoryRepo(db, project, site)
    repo.set_user(r.user)
    new_id = await repo.create(model)
    return created(router.url_path_for('get_memory', project=project, site=site, memory=str(new_id)))


@router.patch('/projects/{project}/sites/{site}/memories/{memory}')
@require_auth(scopes.AUTHENTICATED)
async def modify_memory(
        r: Request,
        project: PID,
        site: SID,
        memory: MID,
        model: ModifiedMemory,
        db: Database = Depends(dba)
) -> JSONResponse:
    repo = MemoryRepo(db, project, site)
    repo.set_user(r.user)
    changed = await repo.modify(memory, model)
    return modified(lambda: router.url_path_for('get_memory', project=project, site=site, memory=str(memory)), changed)


@router.post('/projects/{project}/sites/{site}/memories/{memory}')
@require_auth(scopes.AUTHENTICATED)
async def delete_memory(
        r: Request,
        project: PID,
        site: SID,
        memory: MID,
        db: Database = Depends(dba)
) -> JSONResponse:
    repo = MemoryRepo(db, project, site)
    repo.set_user(r.user)
    await repo.delete(memory)
    return deleted(router.url_path_for('get_memories', project=project, site=site))
