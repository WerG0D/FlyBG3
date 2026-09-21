FlyBG3 = {session=nil, request=0, pending=nil, sampling=false, previous=nil}
local allowed = {idle=true, approach=true, retreat=true, turn_left=true, turn_right=true}
local function log(message) Ext.Utils.Print("[FlyBG3] " .. message) end
local function warn(message) Ext.Utils.PrintWarning("[FlyBG3] " .. message) end

local function finishTurn(completion)
    if not FlyBG3Config.AutoEndTurn then return end
    local uuid = completion and completion.uuid
    if not uuid or Osi.IsInCombat(uuid) ~= 1 or not Observation.myTurn(uuid) then return end
    local ok, reason = pcall(Osi.EndTurn, uuid)
    if ok then
        log("Turn end requested after neural decision #" .. tostring(completion.request_id))
    else
        warn("EndTurn failed after decision #" .. tostring(completion.request_id) .. ": " .. tostring(reason))
    end
end

local function read(name)
    local content = Ext.IO.LoadFile(FlyBG3Config.Directory .. name)
    if not content or #content > 262144 then return nil end
    local ok, data = pcall(Ext.Json.Parse, content)
    if ok and type(data) == "table" then return data end
    return nil
end

local function save(name, data)
    local ok = Ext.IO.SaveFile(FlyBG3Config.Directory .. name, Ext.Json.Stringify(data))
    if not ok then error("cannot write " .. name) end
end

function FlyBG3.heartbeat()
    if not FlyBG3.session then return end
    save("heartbeat_bg3.json", {schema_version=1, alive=true, session_id=FlyBG3.session,
        unix_ms=Ext.Timer.ClockEpoch()*1000, last_request=FlyBG3.request})
end

local function matches(action, pending)
    return type(action) == "table" and action.schema_version == 1
        and action.session_id == pending.observation.session_id
        and action.request_id == pending.observation.request_id
        and type(action.request_id) == "number" and action.request_id%1 == 0
        and Observation.uuid(action.npc_uuid) == pending.observation.npc.uuid
        and allowed[action.action] == true
        and type(action.confidence) == "number" and action.confidence >= 0 and action.confidence <= 1
end
FlyBG3.matches = matches -- unit-tested without BG3; no game API mocked as evidence of live operation

local function poll(session, rid)
    local p = FlyBG3.pending
    if not p or FlyBG3.session ~= session or p.observation.request_id ~= rid then return end
    if not FlyBG3Config.Enabled or not Observation.canAct(p.observation.npc.uuid) then
        FlyBG3.pending = nil
        return
    end
    -- Deadline checked BEFORE file, so a late response can never move an actor.
    if Ext.Timer.MonotonicTime() >= p.deadline then
        FlyBG3.pending = nil
        warn("Decision timeout #" .. rid .. "; IDLE (log-only mode)")
        return
    end
    local response = read("action.json")
    if response and matches(response, p) then
        FlyBG3.pending = nil -- consume before invoking engine; at most once
        log("Neural decision #" .. rid .. ": " .. string.upper(response.action))
        if response.action ~= "idle" then
            local executed, issued, reason, completion = pcall(ActionExecutor.execute, response, p.observation)
            if not executed then
                warn("Action executor failed #" .. rid .. ": " .. tostring(issued))
            elseif issued then
                log("Physical action #" .. rid .. ": " .. string.upper(response.action) .. " (" .. tostring(reason) .. ")")
                if completion and ActionExecutor.isPending(completion) then
                    Ext.Timer.WaitForRealtime(FlyBG3Config.MovementCompletionTimeoutMs, function()
                        local expired = ActionExecutor.expire(completion)
                        if expired then warn("Physical action #" .. rid .. " completion timeout") end
                    end)
                end
            else
                warn("Physical action skipped #" .. rid .. ": " .. tostring(reason))
            end
        else
            finishTurn({uuid=p.observation.npc.uuid, request_id=rid, action="idle"})
        end
        return
    end
    Ext.Timer.WaitForRealtime(FlyBG3Config.PollMs, function() poll(session, rid) end)
end

function FlyBG3.requestObservation()
    local uuid = Observation.uuid(FlyBG3Config.ControlledCharacter)
    if not FlyBG3.session or not FlyBG3Config.Enabled or not uuid then return end
    if FlyBG3.pending or FlyBG3.sampling then return end
    if not Observation.canAct(uuid) then warn("Flyman cannot act or is not player-controlled"); return end
    local session = FlyBG3.session
    FlyBG3.request = FlyBG3.request + 1
    local rid = FlyBG3.request
    local ok, first = pcall(Observation.collect, uuid, session, rid, FlyBG3.previous)
    if not ok then warn("Observation failed: " .. tostring(first)); return end
    FlyBG3.sampling = true
    Ext.Timer.WaitForRealtime(FlyBG3Config.SampleIntervalMs, function()
        if FlyBG3.session ~= session or FlyBG3.request ~= rid then return end
        FlyBG3.sampling = false
        if not FlyBG3Config.Enabled or not Observation.canAct(uuid) then return end
        local collected, observation = pcall(Observation.collect, uuid, session, rid, first)
        if not collected then warn("Observation failed: " .. tostring(observation)); return end
        observation.stimuli.damage_fraction = math.min(1, first.stimuli.damage_fraction + observation.stimuli.damage_fraction)
        FlyBG3.previous = observation
        local written, reason = pcall(function()
            FlyBG3.heartbeat()
            save("observation.json", observation)
        end)
        if not written then warn("Observation I/O failed: " .. tostring(reason)); return end
        FlyBG3.pending = {observation=observation, deadline=Ext.Timer.MonotonicTime()+FlyBG3Config.DecisionTimeoutMs}
        log("Observation #" .. rid .. " sent")
        poll(session, rid)
    end)
end

local function heartbeatLoop(session)
    if FlyBG3.session ~= session then return end
    local ok, reason = pcall(FlyBG3.heartbeat)
    if not ok then warn(tostring(reason)) end
    Ext.Timer.WaitForRealtime(1000, function() heartbeatLoop(session) end)
end

local function autonomousLoop(session)
    if FlyBG3.session ~= session or FlyBG3Config.OutOfCombatIntervalMs <= 0 then return end
    local uuid = Observation.uuid(FlyBG3Config.ControlledCharacter)
    if uuid and Ext.Entity.Get(uuid) and Osi.IsInCombat(uuid) == 0 then FlyBG3.requestObservation() end
    Ext.Timer.WaitForRealtime(FlyBG3Config.OutOfCombatIntervalMs, function() autonomousLoop(session) end)
end

function FlyBG3.start()
    ActionExecutor.clear()
    FlyBG3.session = tostring(Ext.Utils.GenerateGuid())
    FlyBG3.request, FlyBG3.pending, FlyBG3.sampling, FlyBG3.previous = 0, nil, false, nil
    local persisted = read("settings.json")
    if persisted and Observation.uuid(persisted.npc_uuid) then
        FlyBG3Config.ControlledCharacter = Observation.uuid(persisted.npc_uuid)
    end
    log("Flyman adapter loaded. UUID=" .. FlyBG3Config.ControlledCharacter)
    heartbeatLoop(FlyBG3.session)
    autonomousLoop(FlyBG3.session)
end

Ext.Events.SessionLoaded:Subscribe(function() FlyBG3.start() end)
Ext.Osiris.RegisterListener("TurnStarted", 1, "after", function(character)
    if Observation.uuid(character) == Observation.uuid(FlyBG3Config.ControlledCharacter) then
        log("Flyman's turn")
        FlyBG3.requestObservation()
    end
end)
Ext.Osiris.RegisterListener("TurnEnded", 1, "after", function(character)
    if Observation.uuid(character) == Observation.uuid(FlyBG3Config.ControlledCharacter) then
        FlyBG3.pending, FlyBG3.sampling = nil, false
        ActionExecutor.clear()
        FlyBG3.request = FlyBG3.request + 1 -- invalidates in-flight sample callbacks
    end
end)
Ext.Osiris.RegisterListener("EntityEvent", 2, "after", function(object, event)
    local completion = ActionExecutor.consumeArrival(object, event)
    if completion then
        log("Physical action #" .. tostring(completion.request_id) .. " completed")
        finishTurn(completion)
    end
end)
Ext.Osiris.RegisterListener("CharacterMoveToCancelled", 2, "after", function(character, moveId)
    local completion = ActionExecutor.consumeCancellation(character, moveId)
    if completion then
        warn("Physical action #" .. tostring(completion.request_id) .. " cancelled")
    end
end)

Ext.RegisterConsoleCommand("flybg3_bind", function(_, value)
    local uuid = Observation.uuid(value)
    if not uuid or not Ext.Entity.Get(uuid) or Osi.IsCharacter(uuid) ~= 1 then
        warn("Provide an existing character UUID from this save")
        return
    end
    FlyBG3.pending, FlyBG3.sampling = nil, false
    FlyBG3Config.ControlledCharacter = uuid
    save("settings.json", {npc_uuid=uuid})
    FlyBG3.start() -- independent brain experiment for new actor
    log("Flyman bound to " .. uuid)
end)
Ext.RegisterConsoleCommand("flybg3_observe", function() FlyBG3.requestObservation() end)
Ext.RegisterConsoleCommand("flybg3_stop", function()
    FlyBG3Config.Enabled = false
    FlyBG3.pending, FlyBG3.sampling = nil, false
    ActionExecutor.clear()
    FlyBG3.request = FlyBG3.request + 1
    log("Stopped")
end)
Ext.RegisterConsoleCommand("flybg3_start", function()
    FlyBG3Config.Enabled = true
    if not FlyBG3.session then FlyBG3.start() end
    log("Enabled")
end)
Ext.RegisterConsoleCommand("flybg3_physical", function(_, value)
    local enabled = tostring(value or ""):lower() == "on"
    FlyBG3Config.PhysicalActionsEnabled = enabled
    log("Physical actions " .. (enabled and "enabled" or "disabled"))
end)
Ext.RegisterConsoleCommand("flybg3_combat_move", function(_, value)
    local enabled = tostring(value or ""):lower() == "on"
    FlyBG3Config.AllowCombatMovement = enabled
    log("Combat movement " .. (enabled and "enabled" or "disabled") ..
        " (CharacterMoveToPosition bypasses AP/turn economy)")
end)
Ext.RegisterConsoleCommand("flybg3_auto_end", function(_, value)
    local enabled = tostring(value or ""):lower() == "on"
    FlyBG3Config.AutoEndTurn = enabled
    log("Automatic EndTurn after neural decision " .. (enabled and "enabled" or "disabled"))
end)
