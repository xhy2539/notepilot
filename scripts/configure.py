"""Interactive local-only configuration. Never print API keys or auth tokens."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def configure(force=False):
    path = ROOT / 'backend/.env'
    if not path.exists():
        path.write_text((ROOT / '.env.example').read_text(), encoding='utf-8')
    os.chmod(path, 0o600)
    values = dotenv_values(path)
    existing = values.get('DASHSCOPE_API_KEY') or values.get('LLM_API_KEY')
    if force or not existing:
        print('填入北京地域百炼 API Key，可同时用于文案、看图与配图。')
        print('直接回车跳过：先启动离线演示；稍后可编辑 backend/.env。')
        if os.isatty(0):
            key = getpass.getpass('百炼 API Key（不显示）：').strip()
            if key:
                set_key(path, 'DASHSCOPE_API_KEY', key)
                set_key(path, 'LLM_API_KEY', '')
                set_key(path, 'IMAGE_API_KEY', '')
                set_key(path, 'LLM_PROVIDER', 'bailian')
                set_key(path, 'IMAGE_PROVIDER', 'bailian')
                base = input('百炼兼容 API 地址（回车使用北京公共地址）：').strip() or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
                from urllib.parse import urlparse
                parsed = urlparse(base)
                if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.aliyuncs.com') or parsed.username or parsed.password or parsed.query or parsed.fragment:
                    raise SystemExit('请在 backend/.env 填入正确的百炼 HTTPS 兼容 API 地址后重启。')
                set_key(path, 'LLM_BASE_URL', base.rstrip('/'))
                set_key(path, 'IMAGE_BASE_URL', base.rstrip('/'))
                for name, default in [('LLM_MODEL','qwen-plus'), ('VISION_MODEL','qwen-vl-plus'), ('IMAGE_MODEL','qwen-image-2.1-turbo')]:
                    set_key(path, name, values.get(name) or default)
        else:
            print('非交互运行，未填写 Key，将使用离线演示。')
    if not values.get('XHS_API_TOKEN'):
        set_key(path, 'XHS_API_TOKEN', secrets.token_urlsafe(32))
    os.chmod(path, 0o600)
    print('配置已准备好。API Key 与登录状态均不上传 Git。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', action='store_true', help='重新填写百炼 Key')
    configure(parser.parse_args().configure)
