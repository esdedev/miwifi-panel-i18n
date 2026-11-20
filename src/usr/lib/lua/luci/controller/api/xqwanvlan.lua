-- WAN VLAN (802.1Q) API for the stock MiWiFi web panel (tested on RD15 1.0.87).
-- Same auth as the stock API: admin session + stok token (jsonauth).
--
--   GET  /cgi-bin/luci/;stok=<t>/api/xqwanvlan/get
--   POST /cgi-bin/luci/;stok=<t>/api/xqwanvlan/set   enable=0|1  vid=1..4094
--
-- Stores the setting in the firmware's own (hidden) options
--   port_service.wan.wantag, port_service.wantag_attr.vid
-- and re-runs `port_service restart wan`. The patched arch_ps_setup_wan()
-- then uses the tagged device (e.g. eth0.1.20) for network.wan.
module("luci.controller.api.xqwanvlan", package.seeall)

function index()
    local page = node("api", "xqwanvlan")
    page.target = firstchild()
    page.title = ""
    page.order = 400
    page.sysauth = "admin"
    page.sysauth_authenticator = "jsonauth"
    page.index = true
    entry({"api", "xqwanvlan", "get"}, call("getWanVlan"), "", 401)
    entry({"api", "xqwanvlan", "set"}, call("setWanVlan"), "", 402)
end

local http = require("luci.http")

local function json_value(v)
    local t = type(v)
    if t == "number" then
        return tostring(v)
    elseif t == "boolean" then
        return v and "true" or "false"
    end
    local s = tostring(v or "")
    s = s:gsub('[%c"\\]', function(c)
        return string.format("\\u%04x", c:byte())
    end)
    return '"' .. s .. '"'
end

local function reply(tbl)
    local parts = {}
    for k, v in pairs(tbl) do
        parts[#parts + 1] = json_value(k) .. ":" .. json_value(v)
    end
    http.prepare_content("application/json")
    http.write("{" .. table.concat(parts, ",") .. "}")
end

local function cursor()
    return require("luci.model.uci").cursor()
end

-- VLAN ids the internal switch already uses for the LAN/WAN ports (port_map *.vid).
local function switch_vids(c)
    local used = {}
    local all = c:get_all("port_map") or {}
    for _, s in pairs(all) do
        if type(s) == "table" and s.vid then
            used[tostring(s.vid)] = true
        end
    end
    return used
end

function getWanVlan()
    local c = cursor()
    reply({
        code = 0,
        enable = (c:get("port_service", "wan", "wantag") == "1") and 1 or 0,
        vid = c:get("port_service", "wantag_attr", "vid") or "",
        port = c:get("port_service", "wan", "ports") or "",
        ifname = c:get("network", "wan", "ifname") or "",
        proto = c:get("network", "wan", "proto") or ""
    })
end

function setWanVlan()
    local enable = http.formvalue("enable")
    local vid = http.formvalue("vid") or ""
    if enable ~= "0" and enable ~= "1" then
        return reply({code = 1, msg = "enable must be 0 or 1"})
    end
    local c = cursor()
    if enable == "1" then
        local n = vid:match("^%d+$") and tonumber(vid)
        if not n or n < 1 or n > 4094 then
            return reply({code = 2, msg = "VLAN ID must be a number from 1 to 4094"})
        end
        vid = tostring(n)
        if switch_vids(c)[vid] then
            return reply({code = 3, msg = "VLAN ID " .. vid .. " is used internally by the switch"})
        end
    end
    if not c:get("port_service", "wantag_attr") then
        c:section("port_service", "attr", "wantag_attr", {})
    end
    c:set("port_service", "wan", "wantag", enable)
    if enable == "1" then
        c:set("port_service", "wantag_attr", "vid", vid)
    end
    c:commit("port_service")
    -- Constant command line: no user input reaches the shell.
    os.execute("(sleep 2; /usr/sbin/port_service restart wan) >/dev/null 2>&1 &")
    reply({code = 0})
end
