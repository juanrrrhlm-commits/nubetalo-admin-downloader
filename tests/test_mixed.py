import time
import libtorrent as lt
from test_http import server
from test_torrents import make_torrent
from nubetalo.controller import Controller


def test_prioritized_http_gets_larger_actual_share(server, tmp_path):
    url, _ = server
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.connections = 4
    preferred = c.add_http(url, str(tmp_path / 'a'), 'a.bin')
    other = c.add_http(url, str(tmp_path / 'b'), 'b.bin')
    c.set_bandwidth_policy('priority', [preferred.id], 500000)
    started = time.monotonic()
    try:
        while time.monotonic() - started < 4:
            c.tick()
            time.sleep(.025)
        assert preferred.done > 0 and other.done > 0
        assert preferred.done > 2.5 * other.done
        assert preferred.done + other.done <= 2200000
        c.set_bandwidth_policy('equal')
        before_a, before_b = preferred.done, other.done
        started = time.monotonic()
        while time.monotonic() - started < 3:
            c.tick()
            time.sleep(.025)
        a_delta, b_delta = preferred.done - before_a, other.done - before_b
        assert a_delta > 0 and b_delta > 0
        assert .65 < a_delta / b_delta < 1.5
    finally:
        c.pause(preferred.id)
        c.pause(other.id)
        c.close()


def test_http_and_torrent_share_real_download_budget(server, tmp_path):
    url, _ = server
    torrent = make_torrent(tmp_path / 'seed', 'v1')
    seed = lt.session({'listen_interfaces': '127.0.0.1:0', 'enable_dht': False, 'enable_lsd': False,
                       'enable_upnp': False, 'enable_natpmp': False})
    seed.add_torrent({'ti': lt.torrent_info(str(torrent)), 'save_path': str(tmp_path / 'seed')})
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.download_limit = 500000
    c.settings.connections = 1
    http = c.add_http(url, str(tmp_path / 'http'), 'http.bin')
    tor = c.add_torrent(str(torrent), str(tmp_path / 'torrent'))
    c.select(tor.id, [0])
    c.tick()
    c.engine.handles[tor.id].connect_peer(('127.0.0.1', seed.listen_port()))
    started = time.monotonic()
    while time.monotonic() - started < 3.2:
        c.tick()
        time.sleep(.03)
    assert http.done > 0 and tor.done > 0
    # Payload/checkpoint timing and libtorrent token-bucket bursts have a bounded tolerance.
    assert http.done + tor.done <= 1900000
    c.pause(http.id)
    c.pause(tor.id)
    c.close()
    seed.pause()


def test_late_same_server_download_rebalances_without_damage(server, tmp_path):
    from test_http import DATA
    url, _ = server
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.connections = 4
    c.settings.download_limit = 1500000
    a = c.add_http(url, str(tmp_path / 'a'), 'a.bin')
    try:
        c.tick()
        time.sleep(.2)
        b = c.add_http(url, str(tmp_path / 'b'), 'b.bin')
        started = time.monotonic()
        while time.monotonic() - started < 15 and not all(t.status == 'completed' for t in (a, b)):
            c.tick()
            time.sleep(.025)
        assert a.status == b.status == 'completed', (a.status, a.error, b.status, b.error)
        assert (tmp_path / 'a/a.bin').read_bytes() == DATA
        assert (tmp_path / 'b/b.bin').read_bytes() == DATA
    finally:
        c.close()


def test_late_download_preserves_non_resumable_single_connection(server, tmp_path):
    url, handler = server
    handler.ranges = False
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.connections = 4
    c.settings.download_limit = 300000
    a = c.add_http(url, str(tmp_path / 'a'), 'a.bin')
    try:
        started = time.monotonic()
        while a.done < 65536 and time.monotonic() - started < 4:
            c.tick()
            time.sleep(.025)
        assert a.done > 0 and a.server_notice == 'ranges_ignored'
        b = c.add_http(url, str(tmp_path / 'b'), 'b.bin')
        started = time.monotonic()
        while time.monotonic() - started < 2:
            c.tick()
            time.sleep(.025)
        assert a.status == 'downloading', (a.status, a.error)
        assert b.done > 0
    finally:
        c.close()
