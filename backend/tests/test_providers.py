import asyncio
import json
import httpx
import pytest
from notepilot.providers import XHS, LLM, ProviderError, collect
from notepilot.models import Brief
from notepilot.agent import Plan


def test_xhs_read_only_adapter_and_nested_detail(monkeypatch):
    requests = []
    def handler(request):
        requests.append((request.url.path, json.loads(request.content)))
        if request.url.path.endswith('/search'):
            return httpx.Response(200, json={'success':True,'data':{'feeds':[{'id':'n1','xsecToken':'secret-test-token','modelType':'note','noteCard':{'displayTitle':'实际标题','interactInfo':{'likedCount':'1.2万','collectedCount':'300'},'cover':{'urlDefault':'https://img.xhscdn.com/cover.png'}}}]}})
        return httpx.Response(200,json={'success':True,'data':{'feed_id':'n1','data':{'note':{'title':'完整标题','desc':'正文','time':1791849600000},'comments':{'list':[{'content':'怎么开始？'}]}}}})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv('XHS_BASE_URL','http://127.0.0.1:18060')
    samples,warnings=asyncio.run(XHS().research(['AI编程']))
    assert len(samples)==1 and samples[0]['text']=='正文'
    assert samples[0]['likes']==12000 and samples[0]['questions']==['怎么开始？']
    assert {p for p,_ in requests}=={'/api/v1/feeds/search','/api/v1/feeds/detail'}
    assert 'secret-test-token' not in json.dumps(samples)
    assert requests[0][1]['filters']['publish_time']=='一周内'


def test_live_missing_sources_is_not_demo(monkeypatch):
    monkeypatch.delenv('XHS_BASE_URL',raising=False)
    monkeypatch.delenv('DOUYIN_CLIENT_TOKEN',raising=False)
    result=asyncio.run(collect(Brief(intent='真实内容生成',mode='live'),['主题']))
    assert result['coverage']=='partial' and result['samples']==[] and result['music']==[]


def test_llm_invalid_json_is_repaired_only_once(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'invalid'}}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv('LLM_API_KEY','test-not-secret')
    monkeypatch.setenv('LLM_MODEL','test-model')
    with pytest.raises(ProviderError):
        asyncio.run(LLM().json('prompt',Plan))
    assert len(calls)==2
