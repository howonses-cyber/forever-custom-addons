-- Forever Party in Raid 1.1.0: EUI NATIVE PARTY FRAME VISIBILITY BRIDGE.
-- No custom health bars, unit frames, header, or party window is created.
-- Uses the user's existing EllesmereUI Raid & Party Frames and its saved layout.
-- This adapter does not copy or modify EllesmereUI source files.
-- Uses an internal EUI namespace; an EUI update may require this adapter to be revised.

local addon = ...
local IsInRaid, InCombatLockdown = IsInRaid, InCombatLockdown
local GetRaidRosterInfo, UnitInRaid = GetRaidRosterInfo, UnitInRaid
local UnitIsUnit, GetNumGroupMembers = UnitIsUnit, GetNumGroupMembers
local RegisterStateDriver = RegisterStateDriver
local Secret = issecretvalue
local db, ns, original = nil, nil, nil
local cachedGroup, appliedDriver, pendingSwitch = nil, nil, nil
local announcedMissing = false
local events = CreateFrame("Frame") -- event-only controller; never visually displayed

local function Say(message)
    local chat = DEFAULT_CHAT_FRAME
    if chat and chat.AddMessage then
        chat:AddMessage("|cff57d2bd[공대 파티]|r " .. tostring(message))
    end
end

local function InCombat()
    return InCombatLockdown and InCombatLockdown() or false
end

local function IsSecret(value)
    return Secret and Secret(value) or false
end

local function InNativeRaid()
    if not IsInRaid or not IsInRaid() then return false end
    local kind
    if IsInInstance then
        local _, instanceKind = IsInInstance()
        kind = instanceKind
    end
    return kind ~= "arena"  -- EUI already handles the arena party frames natively.
end

local function OwnRaidSubgroup()
    if not InNativeRaid() or InCombat() then return nil end
    local idx = UnitInRaid and UnitInRaid("player")
    if not IsSecret(idx) and type(idx) == "number" and idx >= 1 and idx <= 40 then
        local _, _, group = GetRaidRosterInfo(idx)
        if not IsSecret(group) and type(group) == "number" and group >= 1 and group <= 8 then
            return group
        end
    end
    local count = GetNumGroupMembers and GetNumGroupMembers()
    if IsSecret(count) or type(count) ~= "number" then return nil end
    for i = 1, math.min(count, 40) do
        if UnitIsUnit and UnitIsUnit("raid" .. i, "player") then
            local _, _, group = GetRaidRosterInfo(i)
            if not IsSecret(group) and type(group) == "number" and group >= 1 and group <= 8 then
                return group
            end
        end
    end
    return nil  -- never accidentally show group 1 when our membership is unknown.
end

local function Active()
    return db and db.enabled ~= false and cachedGroup ~= nil and InNativeRaid()
end

local function InstallBridge()
    if ns then return true end
    local moduleNS = EllesmereUI and EllesmereUI._ModuleNS
    local candidate = moduleNS and moduleNS.EllesmereUIRaidFrames
    if type(candidate) ~= "table"
        or type(candidate._RFVisWanted) ~= "function"
        or type(candidate._PartyInRaid) ~= "function"
        or type(candidate._SmallRaidGroup) ~= "function"
        or type(candidate._RFSyncVisDrivers) ~= "function"
        or type(candidate._UpdatePartyVisibility) ~= "function"
        or type(candidate.UpdateVisibility) ~= "function"
        or not candidate._partyContainerFrame
        or not candidate._partyHeader then
        if not announcedMissing then
            Say("EUI Raid & Party Frames를 찾지 못했습니다. 해당 모듈이 켜져 있는지 확인하세요.")
            announcedMissing = true
        end
        return false
    end
    ns = candidate
    original = {
        wanted = ns._RFVisWanted,
        partyInRaid = ns._PartyInRaid,
        smallGroup = ns._SmallRaidGroup,
        syncDrivers = ns._RFSyncVisDrivers,
    }

    ns._RFVisWanted = function(...)
        if Active() then return true, true end -- retain both genuine EUI frame sets
        return original.wanted(...)
    end
    ns._PartyInRaid = function(...)
        if Active() then return true end
        return original.partyInRaid(...)
    end
    ns._SmallRaidGroup = function(...)
        if Active() then return cachedGroup end
        return original.smallGroup(...)
    end
    ns._RFSyncVisDrivers = function(...)
        -- EUI owns its raid driver. Only the PARTY container's secure driver is
        -- augmented: existing raid/solo/party settings keep their original rules.
        local result = original.syncDrivers(...)
        if InCombat() then return result end
        local native = ns._rfPartyVisMacro
        if type(native) ~= "string" or not ns._partyContainerFrame then return result end
        local wanted = Active() and ("[@raid1,exists] show; " .. native) or native
        if appliedDriver ~= wanted then
            RegisterStateDriver(ns._partyContainerFrame, "visibility", wanted)
            appliedDriver = wanted
        end
        return result
    end

    -- EUI's native portrait watcher originally covers raid1-9 (arena / small
    -- raids). A 40-person raid can place our five members at any raid1-40.
    local tracked = ns._kitPortraitUnits
    if type(tracked) == "table" then
        local present = {}
        for _, token in ipairs(tracked) do present[token] = true end
        for i = 1, 40 do
            local token = "raid" .. i
            if not present[token] then tracked[#tracked + 1] = token end
        end
    end
    announcedMissing = false
    return true
end

local function Refresh()
    if InCombat() then return false end
    cachedGroup = OwnRaidSubgroup()
    if not InstallBridge() then return false end
    -- Both are the EUI's own out-of-combat update functions. They apply the
    -- native party layout, click-casts, saved sizing/position, and raid layout.
    ns.UpdateVisibility()
    ns._UpdatePartyVisibility()
    return true
end

local function MirrorUnitEvent(event, unit)
    -- EUI's raid updater uses raidButton OR partyButton for a token, so in a
    -- raid containing both frame sets, the native PARTY frame needs its second
    -- paint. Only paint the five already-created native EUI party buttons.
    if not Active() or not ns or not unit then return end
    local map = ns._partyUnitToButton
    local button = map and map[unit]
    if not button or not button.IsVisible or not button:IsVisible() then return end
    if (event == "UNIT_HEALTH" or event == "UNIT_MAXHEALTH") and ns._UpdateButtonHealth then
        ns._UpdateButtonHealth(button, unit)
        if event == "UNIT_MAXHEALTH" and ns._ResettleButtonHealth then
            ns._ResettleButtonHealth(button)
        end
        return
    end
    local internals = ns._internals
    if internals and type(internals.UpdateButton) == "function" then
        internals.UpdateButton(button)
    end
end

local function SetEnabled(value)
    if InCombat() then
        pendingSwitch = value and true or false
        Say("전투 중에는 기존 파티 프레임 설정을 바꿀 수 없습니다. 전투 종료 후 적용합니다.")
        return
    end
    db.enabled = value and true or false
    Refresh()
    Say(db.enabled and "켜짐: 공격대에서도 기존 EUI 파티 프레임을 유지합니다."
        or "꺼짐: EUI의 원래 파티/공격대 전환 규칙을 복구했습니다.")
end

local function Status()
    if not ns then
        Say("EUI 원본 파티 프레임 연결 대기 중. EUI Raid & Party Frames가 필요합니다.")
        return
    end
    if not db.enabled then Say("꺼짐 · EUI 기본 동작 사용")
    elseif InNativeRaid() and cachedGroup then
        Say("켜짐 · 내 공격대 소그룹 " .. cachedGroup .. " · EUI 원본 파티 프레임 사용")
    elseif InNativeRaid() then Say("소그룹을 확인하지 못했습니다. 전투 후 재검사합니다.")
    else Say("켜짐 · 공격대 밖에서는 EUI 기본 동작 사용") end
end

local function HandleSlash(text)
    text = (text or ""):lower():match("^%s*(.-)%s*$")
    if text == "on" or text == "켜기" then SetEnabled(true)
    elseif text == "off" or text == "끄기" then SetEnabled(false)
    elseif text == "status" or text == "상태" then Status()
    elseif text == "refresh" or text == "갱신" then
        if InCombat() then Say("전투 종료 후 갱신됩니다.")
        elseif Refresh() then Status() end
    else
        Status()
        Say("/fpr on|off|status|refresh · 파티창 위치/크기는 EUI Raid & Party Frames의 Party 설정에서 변경하세요.")
    end
end

local function OnEvent(_, event, arg1)
    if event == "ADDON_LOADED" and arg1 == addon then
        ForeverPartyInRaidDB = ForeverPartyInRaidDB or {}
        db = ForeverPartyInRaidDB
        if db.enabled == nil then db.enabled = true end
    elseif event == "PLAYER_LOGIN" then
        -- OnEnable in EUI may run on the same PLAYER_LOGIN event; defer once.
        if C_Timer and C_Timer.After then
            C_Timer.After(0, Refresh)
        else
            Refresh()
        end
    elseif event == "PLAYER_REGEN_ENABLED" then
        if pendingSwitch ~= nil then
            db.enabled = pendingSwitch
            pendingSwitch = nil
        end
        Refresh()
    elseif event == "PLAYER_ENTERING_WORLD" or event == "GROUP_ROSTER_UPDATE" then
        if not InCombat() then Refresh() end
    elseif event == "UNIT_HEALTH" or event == "UNIT_MAXHEALTH"
        or event == "UNIT_POWER_UPDATE" or event == "UNIT_DISPLAYPOWER"
        or event == "UNIT_NAME_UPDATE" or event == "UNIT_CONNECTION" then
        MirrorUnitEvent(event, arg1)
    end
end

events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("GROUP_ROSTER_UPDATE")
events:RegisterEvent("PLAYER_REGEN_ENABLED")
events:RegisterEvent("UNIT_HEALTH")
events:RegisterEvent("UNIT_MAXHEALTH")
events:RegisterEvent("UNIT_POWER_UPDATE")
events:RegisterEvent("UNIT_DISPLAYPOWER")
events:RegisterEvent("UNIT_NAME_UPDATE")
events:RegisterEvent("UNIT_CONNECTION")
events:SetScript("OnEvent", OnEvent)

SLASH_FOREVERPARTYINRAID1 = "/fpr"
SLASH_FOREVERPARTYINRAID2 = "/공대파티"
SlashCmdList.FOREVERPARTYINRAID = HandleSlash
