import asyncio
import io
import json
import time
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from notepilot.models import Brief, Draft
from notepilot.store import Store, Conflict
from notepilot.providers import count, covers_data, LLM, XHS
from notepilot.agent import research_graph, generation_graph, check_draft
from notepilot.render import slide_html


def test_agent_demo_is_explicit_and_has_no_invented_music():
    brief = Brief(intent='给大学生做一个 AI 编程入门清单').model_dump(mode='json')
    research = asyncio.run(research_graph(lambda *a: None).ainvoke({'brief': brief}))
    assert research['trend']['coverage'] == 'demo'
    assert not research['trend']['music']
    assert all(s['likes'] is None and s['url'] is None for s in research['trend']['samples'])
    result = asyncio.run(generation_graph(lambda *a: None).ainvoke({**research, 'selected': research['plan']['angles'][0]}))
    assert len(result['draft']['slides']) == 6 and not result['issues']
    assert result['draft']['music_id'] is None


def test_database_compare_and_swap_and_restart(tmp_path):
    path = tmp_path/'store.sqlite'
    store = Store(path)
    store.create({'id': 'p', 'revision': 1, 'status': 'review'})
    original = store.get('p')
    saved = store.save({**original, 'status': 'approved'}, 1)
    with pytest.raises(Conflict):
        store.save(original, 1)
    assert Store(path).get('p')['revision'] == saved['revision'] == 2


def test_counts_missing_and_unit_values():
    assert count(None) is None and count('') is None
    assert count('1.2万') == 12000 and count('2.5k') == 2500
    assert count('未知') is None


def test_reference_image_rejects_internal_or_arbitrary_urls():
    for url in ['http://127.0.0.1/x', 'https://evil.com/a.png', 'https://xhscdn.com.evil.com/a.png', 'https://u:p@img.xhscdn.com/a.png']:
        with pytest.raises(Exception):
            asyncio.run(covers_data(url))


def test_renderer_escapes_user_content():
    from notepilot.models import Slide
    result = slide_html(Slide(id='s', title='<script>alert(1)</script>', body=['<img src=x onerror=alert(1)>']), 'mint', 1, 4)
    assert '<script>' not in result and '&lt;script&gt;' in result
    assert '<img src=x' not in result


@pytest.fixture
def client(tmp_path, monkeypatch):
    import notepilot.app as appmodule
    monkeypatch.setattr(appmodule, 'store', Store(tmp_path/'store.sqlite'))
    monkeypatch.setattr(appmodule, 'DATA', tmp_path)
    with TestClient(appmodule.app) as c:
        yield c


def complete(client, pid):
    for _ in range(100):
        p = client.get('/api/projects/'+pid).json()
        if p['status'] not in ('researching', 'generating', 'imaging'):
            return p
        time.sleep(.01)
    raise AssertionError('job timed out')


def make_draft(client):
    p = client.post('/api/projects', json={'intent':'给大学生制作入门清单'}).json()
    p = complete(client, p['id'])
    r = client.post(f"/api/projects/{p['id']}/select", json={'revision':p['revision'],'angle_id':'0'})
    assert r.status_code == 200
    return complete(client, p['id'])


def test_approval_invalidated_by_edit_and_stale_update_rejected(client):
    p = make_draft(client)
    pid = p['id']
    assert client.get(f'/api/projects/{pid}/export?revision={p["revision"]}').status_code == 409
    approved = client.post(f'/api/projects/{pid}/approve', json={'revision':p['revision']}).json()
    assert approved['approval']
    assert client.put(f'/api/projects/{pid}/draft', json={'revision':p['revision'],'draft':p['draft']}).status_code == 409
    r = client.put(f'/api/projects/{pid}/draft', json={'revision':approved['revision'],'draft':p['draft']})
    assert r.status_code == 200 and r.json()['approval'] is None


def test_unknown_music_or_sample_blocks_approval(client):
    p = make_draft(client)
    p['draft']['music_id'] = 'fake-hit'
    p['draft']['slides'][0]['sample_ids'] = ['unknown']
    edited = client.put(f"/api/projects/{p['id']}/draft", json={'revision':p['revision'],'draft':p['draft']}).json()
    assert len(edited['issues']) == 2
    assert client.post(f"/api/projects/{p['id']}/approve", json={'revision':edited['revision']}).status_code == 409


def test_cancel_stops_running_work_and_keeps_project(client, monkeypatch):
    import notepilot.app as module
    class Slow:
        async def ainvoke(self, state):
            await asyncio.sleep(30)
    monkeypatch.setattr(module, 'research_graph', lambda emit: Slow())
    p = client.post('/api/projects', json={'intent':'取消任务测试'}).json()
    r = client.post(f"/api/projects/{p['id']}/cancel")
    assert r.status_code == 200 and r.json()['status'] == 'cancelled'
    assert r.json()['brief']['intent'] == '取消任务测试'


def test_cross_origin_mutation_rejected(client):
    assert client.post('/api/projects', json={'intent':'测试意图'}, headers={'Origin':'https://evil.example'}).status_code == 403


def test_export_png_dimensions_and_archive(client):
    p = make_draft(client)
    p = client.post(f"/api/projects/{p['id']}/approve", json={'revision':p['revision']}).json()
    r = client.get(f"/api/projects/{p['id']}/export?revision={p['revision']}")
    assert r.status_code == 200, r.text if r.status_code!=200 else ''
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        assert len([n for n in archive.namelist() if n.endswith('.png')]) == 6
        import struct
        assert struct.unpack('>II', archive.read('01.png')[16:24]) == (1080,1440)
        assert 'caption.md' in archive.namelist() and 'sources.json' in archive.namelist()
