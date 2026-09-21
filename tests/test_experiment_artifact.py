import json
from pathlib import Path

DECODER_GROUPS = {f"{name}_{side}" for name in ("DNa02", "DNp01", "DNg100", "MDN") for side in "LR"}


def test_real_experiment_artifact_is_complete():
    data = json.loads(Path("experiments/results.json").read_text(encoding="utf-8"))
    assert data["brain"]["neurons"] == 166700
    assert data["brain"]["connections"] == 25582938
    assert data["protocol"]["decoder_receives_only"] == "descending firing rates"
    assert len(data["seeds"]) >= 3 and len(set(data["seeds"])) == len(data["seeds"])
    scenarios = {scenario["name"]: scenario for scenario in data["scenarios"]}
    required = {"threat_left_low", "threat_left_medium", "threat_left_high",
                "threat_right_low", "threat_right_medium", "threat_right_high",
                "threat_front", "approaching_slowly", "approaching_quickly",
                "moving_away", "stationary", "no_stimulus", "left_to_right",
                "threat_then_silence"}
    assert required <= scenarios.keys()
    assert scenarios["left_to_right"]["input_phases"][0]["angle"] < 0
    assert scenarios["left_to_right"]["input_phases"][1]["angle"] > 0
    for scenario in scenarios.values():
        assert len({trial["seed"] for trial in scenario["trials"]}) == len(data["seeds"])
        for trial in scenario["trials"]:
            assert set(trial["decoder_input_rates_hz"]) == DECODER_GROUPS
            assert not DECODER_GROUPS & set(trial["other_descending_rates_hz"])
            assert trial["stimulus"] and trial["latency_ms"] > 0
            assert "network_mean_voltage" in trial["residual_state"]


def test_key_emergent_results_are_reproducible_across_seeds():
    data = json.loads(Path("experiments/results.json").read_text(encoding="utf-8"))
    scenarios = {scenario["name"]: scenario for scenario in data["scenarios"]}
    assert scenarios["threat_left_low"]["phase_summaries"][0]["decision_counts"] == {"turn_left": 5}
    assert scenarios["threat_right_low"]["phase_summaries"][0]["decision_counts"] == {"turn_right": 5}
    sequence = scenarios["left_to_right"]["phase_summaries"]
    assert [phase["decision_counts"] for phase in sequence] == [{"turn_left": 5}, {"turn_right": 5}]
    persistence = scenarios["threat_then_silence"]["phase_summaries"]
    assert persistence[0]["decision_counts"] == {"retreat": 5}
    assert persistence[1]["decision_counts"] == {"retreat": 5}
