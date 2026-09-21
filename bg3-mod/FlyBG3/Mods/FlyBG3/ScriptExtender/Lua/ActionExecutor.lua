-- Reserved for the physical-action milestone.
-- This file is intentionally not loaded by BootstrapServer.lua.
ActionExecutor = {}

function ActionExecutor.execute(_action, _observation)
    return false, "FlyBG3 is in log-only mode; physical actions are not implemented"
end
