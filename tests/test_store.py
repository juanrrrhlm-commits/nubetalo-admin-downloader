from nubetalo.domain import Task, Settings
from nubetalo.store import Store


def test_manual_pause_and_settings_survive_reopen(tmp_path):
    db = tmp_path / 'state.db'
    s = Store(db)
    task = Task(source='https://example.com/a', destination=str(tmp_path), manual_pause=True)
    s.save_task(task)
    config = Settings(download_limit=100000, language='en')
    s.save_settings(config)
    s.close()
    s = Store(db)
    assert s.load_tasks()[0].manual_pause is True
    assert s.settings().download_limit == 100000
    assert s.settings().language == 'en'
    s.delete_task(task.id)
    assert s.load_tasks() == []
    s.close()
