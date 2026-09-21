FlyBG3Config = {
    Enabled = true,
    ControlledCharacter = "", -- actual save UUID; configure with !flybg3_bind UUID
    Debug = true,
    Directory = "FlyBG3/", -- relative to Script Extender I/O root
    DecisionTimeoutMs = 3000,
    PollMs = 100,
    SampleIntervalMs = 200,
    MaxDistance = 30.0,
    HeadingOffsetDegrees = 0.0, -- calibration if a template's forward axis differs
    RequirePlayerControlled = true, -- use recruited companion/hireling, avoid vanilla NPC AI
    OutOfCombatIntervalMs = 0, -- 0: manual !flybg3_observe only; no autonomous walking

    -- Physical milestone: movement is issued only after a neural action has
    -- arrived and the observation still contains a current stimulus. The
    -- default uses CharacterMoveToPosition outside combat; that Osiris call
    -- bypasses AP/turn economy, so combat movement stays opt-in.
    PhysicalActionsEnabled = true,
    AllowOutOfCombatMovement = true,
    AllowCombatMovement = false,
    MovementDistance = 2.0,
    MovementSpeed = "Walk",
    MovementEventPrefix = "FlyBG3_Move_",
    MovementId = 0, -- 0 derives a unique ID from request_id
    MovementCompletionTimeoutMs = 10000,
    EndTurnAfterPhysicalAction = false -- opt-in: !flybg3_auto_end on
}
