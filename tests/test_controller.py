from datetime import datetime
import pytest
from nubetalo.controller import Controller, allocate_limits
from nubetalo.domain import Task


def test_shared_rate_allocation():
    assert sum(allocate_limits(100000, [0, 0, 0])) <= 100000
    limits = allocate_limits(100000, [10000, 0])
    assert limits[0] <= 10000 and sum(limits) <= 100000


def test_priority_weighted_budget_and_cap_redistribution():
    assert allocate_limits(100000, [0, 0], [4, 1]) == [80000, 20000]
    assert allocate_limits(100000, [10000, 0], [4, 1]) == [10000, 90000]
    assert sum(allocate_limits(100001, [0, 0, 0], [1, 1, 1])) == 100001


def test_main_bandwidth_policy_persists(tmp_path):
    c = Controller(tmp_path, local_only=True)
    a = c.add_http('https://example.com/a', str(tmp_path), 'a.bin')
    b = c.add_http('https://example.com/b', str(tmp_path), 'b.bin')
    c.set_bandwidth_policy('priority', [b.id], 1000000)
    assert b.priority == 2 and a.priority == 1
    assert c.settings.bandwidth_mode == 'priority'
    c.close()
    c = Controller(tmp_path, local_only=True)
    assert c.tasks[b.id].priority == 2
    assert c.settings.bandwidth_mode == 'priority'
    c.set_bandwidth_policy('equal')
    assert c.settings.bandwidth_mode == 'equal'
    assert all(t.priority == 1 for t in c.tasks.values())
    c.close()


def test_manual_pause_survives_restart(tmp_path):
    c = Controller(tmp_path, local_only=True)
    task = c.add_http('https://example.com/file', str(tmp_path), 'file.bin')
    c.pause(task.id)
    c.close()
    c = Controller(tmp_path, local_only=True)
    assert c.tasks[task.id].manual_pause
    c.tick()
    assert not c.workers
    c.close()


def test_duplicate_and_conflicting_target_rejected(tmp_path):
    c = Controller(tmp_path, local_only=True)
    c.add_http('https://example.com/a', str(tmp_path), 'file.bin')
    with pytest.raises(ValueError):
        c.add_http('https://example.com/b', str(tmp_path), 'file.bin')
    c.close()


def test_completed_task_stays_completed_when_paused(tmp_path):
    c = Controller(tmp_path, local_only=True)
    task = c.add_http('https://example.com/file', str(tmp_path), 'complete.bin')
    task.status = 'completed'
    c.pause(task.id)
    assert task.status == 'completed'
    c.close()


def test_resuming_metadata_unpauses_engine(tmp_path):
    import libtorrent as lt
    c = Controller(tmp_path / 'app', local_only=True)
    t = c.add_torrent('magnet:?xt=urn:btih:' + '1' * 40, str(tmp_path / 'download'))
    c.pause(t.id)
    assert c.engine.handles[t.id].status().paused
    c.resume(t.id)
    assert not c.engine.handles[t.id].status().paused
    c.close()


def test_metadata_respects_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr('nubetalo.controller.time_window', lambda *args: False)
    c = Controller(tmp_path / 'app', local_only=True)
    c.settings.schedule_enabled = True
    t = c.add_torrent('magnet:?xt=urn:btih:' + '2' * 40, str(tmp_path / 'download'))
    assert c.engine.handles[t.id].status().paused
    c.tick()
    assert c.engine.handles[t.id].status().paused
    c.settings.schedule_enabled = False
    c.tick()
    assert not c.engine.handles[t.id].status().paused
    c.close()


def test_retry_after_longer_than_hour_honored(tmp_path):
    import time
    c = Controller(tmp_path, local_only=True)
    t = c.add_http('https://example.com/a', str(tmp_path), 'later.bin')
    c.events.put(dict(id=t.id, status='waiting', retry_after=7200))
    c.tick()
    assert c.retry_at[t.id] - time.monotonic() > 7190
    assert not c.workers
    c.close()


def test_torrent_completion_notice_occurs_before_seeding_finishes(tmp_path, monkeypatch):
    c = Controller(tmp_path, local_only=True)
    task = Task(source='test', destination=str(tmp_path), kind='torrent', selected=[0], status='downloading')
    c.tasks[task.id] = task
    monkeypatch.setattr(c.engine, 'tick', lambda: [dict(id=task.id, status='seeding', ratio=0)])
    notices = c.tick()
    assert task.status == 'seeding' and task in notices
    task.completion_notified = True
    c.settings.seed_enabled = False
    notices = c.tick()
    assert task.status == 'completed'
    assert all(t.completion_notified for t in notices)
    c.close()
