#!/bin/bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$TASK_ROOT"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "此入口用于 macOS；Linux/Windows 请按 README 手动启动。" >&2
  exit 1
fi
trap 'echo "启动未完成。检查上面的错误；重新运行同一命令会复用已下载的依赖。" >&2' ERR
mkdir -p .tools/uv .tools/node .tools/logs .tools/xhs
chmod 700 .tools .tools/xhs .tools/logs
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/.tools/python"
export UV_CACHE_DIR="$TASK_ROOT/.tools/uv-cache"
export PLAYWRIGHT_BROWSERS_PATH="$TASK_ROOT/.tools/playwright"

if [ ! -x "$TASK_ROOT/.tools/uv/uv" ]; then
  echo "[1/5] 安装项目专用 uv / Python（不修改系统 Python）"
  curl --proto '=https' --tlsv1.2 -fsSL --retry 3 https://astral.sh/uv/install.sh -o .tools/uv-install.sh
  UV_INSTALL_DIR="$TASK_ROOT/.tools/uv" UV_NO_MODIFY_PATH=1 sh .tools/uv-install.sh
fi
TASK_UV="$TASK_ROOT/.tools/uv/uv"
if [ -x .venv/bin/python ] && [ "$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.12" ]; then
  mv .venv ".venv.previous.$(date +%Y%m%d%H%M%S)"
  echo "已保留旧虚拟环境备份，准备 Python 3.12。"
fi
if [ ! -x .venv/bin/python ]; then
  "$TASK_UV" venv --python 3.12 .venv
fi
echo "[2/5] 安装后端与 Chromium"
"$TASK_UV" pip install --python .venv/bin/python -r backend/requirements-mac.lock
"$TASK_UV" pip install --python .venv/bin/python --no-deps -e backend
.venv/bin/python -m playwright install chromium

echo "[3/5] 准备 Node 与前端"
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1 || [ "$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)" -lt 20 ]; then
  case "$(uname -m)" in arm64) TASK_ARCH=arm64;; x86_64) TASK_ARCH=x64;; *) echo "不支持的 Mac 架构" >&2; exit 1;; esac
  if [ ! -x .tools/node/bin/node ]; then
    TASK_NODE_BASE=https://nodejs.org/dist/latest-v22.x
    curl --proto '=https' --tlsv1.2 -fsSL --retry 3 "$TASK_NODE_BASE/SHASUMS256.txt" -o .tools/node-checksums.txt
    TASK_NODE_FILE=$(awk -v arch="$TASK_ARCH" '$2 ~ "-darwin-" arch "\\.tar\\.gz$" {print $2; exit}' .tools/node-checksums.txt)
    if [ -z "$TASK_NODE_FILE" ]; then echo "无法找到官方 Node Mac 安装包" >&2; exit 1; fi
    curl --proto '=https' --tlsv1.2 -fL --retry 3 "$TASK_NODE_BASE/$TASK_NODE_FILE" -o ".tools/$TASK_NODE_FILE"
    awk -v file="$TASK_NODE_FILE" '$2==file {print $1 "  " file}' .tools/node-checksums.txt > .tools/node-selected.sha256
    (cd .tools && shasum -a 256 -c node-selected.sha256)
    tar -xzf ".tools/$TASK_NODE_FILE" -C .tools/node --strip-components=1
  fi
  export PATH="$TASK_ROOT/.tools/node/bin:$PATH"
fi
(cd frontend && npm ci --no-audit --no-fund && VITE_CLOUD_DEMO=0 npm run build)
echo "[4/5] 本地配置（Key 不回显，只保存在 backend/.env）"
.venv/bin/python scripts/configure.py "$@"
echo "[5/5] 启动小红书服务与 NotePilot"
exec .venv/bin/python scripts/launch.py
