from flybg3.config import Config
from flybg3.bridge.service import BridgeService
from flybg3.bridge.watcher import RequestJournal
from flybg3.bridge.atomic_io import read_json


def test_unavailable_brain_only_idle_and_never_reprocesses(tmp_path, observation):
    config = Config()
    config.bridge.directory = str(tmp_path)
    config.bridge.log_directory = str(tmp_path / "logs")
    service = BridgeService(config)
    journal = RequestJournal(tmp_path / "requests.sqlite3")
    assert service.process(observation, journal)
    action = read_json(tmp_path / "action.json")
    assert action["action"] == "idle"
    assert action["debug"]["error"] == "fly brain unavailable"
    assert not service.process(observation, journal)
    assert len(service.log_path.read_text().splitlines()) == 1
    journal.close()
