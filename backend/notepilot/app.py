import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .models import Brief, Draft, Edit, Selection, Revision, ImageRequest, now
from .store import Store, Conflict
from .agent import research_graph, generation_graph, check_draft
from .providers import ProviderError, image_generate
from .render import export_zip

DATA = Path(os.getenv('NOTEPILOT_DATA', './data')).resolve()
store = Store(DATA / 'notepilot.sqlite')
tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app):
    for project in store.list():
        if project['status'] in ('researching', 'generating', 'imaging'):
            project['status'] = 'interrupted'
            project['error'] = '服务重启，已保存的内容仍在；请重试当前阶段'
            store.save(project, project['revision'])
    yield
    for task in list(tasks.values()):
        task.cancel()
    if tasks:
        await asyncio.gather(*list(tasks.values()), return_exceptions=True)


app = FastAPI(title='NotePilot', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])


@app.middleware('http')
async def local_origin(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin not in ('http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8000', 'http://127.0.0.1:8000'):
            return Response('只接受本地工作台请求', status_code=403)
        length = request.headers.get('content-length')
        if length and int(length) > 1_000_000:
            return Response('输入超过 1MB', status_code=413)
    return await call_next(request)


def get(pid):
    try:
        return store.get(pid)
    except KeyError:
        raise HTTPException(404, '作品不存在')


def idle(project):
    if project['status'] in ('researching', 'generating', 'imaging'):
        raise HTTPException(409, '任务仍在执行，请等待或取消')


def save(project, revision):
    try:
        return store.save(project, revision)
    except Conflict as exc:
        raise HTTPException(409, str(exc))


async def run(pid, stage):
    emit = lambda name, message: store.event(pid, name, message)
    try:
        project = get(pid)
        state = {'brief': project['brief'], 'trend': project.get('trend'), 'selected': project.get('selected'), 'repairs': 0}
        graph = research_graph(emit) if stage == 'research' else generation_graph(emit)
        result = await graph.ainvoke(state)
        current = get(pid)
        if stage == 'research':
            current.update(trend=result['trend'], plan=result['plan'], status='awaiting_angle')
        else:
            current.update(draft=result['draft'], issues=result['issues'], status='review')
        current['approval'] = None
        save(current, current['revision'])
        emit('done', '请选方向' if stage == 'research' else '图文草稿已生成，请核对事实、素材和音乐')
    except asyncio.CancelledError:
        current = get(pid)
        current.update(status='cancelled', approval=None)
        save(current, current['revision'])
        emit('cancelled', '任务已取消，已完成内容保留')
    except Exception as exc:
        current = get(pid)
        current.update(status='failed', error=str(exc) if isinstance(exc, ProviderError) else '执行失败，请检查服务配置后重试', approval=None)
        save(current, current['revision'])
        emit('failed', current['error'])
    finally:
        tasks.pop(pid, None)


def start(project, stage):
    project.update(status='researching' if stage == 'research' else 'generating', error=None, approval=None)
    project = save(project, project['revision'])
    tasks[project['id']] = asyncio.create_task(run(project['id'], stage))
    return project


@app.get('/api/health')
def health():
    return {'ok': True, 'llm': bool(os.getenv('LLM_API_KEY') and os.getenv('LLM_MODEL')), 'xhs': bool(os.getenv('XHS_BASE_URL')), 'image': bool(os.getenv('IMAGE_API_KEY') and os.getenv('IMAGE_MODEL'))}


@app.get('/api/projects')
def projects():
    return [{'id': p['id'], 'intent': p['brief']['intent'], 'status': p['status'], 'revision': p['revision']} for p in store.list()]


@app.post('/api/projects')
async def create(brief: Brief):
    project = {'id': uuid4().hex, 'revision': 1, 'status': 'created', 'brief': brief.model_dump(mode='json'), 'created_at': now(), 'updated_at': now(), 'approval': None, 'image_ids': []}
    store.create(project)
    return start(project, 'research')


@app.get('/api/projects/{pid}')
def project(pid: str):
    return get(pid)


@app.post('/api/projects/{pid}/select')
async def select(pid: str, choice: Selection):
    project = get(pid)
    idle(project)
    if choice.revision != project['revision']:
        raise HTTPException(409, '版本已变化，请刷新')
    angle = next((a for a in project.get('plan', {}).get('angles', []) if a['id'] == choice.angle_id), None)
    if not angle:
        raise HTTPException(422, '创作方向不存在')
    project['selected'] = angle
    return start(project, 'generate')


@app.post('/api/projects/{pid}/retry')
async def retry(pid: str, revision: Revision):
    project = get(pid)
    idle(project)
    if project['revision'] != revision.revision:
        raise HTTPException(409, '版本已变化，请刷新')
    return start(project, 'generate' if project.get('selected') and project.get('trend') else 'research')


@app.post('/api/projects/{pid}/cancel')
async def cancel(pid: str):
    get(pid)
    if pid in tasks:
        task = tasks[pid]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        tasks.pop(pid, None)
        current = get(pid)
        if current['status'] in ('researching', 'generating', 'imaging'):
            current.update(status='cancelled', approval=None)
            save(current, current['revision'])
            store.event(pid, 'cancelled', '任务已取消')
    return get(pid)


@app.put('/api/projects/{pid}/draft')
def edit(pid: str, edit: Edit):
    project = get(pid)
    idle(project)
    if not project.get('draft'):
        raise HTTPException(409, '尚无可编辑草稿')
    if any(s.image_id and s.image_id not in project['image_ids'] for s in edit.draft.slides):
        raise HTTPException(422, '只能使用本作品生成的图片')
    project.update(draft=edit.draft.model_dump(), issues=check_draft(edit.draft, project['trend'], project['brief']['pages']), approval=None, status='review')
    return save(project, edit.revision)


@app.post('/api/projects/{pid}/approve')
def approve(pid: str, revision: Revision):
    project = get(pid)
    idle(project)
    if not project.get('draft') or project.get('issues'):
        raise HTTPException(409, '请先生成并修复草稿问题')
    project['approval'] = {'at': now(), 'revision': revision.revision+1}
    project['status'] = 'approved'
    return save(project, revision.revision)


@app.post('/api/projects/{pid}/image')
async def image(pid: str, request: ImageRequest):
    project = get(pid)
    idle(project)
    if project['revision'] != request.revision:
        raise HTTPException(409, '版本已变化，请刷新')
    slide = next((s for s in project.get('draft', {}).get('slides', []) if s['id'] == request.slide_id), None)
    if not slide:
        raise HTTPException(404, '页面不存在')
    if len(project['image_ids']) >= 12:
        raise HTTPException(409, '本作品图片预算已达 12 次，请复用已有配图')
    project.update(status='imaging', approval=None)
    project = save(project, project['revision'])
    async def generate():
        try:
            raw = await image_generate(slide['image_prompt'] or slide['title'])
            iid = uuid4().hex
            (DATA / 'images').mkdir(exist_ok=True)
            (DATA / 'images' / f'{iid}.png').write_bytes(raw)
            current = get(pid)
            next(s for s in current['draft']['slides'] if s['id'] == request.slide_id)['image_id'] = iid
            current['image_ids'].append(iid)
            current.update(status='review', error=None)
            save(current, current['revision'])
            store.event(pid, 'done', '选中页面配图已生成')
        except asyncio.CancelledError:
            current = get(pid)
            current['status'] = 'review'
            save(current, current['revision'])
            store.event(pid, 'cancelled', '配图已取消，原稿保留')
        except Exception as exc:
            current = get(pid)
            current.update(status='review', error=str(exc) if isinstance(exc, ProviderError) else '配图失败，请检查图片服务')
            save(current, current['revision'])
            store.event(pid, 'failed', current['error'])
        finally:
            tasks.pop(pid, None)
    tasks[pid] = asyncio.create_task(generate())
    return project


@app.get('/api/projects/{pid}/images/{iid}')
def get_image(pid: str, iid: str):
    if iid not in get(pid)['image_ids']:
        raise HTTPException(404, '图片不存在')
    return FileResponse(DATA / 'images' / f'{iid}.png', media_type='image/png')


@app.get('/api/projects/{pid}/events')
async def events(pid: str, request: Request, after: int = 0):
    get(pid)
    try:
        cursor = max(after, int(request.headers.get('last-event-id', '0')))
    except ValueError:
        raise HTTPException(422, '事件游标格式错误')
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            rows = store.events(pid, cursor)
            for seq, data in rows:
                cursor = seq
                yield f'id: {seq}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
            if get(pid)['status'] not in ('researching', 'generating', 'imaging') and not rows:
                break
            yield ': heartbeat\n\n'
            await asyncio.sleep(.5)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})


@app.get('/api/projects/{pid}/export')
async def export(pid: str, revision: int):
    project = get(pid)
    if project['revision'] != revision or not project.get('approval') or project['approval']['revision'] != revision:
        raise HTTPException(409, '请审核当前版本后导出')
    try:
        data = await export_zip(project, DATA)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(503, '渲染失败：请安装 Playwright Chromium 和中文字体依赖，详见 README')
    return Response(data, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="notepilot-{pid[:8]}-r{revision}.zip"'})


dist = Path(__file__).resolve().parents[2] / 'frontend/dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
