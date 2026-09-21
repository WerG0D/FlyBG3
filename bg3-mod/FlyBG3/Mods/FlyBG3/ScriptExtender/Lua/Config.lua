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
    OutOfCombatIntervalMs = 0 -- 0: manual !flybg3_observe only; no autonomous walking
}
