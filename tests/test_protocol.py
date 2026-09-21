import json
import pytest
from flybg3.bridge.protocol import Action, ProtocolError, validate_observation, validate_action, response_matches
from flybg3.bridge.watcher import RequestJournal


def test_serialization_and_stale_response(observation):
    validate_observation(observation)
    action = Action(observation["session_id"], 1, observation["npc"]["uuid"]).to_dict()
    assert validate_action(json.loads(json.dumps(action))) == action
    assert response_matches(action, observation)
    observation["request_id"] = 2
    assert not response_matches(action, observation)
    observation["request_id"] = 1
    from uuid import uuid4
    observation["session_id"] = str(uuid4())
    assert not response_matches(action, observation)


@pytest.mark.parametrize("key,value", [("schema_version", 2), ("schema_version", True), ("request_id", True),
                                      ("request_id", -1), ("request_id", 1.5), ("session_id", "fake"),
                                      ("sample_time_ms", float("nan"))])
def test_bad_envelope(observation, key, value):
    observation[key] = value
    with pytest.raises(ProtocolError):
        validate_observation(observation)


def test_claim_survives_restart(tmp_path):
    path = tmp_path / "journal.sqlite3"
    j = RequestJournal(path)
    assert j.claim("session", 10)
    assert not j.claim("session", 10)
    j.close()
    j = RequestJournal(path)
    assert not j.claim("session", 9)
    assert not j.claim("session", 10)
    assert j.claim("session", 11)
    assert j.claim("new-session", 1)
    j.close()
