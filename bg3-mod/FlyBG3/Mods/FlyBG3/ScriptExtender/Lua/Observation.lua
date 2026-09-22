Observation = {}

function Observation.uuid(value)
    if value == nil then return nil end
    local s = tostring(value):lower():match("([%x%-]+)$")
    if not s or #s ~= 36 or not s:match("^%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$") then
        return nil
    end
    return s
end

function Observation.position(uuid)
    local x, y, z = Osi.GetPosition(uuid)
    if x == nil or y == nil or z == nil then error("position unavailable: " .. uuid) end
    return {x=x, y=y, z=z}
end

function Observation.myTurn(uuid)
    local entity = Ext.Entity.Get(uuid)
    local turn = entity and entity.TurnBased
    return turn ~= nil and turn.IsActiveCombatTurn == true and turn.RequestedEndTurn ~= true
end

function Observation.canAct(uuid)
    if not Ext.Entity.Get(uuid) or Osi.IsCharacter(uuid) ~= 1 then return false end
    if Osi.IsDead(uuid) == 1 or (Osi.GetHitpoints(uuid) or 0) <= 0 then return false end
    if Osi.IsInteractionDisabled(uuid) == 1 then return false end
    if FlyBG3Config.RequirePartyControl and Osi.IsPlayer(uuid) ~= 1
            and Osi.IsPartyFollower(uuid) ~= 1 then return false end
    if Osi.IsInCombat(uuid) == 1 and not Observation.myTurn(uuid) then return false end
    return true
end

function Observation.collect(uuid, session, request, previous)
    local position = Observation.position(uuid)
    local _, yaw, _ = Osi.GetRotation(uuid)
    if yaw == nil then error("rotation unavailable") end
    yaw = yaw + FlyBG3Config.HeadingOffsetDegrees
    local hp, maxHp = Osi.GetHitpoints(uuid), Osi.GetMaxHitpoints(uuid)
    if not hp or not maxHp or maxHp <= 0 then error("health unavailable") end
    local now = Ext.Timer.MonotonicTime()
    local nearest, best = nil, FlyBG3Config.MaxDistance
    local scan = {characters=0, hostile=0, in_range=0, visible=0}
    -- Once per observation, never each Tick. Uuid enumeration is a documented
    -- SE API; IsCharacter/IsEnemy/CanSee are real Osiris queries.
    for _, entity in ipairs(Ext.Entity.GetAllEntitiesWithComponent("Uuid")) do
        local target = entity.Uuid and Observation.uuid(entity.Uuid.EntityUuid)
        if target and target ~= uuid and entity.ServerCharacter and Osi.IsDead(target) == 0 then
            scan.characters = scan.characters + 1
            if Osi.IsEnemy(uuid, target) == 1 then
                scan.hostile = scan.hostile + 1
                local p = Observation.position(target)
                local dx, dy, dz = p.x-position.x, p.y-position.y, p.z-position.z
                local distance = math.sqrt(dx*dx + dy*dy + dz*dz)
                if distance < FlyBG3Config.MaxDistance then
                    scan.in_range = scan.in_range + 1
                    if Osi.CanSee(uuid, target) == 1 then
                        scan.visible = scan.visible + 1
                        if distance < best then
                            best = distance
                            -- BG3 Y up, clockwise yaw in degrees; +Z is reference forward.
                            local bearing = math.deg(math.atan(dx, dz))
                            nearest = {uuid=target, distance=distance,
                                relative_angle=(bearing-yaw+180)%360-180, visible=true}
                        end
                    end
                end
            end
        end
    end
    local damage = 0
    if previous then
        local elapsed = (now-previous.sample_time_ms)/1000
        if nearest and previous.nearest_hostile and nearest.uuid == previous.nearest_hostile.uuid
                and elapsed >= 0.05 and elapsed <= 10 then
            nearest.closing_speed = (previous.nearest_hostile.distance-nearest.distance)/elapsed
        end
        damage = math.min(1, math.max(0, previous.npc.hp-hp)/maxHp)
    end
    return {schema_version=1, session_id=session, request_id=request, sample_time_ms=now,
        npc={uuid=uuid, hp=hp, max_hp=maxHp, position=position, heading_degrees=yaw},
        combat={active=Osi.IsInCombat(uuid)==1, my_turn=Observation.myTurn(uuid)},
        nearest_hostile=nearest, stimuli={damage_fraction=damage}}, scan
end
