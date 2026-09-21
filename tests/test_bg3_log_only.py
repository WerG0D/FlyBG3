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


def test_active_milestone_is_log_only():
    bootstrap = (LUA / "BootstrapServer.lua").read_text(encoding="utf-8")
    active = "\n".join(path.read_text(encoding="utf-8") for path in LUA.glob("*.lua"))
    assert "ActionExecutor.lua" not in bootstrap
    for forbidden in ("CharacterMoveTo", "Osi.EndTurn(", "PurgeOsirisQueue", "BeginPathfinding"):
        assert forbidden not in active
    assert '"Observation #" .. rid .. " sent"' in active
    assert '"Neural decision #" .. rid' in active


def test_manifest_files_parse():
    config = json.loads((ROOT / "ScriptExtender/Config.json").read_text())
    assert config == {"RequiredVersion": 30, "ModTable": "FlyBG3", "FeatureFlags": ["Lua"]}
    meta = ET.parse(ROOT / "meta.lsx")
    attrs = {a.attrib["id"]: a.attrib["value"] for a in meta.iter("attribute")}
    assert attrs["Folder"] == "FlyBG3"
    assert attrs["UUID"] == "4294373f-b1ea-41ec-91c2-50d0cdae06c7"
