-- Physical-action milestone.
--
-- The decoder still receives only descending-neuron activity. This module
-- consumes the already-decoded action and the matching observation solely to
-- turn a neural command into a small, bounded movement request. It never
-- chooses an action from position, distance, direction, or speed.
ActionExecutor = {pending=nil}

local function number(value, fallback)
    if type(value) == "number" and value == value and value < math.huge and value > -math.huge then
        return value
    end
    return fallback
end

local function hasCurrentStimulus(observation)
    local nearest = observation and observation.nearest_hostile
    if type(nearest) == "table" and nearest.visible ~= false then return true end
    local stimuli = observation and observation.stimuli
    return type(stimuli) == "table" and number(stimuli.damage_fraction, 0) > 0
end

local function destination(actionName, observation)
    if not hasCurrentStimulus(observation) then return nil, "no_current_stimulus" end
    local npc, position = observation.npc, observation.npc and observation.npc.position
    if type(npc) ~= "table" or type(position) ~= "table" then return nil, "position_unavailable" end

    local yaw = math.rad(number(npc.heading_degrees, 0))
    local dx, dz
    local nearest = observation.nearest_hostile
    if actionName == "turn_left" then
        dx, dz = -math.cos(yaw), math.sin(yaw)
    elseif actionName == "turn_right" then
        dx, dz = math.cos(yaw), -math.sin(yaw)
    elseif actionName == "approach" or actionName == "retreat" then
        if type(nearest) ~= "table" then return nil, "target_unavailable" end
        local bearing = yaw + math.rad(number(nearest.relative_angle, 0))
        dx, dz = math.sin(bearing), math.cos(bearing)
        if actionName == "retreat" then dx, dz = -dx, -dz end
    else
        return nil, "unsupported_action"
    end

    local distance = math.max(0.25, math.min(5.0, number(FlyBG3Config.MovementDistance, 2.0)))
    return {x=number(position.x, 0) + dx * distance,
        y=number(position.y, 0), z=number(position.z, 0) + dz * distance}
end

local function currentGate(uuid, observation)
    if not FlyBG3Config.PhysicalActionsEnabled then return false, "physical_actions_disabled" end
    if not observation or not observation.combat then return false, "combat_state_unavailable" end
    if observation.combat.active and not observation.combat.my_turn then return false, "not_my_turn" end
    if observation.combat.active and not FlyBG3Config.AllowCombatMovement then
        return false, "combat_movement_disabled" end
    if not observation.combat.active and not FlyBG3Config.AllowOutOfCombatMovement then
        return false, "out_of_combat_movement_disabled" end
    if Osi.IsInteractionDisabled(uuid) == 1 then return false, "interaction_disabled" end
    if Osi.IsDead(uuid) == 1 or (Osi.GetHitpoints(uuid) or 0) <= 0 then return false, "dead_or_down" end
    -- Re-check the live engine state after the Python round trip. The
    -- observation is not trusted to authorize a stale movement request.
    if Osi.IsInCombat(uuid) == 1 and not FlyBG3Config.AllowCombatMovement then
        return false, "combat_started_during_round_trip" end
    return true
end

local function reachable(uuid, point)
    if not Ext or not Ext.Level or type(Ext.Level.BeginPathfindingImmediate) ~= "function" then
        return false, "pathfinding_unavailable"
    end
    local entity = Ext.Entity.Get(uuid)
    if not entity then return false, "entity_unavailable" end
    -- glm::vec3 is marshalled by BG3SE from a positional Lua table. A keyed
    -- {x=..., y=..., z=...} table is convenient internally, but is not a vec3
    -- at the native boundary and makes request creation fail.
    local target = {point.x, point.y, point.z}
    local started, path = pcall(Ext.Level.BeginPathfindingImmediate, entity, target)
    if not started then
        return false, "pathfinding_request_failed: " .. tostring(path)
    end
    if not path then return false, "pathfinding_request_failed: no_path" end
    local found, result = pcall(Ext.Level.FindPath, path)
    local released, releaseError = pcall(Ext.Level.ReleasePath, path)
    if not released then
        return false, "pathfinding_release_failed: " .. tostring(releaseError)
    end
    if not found then return false, "pathfinding_failed: " .. tostring(result) end
    if result ~= true then return false, "destination_unreachable" end
    return true
end

local function movementIdentity(action)
    local requestId = math.max(1, math.floor(number(action.request_id, 1)))
    local configured = math.floor(number(FlyBG3Config.MovementId, 0))
    local moveId = configured ~= 0 and configured or requestId % 2147483647
    if moveId == 0 then moveId = 1 end
    return tostring(FlyBG3Config.MovementEventPrefix or "FlyBG3_Move_") .. tostring(requestId), moveId, requestId
end

function ActionExecutor.consumeArrival(uuid, event)
    local pending = ActionExecutor.pending
    if pending and Observation.uuid(uuid) == pending.uuid and tostring(event) == pending.event then
        ActionExecutor.pending = nil
        return pending
    end
end

function ActionExecutor.consumeCancellation(uuid, moveId)
    local pending = ActionExecutor.pending
    if pending and Observation.uuid(uuid) == pending.uuid and number(moveId, -1) == pending.move_id then
        ActionExecutor.pending = nil
        return pending
    end
end

function ActionExecutor.expire(expected)
    if ActionExecutor.pending == expected then
        ActionExecutor.pending = nil
        return expected
    end
end

function ActionExecutor.isPending(expected)
    return ActionExecutor.pending == expected
end

function ActionExecutor.clear()
    ActionExecutor.pending = nil
end

function ActionExecutor.execute(action, observation)
    if type(action) ~= "table" then return false, "invalid_action" end
    local actionName = tostring(action.action or ""):lower()
    if actionName == "idle" then return true, "idle" end
    local uuid = Observation.uuid(observation and observation.npc and observation.npc.uuid)
    if not uuid then return false, "npc_uuid_unavailable" end
    if ActionExecutor.pending then return false, "physical_action_in_progress" end
    local allowed, reason = currentGate(uuid, observation)
    if not allowed then return false, reason end
    local point, pointReason = destination(actionName, observation)
    if not point then return false, pointReason end
    local pathOk, pathReason = reachable(uuid, point)
    if not pathOk then return false, pathReason end
    -- Osiris names are BG3SE LightCppValue callable proxies, not ordinary Lua
    -- functions. Calling through pcall both supports that proxy and reports a
    -- useful error if this name/arity is absent in the loaded game build.
    local event, moveId, requestId = movementIdentity(action)
    local completion = {uuid=uuid, event=event, move_id=moveId,
        request_id=requestId, action=actionName}
    ActionExecutor.pending = completion -- set before call; arrival may be synchronous
    local ok, errorMessage = pcall(Osi.CharacterMoveToPosition, uuid, point.x, point.y, point.z,
        tostring(FlyBG3Config.MovementSpeed or "Walk"), event, moveId)
    if not ok then
        ActionExecutor.expire(completion)
        return false, "CharacterMoveToPosition_failed: " .. tostring(errorMessage)
    end
    return true, "issued", completion
end
