import importlib.util
from pathlib import Path
import pytest


def helper():
    path=Path(__file__).resolve().parents[2]/'scripts/configure.py'
    spec=importlib.util.spec_from_file_location('mac_config',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_first_run_key_is_local_private_and_not_printed(tmp_path,monkeypatch,capsys):
    module=helper()
    (tmp_path/'backend').mkdir()
    (tmp_path/'.env.example').write_text('LLM_MODEL=qwen-plus\nIMAGE_MODEL=qwen-image-2.1-turbo\n')
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module.os,'isatty',lambda fd:True)
    monkeypatch.setattr(module.getpass,'getpass',lambda prompt:'test-secret-local')
    monkeypatch.setattr('builtins.input',lambda prompt:'')
    module.configure()
    path=tmp_path/'backend/.env'
    assert 'test-secret-local' in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'test-secret-local' not in capsys.readouterr().out
    original=path.read_text()
    monkeypatch.setattr(module.getpass,'getpass',lambda prompt:pytest.fail('Existing key must not be prompted again'))
    module.configure()
    assert path.read_text()==original


def test_noninteractive_first_run_does_not_invent_key(tmp_path,monkeypatch):
    module=helper();(tmp_path/'backend').mkdir();(tmp_path/'.env.example').write_text('DASHSCOPE_API_KEY=\n')
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module.os,'isatty',lambda fd:False)
    module.configure()
    values=module.dotenv_values(tmp_path/'backend/.env')
    assert not values['DASHSCOPE_API_KEY'] and values['XHS_API_TOKEN']
