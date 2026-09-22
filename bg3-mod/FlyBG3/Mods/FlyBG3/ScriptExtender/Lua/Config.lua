FlyBG3Config = {
    Enabled = true,
    ControlledCharacter = "", -- populated only after verifying Flyman's own root template
    BodyTemplateUUID = "f8881547-6e53-44d4-943b-15cddef25f22",
    BodyTemplate = "FlyBG3_MudMephit_Flyman_f8881547-6e53-44d4-943b-15cddef25f22",
    Debug = true,
    Directory = "FlyBG3/", -- relative to Script Extender I/O root
    DecisionTimeoutMs = 3000,
    BrainHeartbeatMaxAgeMs = 5000,
    PollMs = 100,
    SampleIntervalMs = 200,
    MaxDistance = 30.0,
    HeadingOffsetDegrees = 0.0, -- calibration if a template's forward axis differs
    RequirePartyControl = true, -- player or party follower; never act as vanilla NPC
    PartyControlCheckDelayMs = 1500, -- allow CharacterJoinedParty to arrive before warning
    ImmortalForTesting = true, -- only Flyman's own template; !flybg3_immortal off to revert
    ImmortalityVerifyDelayMs = 200,
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
    AutoEndTurn = false -- opt-in: !flybg3_auto_end on
}
