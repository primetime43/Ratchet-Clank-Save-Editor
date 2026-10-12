-- Lua 5.0-compatible module. Loading it performs no grants or console calls.
-- Requires a separate, working in-game Lua loading/injection path; not an installer.
local M = {}

local function call_handle_helper(name, handle)
    local fn = _G[name]
    if type(fn) ~= "function" then return false, name .. " is unavailable" end
    if handle == nil then return false, "A valid in-game moby/hero handle is required" end
    -- Never fabricate an integer/pointer as a handle. Native diagnostic paths
    -- may continue instead of returning; pcall cannot contain a native crash.
    return pcall(fn, handle)
end

function M.available()
    return {
        ammo = type(_G.hero_give_all_ammo) == "function",
        ally_diagnostics = type(_G.ally_debug) == "function",
        console = type(_G.debug) == "table" and type(_G.debug.debug) == "function"
    }
end

function M.refill_ammo(hero_handle)
    return call_handle_helper("hero_give_all_ammo", hero_handle)
end

function M.ally_diagnostics(ally_handle)
    return call_handle_helper("ally_debug", ally_handle)
end

function M.open_console(allow_blocking)
    if allow_blocking ~= true then return false, "Console may block; explicit true is required" end
    if not M.available().console then return false, "debug.debug is unavailable" end
    -- The native loop exits on input end or 'cont' followed by a newline.
    -- Native streams have not been confirmed accessible from RPCS3.
    return pcall(_G.debug.debug)
end

return M
