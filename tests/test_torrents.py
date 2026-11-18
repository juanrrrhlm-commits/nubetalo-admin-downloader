from pathlib import Path
import time
import libtorrent as lt
import pytest
from nubetalo.domain import Task
from nubetalo.torrents import TorrentEngine


def make_torrent(root, mode):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'content.bin').write_bytes(bytes(range(256)) * 4096)
    fs = lt.file_storage()
    fs.add_file('content.bin', 1048576)
    flags = {'v1': lt.create_torrent.v1_only, 'v2': lt.create_torrent.v2_only, 'hybrid': 0}[mode]
    torrent = lt.create_torrent(fs, 16384, flags)
    lt.set_piece_hashes(torrent, str(root))
    path = root / (mode + '.torrent')
    path.write_bytes(lt.bencode(torrent.generate()))
    return path


def test_metadata_checked_once_and_cached_files_protected(tmp_path, monkeypatch):
    from nubetalo.protection import PREFIX, unprotect
    source = make_torrent(tmp_path / 'seed', 'v1')
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(str(source), str(tmp_path / 'downloads'), kind='torrent')
    calls = []
    original = engine.validate_info
    monkeypatch.setattr(engine, 'validate_info', lambda info, destination: (calls.append(True), original(info, destination))[-1])
    try:
        engine.add(task)
        for _ in range(5):
            engine.tick()
        assert len(calls) == 1
        cached = Path(task.torrent_path).read_bytes()
        assert cached.startswith(PREFIX)
        assert unprotect(cached) == source.read_bytes()
    finally:
        engine.close()


def test_rejected_metadata_does_not_repeat_validation_each_tick(tmp_path, monkeypatch):
    source = make_torrent(tmp_path / 'seed', 'v1')
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(str(source), str(tmp_path / 'downloads'), kind='torrent')
    engine.add(task)
    engine.validated.clear()
    calls = []
    def rejected(info, destination):
        calls.append(True)
        raise ValueError('Unsupported torrent metadata')
    monkeypatch.setattr(engine, 'validate_info', rejected)
    try:
        for _ in range(5):
            assert engine.tick()[0]['status'] == 'error'
        assert len(calls) == 1
    finally:
        engine.close()


@pytest.mark.parametrize('mode', ['v1', 'v2', 'hybrid'])
def test_local_transfer_and_selection(tmp_path, mode):
    seed_root, dest = tmp_path / 'seed', tmp_path / 'dest'
    torrent = make_torrent(seed_root, mode)
    seed = lt.session({'listen_interfaces': '127.0.0.1:0', 'enable_dht': False, 'enable_lsd': False, 'enable_upnp': False, 'enable_natpmp': False})
    info = lt.torrent_info(str(torrent))
    handle = seed.add_torrent({'ti': info, 'save_path': str(seed_root)})
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(source=str(torrent), destination=str(dest), kind='torrent', selected=[0])
    engine.add(task)
    engine.resume(task.id)
    engine.handles[task.id].connect_peer(('127.0.0.1', seed.listen_port()))
    deadline = time.time() + 20
    while time.time() < deadline:
        events = engine.tick()
        if any(e.get('status') == 'seeding' for e in events):
            break
        time.sleep(.1)
    assert engine.handles[task.id].status().is_seeding
    engine.pause(task.id)
    assert next(e for e in engine.tick() if e['id'] == task.id)['status'] == 'queued'
    engine.close()
    assert (dest / 'content.bin').read_bytes() == (seed_root / 'content.bin').read_bytes()
    seed.pause()


def test_unselected_torrent_stays_metadata_only(tmp_path):
    torrent = make_torrent(tmp_path / 'seed', 'v1')
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(source=str(torrent), destination=str(tmp_path / 'dest'), kind='torrent')
    engine.add(task)
    assert engine.files(task.id)[0]['name'] == 'content.bin'
    assert not (tmp_path / 'dest/content.bin').exists()
    engine.close()


def test_duplicate_infohash_rejected(tmp_path):
    torrent = make_torrent(tmp_path / 'seed', 'v1')
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    engine.add(Task(source=str(torrent), destination=str(tmp_path / 'one'), kind='torrent'))
    with pytest.raises((ValueError, RuntimeError)):
        engine.add(Task(source=str(torrent), destination=str(tmp_path / 'two'), kind='torrent'))
    engine.close()


def test_paused_magnet_not_resumed_for_metadata(tmp_path):
    torrent = make_torrent(tmp_path / 'seed', 'v1')
    magnet = lt.make_magnet_uri(lt.torrent_info(str(torrent)))
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(source=magnet, destination=str(tmp_path / 'dest'), kind='torrent', manual_pause=True)
    engine.add(task)
    assert engine.handles[task.id].status().paused
    engine.close()


def test_file_priority_selection(tmp_path):
    torrent = make_torrent(tmp_path / 'seed', 'v1')
    engine = TorrentEngine(tmp_path / 'state', local_only=True)
    task = Task(source=str(torrent), destination=str(tmp_path / 'dest'), kind='torrent')
    engine.add(task)
    engine.select(task.id, [0], {'0': 7})
    deadline = time.monotonic() + 3
    while engine.handles[task.id].get_file_priorities()[0] != 7 and time.monotonic() < deadline:
        time.sleep(.02)  # libtorrent applies file priorities on its asynchronous disk thread.
    assert engine.handles[task.id].get_file_priorities()[0] == 7
    engine.close()
