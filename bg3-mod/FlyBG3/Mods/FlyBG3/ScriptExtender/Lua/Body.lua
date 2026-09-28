FlyBG3Body = {}

function FlyBG3Body.isFlyman(value)
    local uuid = Observation.uuid(value)
    if not uuid or not Ext.Entity.Get(uuid) or Osi.IsCharacter(uuid) ~= 1 then return false end
    local ok, template = pcall(Osi.GetTemplate, uuid)
    return ok and Observation.uuid(template) == FlyBG3Config.BodyTemplateUUID
end

function FlyBG3Body.findExisting()
    for _, entity in ipairs(Ext.Entity.GetAllEntitiesWithComponent("Uuid")) do
        local uuid = entity.Uuid and Observation.uuid(entity.Uuid.EntityUuid)
        if uuid and entity.ServerCharacter and FlyBG3Body.isFlyman(uuid) then return uuid end
    end
    return nil
end

function FlyBG3Body.attach(uuid)
    if not FlyBG3Body.isFlyman(uuid) then return false, "not_flyman" end
    local okHost, host = pcall(Osi.GetHostCharacter)
    local hostUuid = okHost and Observation.uuid(host) or nil
    if not hostUuid or not Ext.Entity.Get(hostUuid) or Osi.IsCharacter(hostUuid) ~= 1 then
        return false, "host_character_unavailable"
    end
    if Osi.IsInCombat(hostUuid) == 1 then return false, "attach_outside_combat_only" end
    if Osi.IsPartyFollower(uuid) == 1 or Osi.IsPlayer(uuid) == 1 then
        return true, "already_controlled"
    end

    local okFollower, followerError = pcall(Osi.AddPartyFollower, uuid, hostUuid)
    if not okFollower then return false, "AddPartyFollower_failed: " .. tostring(followerError) end
    return true, "requested"
end

function FlyBG3Body.setImmortal(uuid, enabled)
    if not FlyBG3Body.isFlyman(uuid) then return false, "not_flyman" end
    local ok, reason = pcall(Osi.SetImmortal, uuid, enabled and 1 or 0)
    if not ok then return false, "SetImmortal_failed: " .. tostring(reason) end
    return true
end

function FlyBG3Body.spawn()
    local existing = FlyBG3Body.findExisting()
    if existing then
        local attached, reason = FlyBG3Body.attach(existing)
        if not attached then return nil, reason end
        return existing, "existing"
    end
    local okHost, host = pcall(Osi.GetHostCharacter)
    local hostUuid = okHost and Observation.uuid(host) or nil
    if not hostUuid or not Ext.Entity.Get(hostUuid) or Osi.IsCharacter(hostUuid) ~= 1 then
        return nil, "host_character_unavailable"
    end
    if Osi.IsInCombat(hostUuid) == 1 then return nil, "spawn_outside_combat_only" end

    local okCreate, created = pcall(Osi.CreateAtObject,
        FlyBG3Config.BodyTemplate, hostUuid, 0, 0, "", 1)
    local uuid = okCreate and Observation.uuid(created) or nil
    if not uuid then return nil, "CreateAtObject_failed: " .. tostring(created) end
    if not FlyBG3Body.isFlyman(uuid) then
        return nil, "spawned_template_mismatch: " .. tostring(created)
    end

    local attached, reason = FlyBG3Body.attach(uuid)
    if not attached then return nil, "created " .. uuid .. " but " .. tostring(reason) end
    return uuid, "created"
end
