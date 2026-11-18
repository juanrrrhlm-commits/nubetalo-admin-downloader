import json
import sqlite3
import pytest
from nubetalo.domain import Task, Settings
from nubetalo.store import Store
from nubetalo.protection import protect, unprotect


def test_windows_protection_roundtrip_and_tamper_rejected():
    value = b'https://example.com/file?private=fixture-secret'
    encrypted = protect(value)
    assert value not in encrypted
    assert unprotect(encrypted) == value
    damaged = bytearray(encrypted)
    damaged[-1] ^= 1
    with pytest.raises(OSError):
        unprotect(bytes(damaged))


def test_queue_does_not_leave_private_url_in_database_or_wal(tmp_path):
    path = tmp_path / 'private.db'
    store = Store(path)
    task = Task(source='https://example.com/file?private=fixture-secret', destination=str(tmp_path))
    store.save_task(task)
    assert store.load_tasks()[0].source == task.source
    for file in tmp_path.iterdir():
        if file.is_file():
            assert b'fixture-secret' not in file.read_bytes()
    store.close()


def test_legacy_queue_migrates_without_losing_task_and_removes_plaintext(tmp_path):
    path = tmp_path / 'state.db'
    task = Task(source='https://example.com/file?private=legacy-fixture', destination=str(tmp_path))
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE tasks(id TEXT PRIMARY KEY,data TEXT NOT NULL); CREATE TABLE settings(id INTEGER PRIMARY KEY,data TEXT NOT NULL);')
    db.execute('INSERT INTO tasks VALUES(?,?)', (task.id, json.dumps(task.data())))
    db.execute('INSERT INTO settings VALUES(1,?)', (json.dumps(Settings(language='en').__dict__),))
    db.commit()
    db.close()
    store = Store(path)
    assert store.load_tasks()[0].source == task.source
    assert store.settings().language == 'en'
    store.close()
    assert b'legacy-fixture' not in path.read_bytes()
