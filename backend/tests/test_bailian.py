import asyncio
import json
import httpx
import pytest
from notepilot.providers import image_generate, download_bailian_image, bailian_image_url


def test_bailian_url_generation_and_download_never_forwards_key(monkeypatch):
    seen=[]
    png=b'\x89PNG\r\n\x1a\nfixture'
    def handler(request):
        seen.append(request)
        if request.method=='POST':
            assert 'response_format' not in json.loads(request.content)
            return httpx.Response(200,json={'data':[{'url':'https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/a.png?Expires=123'}]})
        assert 'authorization' not in request.headers
        return httpx.Response(200,content=png,headers={'content-type':'image/png'})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv('IMAGE_PROVIDER','bailian')
    monkeypatch.setenv('DASHSCOPE_API_KEY','test-key')
    monkeypatch.setenv('IMAGE_MODEL','qwen-image-2.1-turbo')
    monkeypatch.setenv('LLM_BASE_URL','https://dashscope.aliyuncs.com/compatible-mode/v1')
    monkeypatch.delenv('IMAGE_API_KEY',raising=False)
    monkeypatch.delenv('IMAGE_BASE_URL',raising=False)
    result=asyncio.run(image_generate('原创图示'))
    assert result==png
    assert str(seen[0].url)=='https://dashscope.aliyuncs.com/compatible-mode/v1/images/generations'
    assert seen[0].headers['authorization']=='Bearer test-key'


def test_official_bailian_download_host_constraints():
    assert bailian_image_url('https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/a.png')
    assert bailian_image_url('https://dashscope-result.oss-accelerate.aliyuncs.com/a.png')
    for url in ['http://dashscope-result.oss-cn-beijing.aliyuncs.com/a','https://127.0.0.1/a','https://evil.oss-cn-beijing.aliyuncs.com/a','https://dashscope-result.oss-cn-beijing.aliyuncs.com.evil.test/a','https://user:pw@dashscope-result.oss-cn-beijing.aliyuncs.com/a']:
        assert not bailian_image_url(url)
        with pytest.raises(Exception): asyncio.run(download_bailian_image(url))


def test_download_rejects_redirect_without_following(monkeypatch):
    original=httpx.AsyncClient
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(302,headers={'location':'http://127.0.0.1/internal'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(Exception): asyncio.run(download_bailian_image('https://dashscope-result.oss-cn-beijing.aliyuncs.com/a'))
    assert len(calls)==1


def test_health_accepts_single_shared_bailian_key(client,monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY','test-key')
    monkeypatch.setenv('LLM_MODEL','qwen-plus')
    monkeypatch.setenv('IMAGE_MODEL','qwen-image-2.1-turbo')
    monkeypatch.setenv('IMAGE_PROVIDER','bailian')
    assert client.get('/api/health').json()['llm']
    assert client.get('/api/health').json()['image']


@pytest.fixture
def client(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import notepilot.app as module
    from notepilot.store import Store
    monkeypatch.setattr(module,'store',Store(tmp_path/'store.sqlite'))
    with TestClient(module.app) as client:yield client


def test_xhs_login_proxy_filters_credentials(client,monkeypatch):
    original=httpx.AsyncClient
    def handler(request):
        assert request.headers['authorization']=='Bearer local-test-token'
        return httpx.Response(200,json={'success':True,'data':{'is_logged_in':False,'img':'data:image/png;base64,test','timeout':'4m','cookie':'must-not-leak'}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv('XHS_BASE_URL','http://127.0.0.1:18060')
    monkeypatch.setenv('XHS_API_TOKEN','local-test-token')
    result=client.get('/api/integrations/xhs/qrcode')
    assert result.status_code==200 and 'cookie' not in result.json()
    assert client.get('/api/integrations/xhs/publish').status_code==404
