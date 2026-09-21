from pathlib import Path
import json
import xml.etree.ElementTree as ET
from lupa import LuaRuntime

ROOT = Path("bg3-mod/FlyBG3/Mods/FlyBG3")
LUA = ROOT / "ScriptExtender/Lua"


def test_all_lua_parses():
    runtime = LuaRuntime()
    for path in LUA.glob("*.lua"):
        runtime.execute("assert(load(...))", path.read_text(encoding="utf-8"))


def test_physical_milestone_is_guarded():
    bootstrap = (LUA / "BootstrapServer.lua").read_text(encoding="utf-8")
    active = "\n".join(path.read_text(encoding="utf-8") for path in LUA.glob("*.lua"))
    executor = (LUA / "ActionExecutor.lua").read_text(encoding="utf-8")
    assert 'Ext.Require("ActionExecutor.lua")' in bootstrap
    assert "ActionExecutor.execute" in active
    assert "Osi.CharacterMoveToPosition" in executor
    for forbidden in ("Osi.EndTurn(", "PurgeOsirisQueue"):
        assert forbidden not in active
    assert '"Observation #" .. rid .. " sent"' in active
    assert '"Neural decision #" .. rid' in active


def test_action_executor_requires_current_stimulus_and_issues_move():
    runtime = LuaRuntime(unpack_returned_tuples=True)
    runtime.execute("""
        calls = { count = 0 }
        Osi = {
            IsInteractionDisabled = function(_) return 0 end,
            IsDead = function(_) return 0 end,
            GetHitpoints = function(_) return 10 end,
            IsInCombat = function(_) return 0 end,
            CharacterMoveToPosition = function(...) calls.count = calls.count + 1; calls.args = {...} end
        }
        Ext = {
            Entity = { Get = function(_) return {} end },
            Level = {
                BeginPathfindingImmediate = function(_, _) return {} end,
                FindPath = function(_) return true end,
                ReleasePath = function(_) end
            }
        }
        Observation = { uuid = function(value) return value end }
        FlyBG3Config = {
            PhysicalActionsEnabled = true,
            AllowOutOfCombatMovement = true,
            AllowCombatMovement = false,
            MovementDistance = 2.0,
            MovementSpeed = "Walk",
            MovementEvent = "",
            MovementId = 0
        }
    """)
    runtime.execute((LUA / "ActionExecutor.lua").read_text(encoding="utf-8"))
    no_stimulus = """
        return ActionExecutor.execute(
            {action="turn_left"},
            {npc={uuid="npc", heading_degrees=0, position={x=0, y=1, z=0}},
             combat={active=false, my_turn=false}, stimuli={damage_fraction=0}}
        )
    """
    ok, reason = runtime.execute(no_stimulus)
    assert ok is False
    assert reason == "no_current_stimulus"
    assert runtime.globals().calls["count"] == 0

    with_target = """
        return ActionExecutor.execute(
            {action="turn_left"},
            {npc={uuid="npc", heading_degrees=0, position={x=0, y=1, z=0}},
             combat={active=false, my_turn=false},
             nearest_hostile={uuid="enemy", relative_angle=-45, visible=true},
             stimuli={damage_fraction=0}}
        )
    """
    ok, reason = runtime.execute(with_target)
    assert ok is True
    assert reason == "issued"
    assert runtime.globals().calls["count"] == 1
    args = runtime.globals().calls["args"]
    assert args[1] == "npc"
    assert abs(args[2] + 2.0) < 1e-6  # lateral left step at yaw 0
    assert args[3] == 1
    assert args[4] == 0
    assert args[5] == "Walk"

    runtime.execute("calls.count = 0; Ext.Level.FindPath = function(_) return false end")
    ok, reason = runtime.execute(with_target)
    assert ok is False
    assert reason == "destination_unreachable"
    assert runtime.globals().calls["count"] == 0

    runtime.execute("Ext.Level.FindPath = function(_) return true end")
    combat_target = """
        return ActionExecutor.execute(
            {action="turn_right"},
            {npc={uuid="npc", heading_degrees=0, position={x=0, y=1, z=0}},
             combat={active=true, my_turn=true},
             nearest_hostile={uuid="enemy", relative_angle=45, visible=true},
             stimuli={damage_fraction=0}}
        )
    """
    ok, reason = runtime.execute(combat_target)
    assert ok is False
    assert reason == "combat_movement_disabled"
    assert runtime.globals().calls["count"] == 0


def test_manifest_files_parse():
    config = json.loads((ROOT / "ScriptExtender/Config.json").read_text())
    assert config == {"RequiredVersion": 30, "ModTable": "FlyBG3", "FeatureFlags": ["Lua"]}
    meta = ET.parse(ROOT / "meta.lsx")
    attrs = {a.attrib["id"]: a.attrib["value"] for a in meta.iter("attribute")}
    assert attrs["Folder"] == "FlyBG3"
    assert attrs["UUID"] == "4294373f-b1ea-41ec-91c2-50d0cdae06c7"
