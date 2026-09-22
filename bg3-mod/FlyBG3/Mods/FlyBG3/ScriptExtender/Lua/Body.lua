-- Flyman's identity is the mod-owned root template, never a player's UUID.
-- Its parent is the stock MEPHIT_Mud_A root from Shared.pak.
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

function FlyBG3Body.spawn()
    local existing = FlyBG3Body.findExisting()
    if existing then return existing, "existing" end
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

    -- MakePlayer assigns this *separate* creature to the host's user and
    -- prevents vanilla NPC AI competing with neural decisions. It adds a
    -- party portrait; the host's avatar itself is never modified.
    local okPlayer, playerError = pcall(Osi.MakePlayer, uuid, hostUuid, 0)
    if not okPlayer then return nil, "MakePlayer_failed for " .. uuid .. ": " .. tostring(playerError) end
    return uuid, "created"
end
