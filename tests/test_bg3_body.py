from pathlib import Path
import xml.etree.ElementTree as ET

from lupa import LuaRuntime


ROOT = Path("bg3-mod/FlyBG3")
LUA = ROOT / "Mods/FlyBG3/ScriptExtender/Lua"
FLYMAN_TEMPLATE = "f8881547-6e53-44d4-943b-15cddef25f22"
STOCK_MUD_MEPHIT = "f765566e-3f98-457b-9048-59bdcc66f51d"
HOST = "680c4c06-e50e-4382-bbee-2e5a76a2e9cb"  # synthetic test-only avatar
CREATED = "92181985-430f-4ef2-b31b-86655ed64988"


def test_flyman_is_a_separate_inherited_mud_mephit_template():
    root = ET.parse(ROOT / "Public/FlyBG3/RootTemplates/_merged.lsx")
    attrs = {a.get("id"): a for a in root.iter("attribute")}
    assert attrs["MapKey"].get("value") == FLYMAN_TEMPLATE
    assert attrs["ParentTemplateId"].get("value") == STOCK_MUD_MEPHIT
    assert attrs["Type"].get("value") == "character"
    assert attrs["Stats"].get("value") == "Mephit_Mud"
    locale = ET.parse(ROOT / "Localization/English/FlyBG3.xml")
    content = next(locale.iter("content"))
    assert content.get("contentuid") == attrs["DisplayName"].get("handle")
    assert content.text == "Flyman"


def body_runtime():
    runtime = LuaRuntime(unpack_returned_tuples=True)
    runtime.execute(f"""
        calls = {{created=0, party_follower=0, immortal_calls=0, immortal_state=0}}
        FlyBG3Config = {{
            BodyTemplateUUID="{FLYMAN_TEMPLATE}",
            BodyTemplate="FlyBG3_MudMephit_Flyman_{FLYMAN_TEMPLATE}"
        }}
        Ext = {{Entity={{
            Get=function(uuid) return {{}} end,
            GetAllEntitiesWithComponent=function(_) return {{}} end
        }}}}
        Osi = {{
            GetHostCharacter=function() return "{HOST}" end,
            IsCharacter=function(uuid) return 1 end,
            IsInCombat=function(uuid) return 0 end,
            IsPlayer=function(uuid) return 0 end,
            IsPartyFollower=function(uuid) return calls.party_follower end,
            IsImmortal=function(uuid) return calls.immortal_state end,
            GetTemplate=function(uuid)
                if uuid == "{CREATED}" then return FlyBG3Config.BodyTemplate end
                return "Avatar_11111111-1111-4111-8111-111111111111"
            end,
            CreateAtObject=function(template, anchor, temporary, play, event, orientation)
                assert(template == FlyBG3Config.BodyTemplate)
                assert(anchor == "{HOST}" and temporary == 0 and play == 0 and orientation == 1)
                calls.created = calls.created + 1
                return "{CREATED}"
            end,
            AddPartyFollower=function(target, owner)
                assert(target == "{CREATED}" and owner == "{HOST}")
                calls.party_follower = calls.party_follower + 1
            end,
            SetImmortal=function(target, enabled)
                assert(target == "{CREATED}")
                calls.immortal_calls = calls.immortal_calls + 1
                calls.immortal_state = enabled
            end
        }}
    """)
    runtime.execute((LUA / "Observation.lua").read_text(encoding="utf-8"))
    runtime.execute((LUA / "Body.lua").read_text(encoding="utf-8"))
    return runtime


def test_spawn_uses_separate_party_follower_and_never_recruits_host():
    runtime = body_runtime()
    assert runtime.globals().FlyBG3Body["isFlyman"](HOST) is False
    uuid, status = runtime.globals().FlyBG3Body["spawn"]()
    assert uuid == CREATED
    assert status == "created"
    assert runtime.globals().FlyBG3Body["isFlyman"](uuid) is True
    assert runtime.globals().calls["created"] == 1
    assert runtime.globals().calls["party_follower"] == 1


def test_spawn_refuses_combat_without_creating_npc():
    runtime = body_runtime()
    runtime.execute("Osi.IsInCombat=function(uuid) return 1 end")
    uuid, reason = runtime.globals().FlyBG3Body["spawn"]()
    assert uuid is None
    assert reason == "spawn_outside_combat_only"
    assert runtime.globals().calls["created"] == 0


def test_spawn_reuses_existing_flyman_instead_of_duplicating():
    runtime = body_runtime()
    runtime.execute(f"""
        Ext.Entity.GetAllEntitiesWithComponent=function(_)
            return {{{{Uuid={{EntityUuid="{CREATED}"}}, ServerCharacter={{}}}}}}
        end
    """)
    uuid, status = runtime.globals().FlyBG3Body["spawn"]()
    assert uuid == CREATED
    assert status == "existing"
    assert runtime.globals().calls["created"] == 0
    assert runtime.globals().calls["party_follower"] == 1


def test_immortality_is_restricted_to_flyman_template():
    runtime = body_runtime()
    failed, reason = runtime.globals().FlyBG3Body["setImmortal"](HOST, True)
    assert failed is False
    assert reason == "not_flyman"
    assert runtime.globals().calls["immortal_calls"] == 0
    assert runtime.globals().FlyBG3Body["setImmortal"](CREATED, True) is True
    assert runtime.globals().calls["immortal_state"] == 1
    assert runtime.globals().FlyBG3Body["setImmortal"](CREATED, False) is True
    assert runtime.globals().calls["immortal_state"] == 0
    assert runtime.globals().calls["immortal_calls"] == 2


def test_observation_requires_party_control_but_accepts_party_follower():
    runtime = body_runtime()
    runtime.execute("""
        FlyBG3Config.RequirePartyControl = true
        Osi.IsDead=function(_) return 0 end
        Osi.GetHitpoints=function(_) return 10 end
        Osi.IsInteractionDisabled=function(_) return 0 end
    """)
    assert runtime.globals().Observation["canAct"](CREATED) is False
    runtime.execute("calls.party_follower = 1")
    assert runtime.globals().Observation["canAct"](CREATED) is True


def test_sensory_scan_explains_missing_hostile_without_changing_observation():
    runtime = body_runtime()
    enemy = "efc81280-e859-4c93-b907-9b1645fcbb49"
    runtime.execute(f"""
        FlyBG3Config.MaxDistance = 30
        FlyBG3Config.HeadingOffsetDegrees = 0
        Ext.Timer = {{MonotonicTime=function() return 1000 end}}
        Ext.Entity.GetAllEntitiesWithComponent=function(_)
            return {{{{Uuid={{EntityUuid="{CREATED}"}}, ServerCharacter={{}}}},
                     {{Uuid={{EntityUuid="{enemy}"}}, ServerCharacter={{}}}}}}
        end
        Osi.GetPosition=function(uuid)
            if uuid == "{CREATED}" then return 0, 1, 0 end
            return 0, 1, 5
        end
        Osi.GetRotation=function(_) return 0, 0, 0 end
        Osi.GetHitpoints=function(_) return 10 end
        Osi.GetMaxHitpoints=function(_) return 10 end
        Osi.IsDead=function(_) return 0 end
        Osi.IsEnemy=function(_, _) return 0 end
        Osi.CanSee=function(_, _) return 1 end
    """)
    observation, scan = runtime.execute(f'return Observation.collect("{CREATED}", "session", 1, nil)')
    assert observation["nearest_hostile"] is None
    assert scan["characters"] == 1
    assert scan["hostile"] == 0
    runtime.execute("Osi.IsEnemy=function(_, _) return 1 end")
    observation, scan = runtime.execute(f' return Observation.collect("{CREATED}", "session", 1, nil)')
    assert observation["nearest_hostile"]["uuid"] == enemy
    assert scan["hostile"] == scan["in_range"] == scan["visible"] == 1


def test_legacy_avatar_binding_cannot_reactivate_on_load():
    runtime = body_runtime()
    runtime.execute(f"""
        saved_settings = {{npc_uuid="{HOST}"}}
        writes = {{}}
        console = {{}}
        Ext.IO = {{
            LoadFile=function(name)
                if name == "FlyBG3/settings.json" then return writes[name] or saved_settings end
                return nil
            end,
            SaveFile=function(name, value) writes[name] = value; return true end
        }}
        Ext.Json = {{
            Parse=function(value) return value end,
            Stringify=function(value) return value end
        }}
        Ext.Utils = {{
            GenerateGuid=function() return "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb" end,
            Print=function(_) end, PrintWarning=function(_) end
        }}
        Ext.Timer = {{ClockEpoch=function() return 1 end, WaitForRealtime=function(_, _) end}}
        Ext.Events = {{SessionLoaded={{Subscribe=function(_) end}}}}
        Ext.Osiris = {{RegisterListener=function(_, _, _, _) end}}
        Ext.RegisterConsoleCommand=function(name, handler) console[name]=handler end
        ActionExecutor = {{clear=function() end}}
        FlyBG3Config.Directory = "FlyBG3/"
        FlyBG3Config.OutOfCombatIntervalMs = 0
        FlyBG3Config.Enabled = true
        FlyBG3Config.ImmortalForTesting = true
        FlyBG3Config.ImmortalityVerifyDelayMs = 200
        FlyBG3Config.BrainHeartbeatMaxAgeMs = 5000
    """)
    runtime.execute((LUA / "FlyBG3.lua").read_text(encoding="utf-8"))
    ready, age = runtime.execute("return FlyBG3.brainStatus({alive=true, brain_loaded=true, unix_ms=1000})")
    assert ready is True and age == 0
    assert runtime.execute("return FlyBG3.brainStatus({alive=true, brain_loaded=true, unix_ms=-5000})")[0] is False
    assert runtime.execute("return FlyBG3.brainStatus({alive=true, brain_loaded=false, unix_ms=1000})")[0] is False
    runtime.globals().FlyBG3["start"]()
    assert runtime.globals().FlyBG3Config["ControlledCharacter"] == ""
    runtime.globals().console["flybg3_bind"]("flybg3_bind", HOST)
    assert runtime.globals().FlyBG3Config["ControlledCharacter"] == ""
    assert runtime.globals().writes["FlyBG3/settings.json"]["schema_version"] == 2

    runtime.globals().console["flybg3_spawn"]("flybg3_spawn")
    assert runtime.globals().FlyBG3Config["ControlledCharacter"] == CREATED
    assert runtime.globals().writes["FlyBG3/settings.json"]["npc_uuid"] == CREATED
    assert runtime.globals().calls["immortal_state"] == 1
    runtime.execute("calls.party_follower = 0")
    runtime.globals().console["flybg3_spawn"]("flybg3_spawn")
    assert runtime.globals().calls["created"] == 1
    assert runtime.globals().calls["party_follower"] == 1
    runtime.globals().console["flybg3_immortal"]("flybg3_immortal", "off")
    assert runtime.globals().calls["immortal_state"] == 0
    runtime.globals().console["flybg3_status"]("flybg3_status")
