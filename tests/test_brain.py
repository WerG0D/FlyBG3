import pytest
from flybg3.config import Config
from flybg3.brain.simulation import Simulation


@pytest.mark.brain
def test_real_connectome_causal_input_and_state(observation):
    config = Config()
    config.performance.device = "cpu"
    sim = Simulation(config)
    info = sim.brain.info()
    assert (info["neurons"], info["connections"], info["descending_neurons"]) == (166700, 25582938, 1314)
    observation["nearest_hostile"].update(relative_angle=-90., distance=4., closing_speed=4.)
    action, stimulated = sim.decide(observation)
    previous_steps = stimulated["neural_activity"]["steps_total"]
    _, continued = sim.decide(observation)
    assert continued["neural_activity"]["steps_total"] == previous_steps + config.brain.simulation_steps
    sim.reset()
    observation["nearest_hostile"] = None
    _, baseline = sim.decide(observation)
    assert stimulated["neural_activity"]["rates_hz"]["DNp01_L"] > baseline["neural_activity"]["rates_hz"]["DNp01_L"] + 5
    assert stimulated["neural_activity"]["rates_hz"]["DNp01_L"] > stimulated["neural_activity"]["rates_hz"]["DNp01_R"]
    assert action.action == "retreat"


@pytest.mark.brain
def test_decoder_has_no_sensory_bypass(observation):
    config = Config()
    sim = Simulation(config)
    import numpy as np
    sim.brain.brain.synaptic_input = lambda fired: sim.brain.brain.xp.zeros((sim.brain.brain.n, 1), np.float32)
    observation["nearest_hostile"].update(relative_angle=-90., closing_speed=8., distance=3.)
    _, stimulated = sim.decide(observation)
    sim.reset()
    observation["nearest_hostile"] = None
    _, baseline = sim.decide(observation)
    assert stimulated["neural_activity"]["spikes"] == baseline["neural_activity"]["spikes"]
    assert stimulated["scores"] == baseline["scores"]
