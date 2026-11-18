"""Kill a real worker process and recover only its persisted checkpoints."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from test_http import server, DATA
from nubetalo.controller import Controller


def test_process_kill_and_resume(server, tmp_path):
    url, _ = server
    script = '''
from pathlib import Path
import sys,time
from nubetalo.controller import Controller
c=Controller(Path(sys.argv[1]),local_only=True)
c.settings.download_limit=1000000
c.settings.connections=1
c.apply_settings(c.settings)
c.add_http(sys.argv[2],sys.argv[3],'recovered.bin')
while True:
    c.tick()
    time.sleep(.03)
'''
    process = subprocess.Popen([sys.executable, '-c', script, str(tmp_path / 'app'), url, str(tmp_path / 'downloads')],
                               cwd=Path(__file__).resolve().parent.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 12
        persisted = False
        while time.monotonic() < deadline:
            for path in (tmp_path / 'downloads').glob('.nubetalo-*/state.json'):
                try:
                    state = json.loads(path.read_text())
                    persisted = sum(s['done'] for s in state['segments']) > 100000
                except (OSError, ValueError):
                    continue
            if persisted:
                break
            time.sleep(.05)
        assert persisted
    finally:
        process.kill()
        process.wait(timeout=5)
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.download_limit = 0
    deadline = time.monotonic() + 15
    task = next(iter(c.tasks.values()))
    while task.status != 'completed' and time.monotonic() < deadline:
        c.tick()
        time.sleep(.03)
    assert task.status == 'completed', task.error
    c.close()
    assert hashlib.sha256((tmp_path / 'downloads/recovered.bin').read_bytes()).digest() == hashlib.sha256(DATA).digest()
