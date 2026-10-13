"""Mac supervisor; owns and cleans up only the processes started by this script."""
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
XHS_VERSION = 'v2.5.5'
XHS_FILE = 'xiaohongshu-mcp-darwin-arm64'
XHS_SHA = 'fad3633fda4a8060e66e2941bc8fc5460326c7cb4e58a32485a9e2c9408e95a8'


def download_xhs():
    binary = ROOT / '.tools/xhs' / XHS_FILE
    if binary.exists() and hashlib.sha256(binary.read_bytes()).hexdigest() == XHS_SHA:
        return binary
    print('下载已核对 SHA256 的小红书 MCP v2.5.5…')
    temp = binary.with_suffix('.download')
    url = f'https://github.com/xpzouying/xiaohongshu-mcp/releases/download/{XHS_VERSION}/{XHS_FILE}'
    subprocess.run(['curl','--proto','=https','--tlsv1.2','-fL','--retry','3',url,'-o',str(temp)],check=True)
    if hashlib.sha256(temp.read_bytes()).hexdigest() != XHS_SHA:
        temp.unlink(missing_ok=True)
        raise RuntimeError('小红书二进制校验失败，未运行')
    temp.replace(binary)
    binary.chmod(0o755)
    return binary


def port_free(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def launch():
    config = {key: value for key,value in dotenv_values(ROOT/'backend/.env').items() if value is not None}
    env = {**os.environ, **config}
    if not port_free(8000):
        raise SystemExit('8000 端口已占用。关闭之前的 NotePilot 终端，或在浏览器打开 http://127.0.0.1:8000。')
    processes, files = [], []
    def stop(*args):
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for file in files:
            file.close()
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    try:
        if config.get('XHS_BASE_URL','').rstrip('/') == 'http://127.0.0.1:18060' and port_free(18060):
            if os.uname().machine == 'arm64':
                try:
                    binary = download_xhs()
                    log = open(ROOT/'.tools/logs/xhs.log','a',encoding='utf-8'); files.append(log)
                    xhs_env = {**env, 'AUTH_TOKEN': config.get('XHS_API_TOKEN','')}
                    processes.append(subprocess.Popen([str(binary),'-port','127.0.0.1:18060'],cwd=ROOT/'.tools/xhs',env=xhs_env,stdout=log,stderr=log))
                    print('小红书服务正在启动，首次会下载浏览器；进入工作台扫码即可登录。')
                except (OSError, RuntimeError, subprocess.CalledProcessError):
                    print('小红书服务未启动。可先体验演示或导入真实样本；详细说明见 docs/mac.md。')
            else:
                print('Intel Mac 的上游发行版没有对应二进制；使用 Docker 接入小红书，见 docs/mac.md。')
        elif config.get('XHS_BASE_URL','').rstrip('/') == 'http://127.0.0.1:18060':
            print('18060 已有服务，本次不会启动或关闭它；需确保 .env 的 XHS_API_TOKEN 与该服务匹配。')
        backend = subprocess.Popen([sys.executable,'-m','uvicorn','notepilot.app:app','--host','127.0.0.1','--port','8000'],cwd=ROOT/'backend',env=env)
        processes.append(backend)
        for _ in range(60):
            if backend.poll() is not None:
                raise SystemExit('后端退出，请检查上面的错误提示。')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1):
                    break
            except OSError:
                time.sleep(.5)
        else:
            raise SystemExit('后端启动超时。')
        print('\nNotePilot 已启动：http://127.0.0.1:8000\n保持此终端打开；按 Ctrl+C 停止本次启动的服务。')
        webbrowser.open('http://127.0.0.1:8000')
        backend.wait()
    except KeyboardInterrupt:
        print('\n正在停止服务…')
    finally:
        stop()


if __name__ == '__main__':
    launch()
