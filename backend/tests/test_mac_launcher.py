import hashlib
import importlib.util
from pathlib import Path
import pytest


def helper():
    path=Path(__file__).resolve().parents[2]/'scripts/launch.py'
    spec=importlib.util.spec_from_file_location('mac_launch',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_launcher_uses_loopback_and_cleans_owned_process(tmp_path,monkeypatch):
    module=helper();(tmp_path/'backend').mkdir();(tmp_path/'backend/.env').write_text('XHS_BASE_URL=\n')
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'port_free',lambda port:True)
    calls=[]
    class Process:
        stopped=False
        interrupted=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout=None):
            if not self.interrupted:
                self.interrupted=True
                raise KeyboardInterrupt
            return 0
    process=Process()
    monkeypatch.setattr(module.subprocess,'Popen',lambda args,**kwargs:(calls.append((args,kwargs)) or process))
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *args,**kwargs:Response())
    monkeypatch.setattr(module.webbrowser,'open',lambda url:True)
    monkeypatch.setattr(module.signal,'signal',lambda *args:None)
    module.launch()
    assert process.stopped
    assert calls[0][0][-4:]==['--host','127.0.0.1','--port','8000']


def test_corrupted_xhs_binary_is_never_accepted(tmp_path,monkeypatch):
    module=helper();monkeypatch.setattr(module,'ROOT',tmp_path)
    directory=tmp_path/'.tools/xhs';directory.mkdir(parents=True)
    (directory/module.XHS_FILE).write_bytes(b'corrupted')
    def fake_download(args,check):
        Path(args[-1]).write_bytes(b'also-invalid')
    monkeypatch.setattr(module.subprocess,'run',fake_download)
    with pytest.raises(RuntimeError):module.download_xhs()
    assert not (directory/(module.XHS_FILE+'.download')).exists()
