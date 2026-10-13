import json
import os
from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from .models import Brief, Angle, Draft, Slide
from .providers import LLM, ProviderError, collect, covers_data


class Plan(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=2)
    angles: list[Angle] = Field(min_length=3, max_length=3)


class Visual(BaseModel):
    palette: str
    composition: str
    text_density: str
    reusable_rules: list[str]


class State(TypedDict, total=False):
    brief: dict
    trend: dict
    plan: dict
    selected: dict
    draft: dict
    issues: list[str]
    repairs: int


def prompt_context(state):
    # Bound context and avoid sending imported material twice through Brief.
    brief = {k: state['brief'][k] for k in ('intent', 'audience', 'goal', 'pages', 'mode')}
    trend = dict(state['trend'])
    trend['samples'] = [{**s, 'text': s.get('text', '')[:1500], 'questions': s.get('questions', [])[:5]} for s in trend['samples'][:12]]
    trend['music'] = trend['music'][:12]
    return {'brief': brief, 'trend': trend, 'selected': state.get('selected')}


def check_draft(draft: Draft, trend, pages):
    issues = []
    valid = {s['id'] for s in trend['samples']}
    if len(draft.slides) != pages:
        issues.append('页数与要求不一致')
    if len({s.id for s in draft.slides}) != len(draft.slides):
        issues.append('页面 ID 重复')
    if draft.music_id and draft.music_id not in {m['id'] for m in trend['music']}:
        issues.append('音乐引用不在真实候选中')
    for slide in draft.slides:
        if set(slide.sample_ids) - valid:
            issues.append(f'{slide.id} 引用了未知参考样本')
        if len(slide.title) > 32 or any(len(b) > 100 for b in slide.body) or sum(map(len, slide.body)) > 320:
            issues.append(f'{slide.id} 文字密度过高，请缩短')
    return list(dict.fromkeys(issues))


def demo_plan(brief):
    return Plan(keywords=[brief.intent[:30]], angles=[Angle(id=str(i), title=title, reason=reason, contribution=extra, sample_ids=[f'demo-{i}']) for i, (title, reason, extra) in enumerate([
        ('可收藏的入门行动清单', '将目标拆成具体步骤，适合初学者收藏。', '增加验收步骤与可复用检查表。'),
        ('常见误区与替代做法', '围绕初学者容易卡住的问题组织内容。', '每个问题提供具体替代行动。'),
        ('一个小任务的完整过程', '缩小范围，读者更容易实际尝试。', '展示目标、行动和结果验证。')])])


def demo_draft(brief, selected, trend):
    sections = [
        ('cover', selected['title'], [brief.intent, '一份可以照着做的行动清单']),
        ('steps', '01 / 先把目标缩小', ['写下你希望完成的一件具体事情。', '明确给谁用，以及什么结果算完成。']),
        ('compare', '02 / 收集可信参考', ['先查原始文档，再参考同类内容结构。', '热门样本提供灵感，事实仍需核对。']),
        ('steps', '03 / 一次只做一步', ['把任务拆成输入、行动、预期输出。', '先完成最小结果，再逐步补充。']),
        ('steps', '04 / 用结果验收', ['实际执行步骤，记录失败与修改。', '涉及亲身经历的内容只写真实做过的事。']),
        ('summary', '保存这份检查清单', ['目标明确 · 来源可查 · 步骤可执行', '结果可验证 · 配图一致 · 音乐适配'])]
    while len(sections) < brief.pages:
        sections.insert(-1, ('steps', f'补充步骤 {len(sections)-4}', ['记录自己的实践与发现。', '发布前再检查操作是否适用。']))
    sections = sections[:brief.pages-1] + [sections[-1]] if len(sections) > brief.pages else sections
    return Draft(titles=[selected['title'], '从零开始，先做这几步', '把想法变成能执行的清单'], caption=f'【离线演示文案，发布前请补充真实内容】\n\n{brief.intent}\n\n先明确目标，再找可信参考，分步执行，最后验证结果。\n\n这份清单帮助你开始；具体工具和操作需要依据当前官方资料核实。\n\nAI 辅助创作。', tags=['学习方法', '行动清单'], slides=[Slide(id=f's{i+1}', kind=kind, title=title, body=body, sample_ids=['demo-0'], image_prompt=f'极简薄荷色编辑插画，表达{title}') for i, (kind, title, body) in enumerate(sections)])


def research_graph(emit):
    async def research(state):
        brief = Brief.model_validate(state['brief'])
        emit('research', '采集近期参考样本与 BGM 候选')
        if brief.mode == 'demo':
            keywords = [brief.intent[:30]]
        else:
            # Keep provider and call budget small: one planning call after collection.
            keywords = [brief.intent[:30], brief.audience[:20]]
        trend = await collect(brief, keywords)
        if brief.mode == 'live' and not trend['samples']:
            raise ProviderError('没有取得参考样本。启动已登录的 XHS 服务或导入样本后重试。')
        if brief.mode == 'live' and os.getenv('VISION_MODEL'):
            for sample in trend['samples'][:2]:
                if sample.get('image_url'):
                    try:
                        cover = await covers_data(sample['image_url'])
                        result = await LLM().json('分析这张参考封面的配色、构图与文字密度；提取抽象规则，不复制原图。', Visual, [cover])
                        trend['visual_analysis'].append({'sample_id': sample['id'], **result.model_dump()})
                    except Exception:
                        # Don't surface provider payloads, tokens or CDN signatures.
                        trend['warnings'].append('部分封面视觉分析失败，未声称已分析图片')
        if not trend['visual_analysis']:
            trend['warnings'].append('未读取参考封面视觉：当前配图使用自有模板，热门视觉适配待启用 VISION_MODEL')
        return {'trend': trend}

    async def plan(state):
        emit('plan', '根据目标和参考样本提出三个原创方向')
        brief = Brief.model_validate(state['brief'])
        result = demo_plan(brief) if brief.mode == 'demo' else await LLM().json('给出三个不同内容角度。id 用 0/1/2。每个角度给出适合目标的理由、新增价值和 sample_ids。不要声称保证流量。\n输入：' + json.dumps(prompt_context(state), ensure_ascii=False), Plan)
        valid = {s['id'] for s in state['trend']['samples']}
        if len({a.id for a in result.angles}) != 3 or any(set(a.sample_ids)-valid for a in result.angles):
            raise ProviderError('策划引用无效，请重新调研')
        return {'plan': result.model_dump()}

    graph = StateGraph(State)
    graph.add_node('research', research)
    graph.add_node('plan', plan)
    graph.add_edge(START, 'research')
    graph.add_edge('research', 'plan')
    graph.add_edge('plan', END)
    return graph.compile()


def generation_graph(emit):
    async def write(state):
        emit('write', '联合策划文案、配图与音乐')
        brief = Brief.model_validate(state['brief'])
        if brief.mode == 'demo':
            draft = demo_draft(brief, state['selected'], state['trend'])
        else:
            draft = await LLM().json('生成可编辑图文。每页 title 最多32字，每条 body 最多100字，整页正文最多320字。页数严格按输入。使用相同视觉风格；image_prompt 用于原创无字插画。music_id 只能从候选选择，可为空；区分抖音榜与小红书热门。sample_ids 仅为结构/选题参考，不能把样本当权威事实。不要虚构亲测、数据或价格。不确定事实注明待核实。不要输出 image_id。修复此前问题：' + json.dumps(state.get('issues', []), ensure_ascii=False) + '\n数据：' + json.dumps(prompt_context(state), ensure_ascii=False), Draft)
            for slide in draft.slides:
                slide.image_id = None
        return {'draft': draft.model_dump(), 'repairs': state.get('repairs', 0) + 1}

    def review(state):
        emit('review', '检查引用、音乐候选与页面字数')
        return {'issues': check_draft(Draft.model_validate(state['draft']), state['trend'], state['brief']['pages'])}

    def route(state):
        return 'write' if state['issues'] and state.get('repairs', 0) < 2 else END

    graph = StateGraph(State)
    graph.add_node('write', write)
    graph.add_node('review', review)
    graph.add_edge(START, 'write')
    graph.add_edge('write', 'review')
    graph.add_conditional_edges('review', route)
    return graph.compile()
