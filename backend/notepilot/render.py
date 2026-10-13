import base64
import html
import io
import json
import tempfile
import zipfile
from pathlib import Path
from playwright.async_api import async_playwright
from .models import Draft

PALETTES = {'mint': ('#f4f6ef', '#1b3430', '#b8d5c4'), 'ink': ('#ececf0', '#222632', '#c5c5ef'), 'peach': ('#fff3eb', '#51372f', '#f4c6af')}


def slide_html(slide, palette, index, total, image=None):
    bg, fg, accent = PALETTES[palette]
    title = html.escape(slide.title)
    blocks = ''.join(f'<li><span>{i+1:02}</span><p>{html.escape(b)}</p></li>' for i, b in enumerate(slide.body))
    illustration = f'<img class="art" src="data:image/png;base64,{base64.b64encode(image).decode()}">' if image else '<div class="shape"><b>✳</b><span>MAKE IT<br>HAPPEN.</span></div>'
    fonts = Path(__file__).resolve().parents[2] / 'frontend/node_modules/@fontsource/noto-sans-sc/index.css'
    font_css = ''
    if fonts.exists():
        import re
        font_css = re.sub(r'url\((\./[^)]+)\)', lambda m: 'url(' + (fonts.parent / m[1]).resolve().as_uri() + ')', fonts.read_text())
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>{font_css}
*{{box-sizing:border-box}}body{{margin:0;width:1080px;height:1440px;background:{bg};color:{fg};font-family:'Noto Sans SC',sans-serif}}main{{height:100%;padding:86px;position:relative;overflow:hidden}}header{{font-size:25px;letter-spacing:4px;display:flex;justify-content:space-between;border-bottom:2px solid {fg};padding-bottom:28px}}.pill{{display:inline-block;background:{accent};padding:14px 24px;margin:48px 0 20px;border-radius:40px;font-size:23px}}h1{{font-size:{76 if slide.kind=='cover' else 60}px;line-height:1.35;margin:10px 0 34px;overflow-wrap:anywhere}}ul{{padding:0;list-style:none}}li{{display:flex;gap:22px;margin:22px 0;padding:20px;background:#ffffff88;border-radius:20px;align-items:baseline}}li span{{font-size:25px}}p{{margin:0;font-size:32px;line-height:1.65;overflow-wrap:anywhere}}.shape{{height:300px;background:{accent};border-radius:170px 170px 32px 32px;display:flex;align-items:center;justify-content:space-around;margin:36px 0}}.shape b{{font-size:175px}}.shape span{{font:800 46px/1.2 sans-serif}}.art{{height:300px;width:100%;object-fit:contain;border-radius:24px;margin:28px 0}}footer{{position:absolute;bottom:50px;left:86px;right:86px;border-top:2px solid {fg};padding-top:20px;display:flex;justify-content:space-between;font-size:21px}}.content{{max-height:1150px}} </style>
<main><header><b>NOTEPILOT / FIELD NOTES</b><span>{index:02}—{total:02}</span></header><section class="content"><div class="pill">{'入门行动指南' if slide.kind=='cover' else '一步一步，开始行动'}</div><h1>{title}</h1>{illustration if slide.kind=='cover' or image else ''}<ul>{blocks}</ul></section><footer><span>AI 辅助创作 · 图示仅作说明</span><span>保存 · 实践 · 复盘</span></footer></main></html>'''


async def export_zip(project, data_dir):
    draft = Draft.model_validate(project['draft'])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page(viewport={'width': 1080, 'height': 1440}, device_scale_factor=1)
                for index, slide in enumerate(draft.slides, 1):
                    image_path = data_dir / 'images' / f'{slide.image_id}.png' if slide.image_id else None
                    image = image_path.read_bytes() if image_path and image_path.exists() else None
                    with tempfile.TemporaryDirectory() as directory:
                        file = Path(directory) / 'slide.html'
                        file.write_text(slide_html(slide, draft.palette, index, len(draft.slides), image), encoding='utf-8')
                        await page.goto(file.as_uri())
                        await page.evaluate('document.fonts.ready')
                        overflow = await page.evaluate('document.querySelector(".content").scrollHeight > 1150')
                        if overflow:
                            raise ValueError(f'第 {index} 页版式溢出，请缩短文字后重新审核')
                        archive.writestr(f'{index:02}.png', await page.screenshot())
            finally:
                await browser.close()
        caption = draft.titles[0] + '\n\n' + draft.caption + '\n\n' + ' '.join('#'+t.lstrip('#') for t in draft.tags)
        archive.writestr('caption.md', caption)
        archive.writestr('sources.json', json.dumps(project['trend'], ensure_ascii=False, indent=2))
        song = next((m for m in project['trend']['music'] if m['id'] == draft.music_id), None)
        archive.writestr('music.md', json.dumps(song, ensure_ascii=False, indent=2) + '\n\n' + draft.music_reason + '\n\n发布时确认平台曲库和版本；本包不含音频。')
        archive.writestr('project.json', json.dumps(project, ensure_ascii=False, indent=2))
    return buffer.getvalue()
