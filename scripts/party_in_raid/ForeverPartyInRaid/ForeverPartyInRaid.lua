-- Forever Party in Raid 1.0.0
-- Independent, read-only visual overlay plus secure unit target buttons.
-- DOES NOT touch the Blizzard PartyMemberFrames or any EllesmereUI frames,
-- their state drivers, saved settings, or click-cast registrations.
-- Raid units, NOT party1..4, are required when the player joins a raid.

local ADDON_NAME = ...
local CreateFrame = CreateFrame
local IsInRaid = IsInRaid
local InCombatLockdown = InCombatLockdown
local GetRaidRosterInfo = GetRaidRosterInfo
local UnitInRaid = UnitInRaid
local UnitExists = UnitExists
local UnitName = UnitName
local UnitClass = UnitClass
local UnitHealth = UnitHealth
local UnitHealthMax = UnitHealthMax
local UnitPower = UnitPower
local UnitPowerMax = UnitPowerMax
local UnitHealthPercent = UnitHealthPercent
local UnitPowerPercent = UnitPowerPercent
local issecretvalue = issecretvalue

local ROW_WIDTH, ROW_HEIGHT, ROW_GAP = 188, 34, 4
local PAD, TITLE_HEIGHT = 8, 25
local WIDTH = ROW_WIDTH + PAD * 2
local HEIGHT = TITLE_HEIGHT + 5 * ROW_HEIGHT + 4 * ROW_GAP + PAD
local VIS_MACRO = "[group:raid]show;hide"
local DEFAULTS = { enabled = true, locked = true, scale = 1, x = 32, y = -235 }
local db, holder, header, dragStrip, titleText
local buttons = {}
local appliedGroup, pendingSecureUpdate, appliedEnabled
local eventFrame = CreateFrame("Frame")

local function Info(msg)
    if DEFAULT_CHAT_FRAME and DEFAULT_CHAT_FRAME.AddMessage then
        DEFAULT_CHAT_FRAME:AddMessage("|cff57d2bd[공대 파티]|r " .. tostring(msg))
    end
end

local function Combat()
    return InCombatLockdown and InCombatLockdown()
end

local function Secret(v)
    return issecretvalue and issecretvalue(v)
end

local function IsRaid()
    return IsInRaid and IsInRaid() and true or false
end

local function MySubgroup()
    -- Only query and compare raid roster information out of combat; some
    -- Forever / 12.1 values can be restricted during combat.
    if not IsRaid() or not GetRaidRosterInfo then return nil end
    local index = UnitInRaid and UnitInRaid("player")
    if not Secret(index) and type(index) == "number" and index >= 1 and index <= 40 then
        local _, _, group = GetRaidRosterInfo(index)
        if not Secret(group) and type(group) == "number" and group >= 1 and group <= 8 then
            return group
        end
    end
    -- Fallback for clients where UnitInRaid is nil during roster transition.
    if GetNumGroupMembers and UnitIsUnit then
        local count = GetNumGroupMembers()
        if type(count) == "number" then
            for i = 1, math.min(count, 40) do
                if UnitIsUnit("raid" .. i, "player") then
                    local _, _, group = GetRaidRosterInfo(i)
                    if not Secret(group) and type(group) == "number" and group >= 1 and group <= 8 then
                        return group
                    end
                end
            end
        end
    end
end

local function SetBarValue(bar, unit, percentFunc, currentFunc, maxFunc)
    -- UnitHealthPercent/UnitPowerPercent with a 0..100 curve is safe for
    -- 12.1 restricted ('secret') values: hand the number straight to SetValue.
    -- Never compare or perform math on a secret result.
    if percentFunc then
        local curve = CurveConstants and CurveConstants.ScaleTo100
        local ok, percent
        if curve then
            ok, percent = pcall(percentFunc, unit, true, curve)
        else
            ok, percent = pcall(percentFunc, unit)
        end
        if ok then
            bar:SetValue(percent)
            return
        end
    end
    -- Older clients: ordinary (not secret) health/power values.
    if not currentFunc or not maxFunc then return end
    local value, maximum = currentFunc(unit), maxFunc(unit)
    if Secret(value) or Secret(maximum) then return end
    if type(maximum) == "number" and maximum > 0 and type(value) == "number" then
        bar:SetValue(100 * value / maximum)
    end
end

local function UpdateButton(button)
    if not button or not button.health then return end
    local unit = button:GetAttribute("unit")
    if not unit or Secret(unit) then return end
    -- The secure header owns unit binding and visibility. Never SetAttribute
    -- on its buttons during roster, unit, or combat events.
    if UnitName then button.nameText:SetText(UnitName(unit)) end
    SetBarValue(button.health, unit, UnitHealthPercent, UnitHealth, UnitHealthMax)
    SetBarValue(button.power, unit, UnitPowerPercent, UnitPower, UnitPowerMax)
    local class
    if UnitClass then
        local _
        _, class = UnitClass(unit)
    end
    if not Secret(class) and type(class) == "string" then
        local c = RAID_CLASS_COLORS and RAID_CLASS_COLORS[class]
        if c then button.health:SetStatusBarColor(c.r, c.g, c.b) end
    end
end

local function UpdateAll()
    if not holder then return end
    for i = 1, 5 do UpdateButton(buttons[i]) end
end

local function CreateBar(button, y, height, color)
    local bg = button:CreateTexture(nil, "BACKGROUND")
    bg:SetColorTexture(0.06, 0.09, 0.13, 0.96)
    bg:SetPoint("TOPLEFT", button, "TOPLEFT", 1, -y)
    bg:SetPoint("TOPRIGHT", button, "TOPRIGHT", -1, -y)
    bg:SetHeight(height)

    local bar = CreateFrame("StatusBar", nil, button)
    bar:SetPoint("TOPLEFT", button, "TOPLEFT", 1, -y)
    bar:SetPoint("TOPRIGHT", button, "TOPRIGHT", -1, -y)
    bar:SetHeight(height)
    bar:SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")
    bar:SetMinMaxValues(0, 100)
    bar:SetValue(100)
    bar:SetStatusBarColor(color[1], color[2], color[3])
    bar:EnableMouse(false)
    return bar
end

local function StyleButton(button)
    if not button or button.health then return end
    button:SetSize(ROW_WIDTH, ROW_HEIGHT)
    button:RegisterForClicks("AnyUp")
    button:SetAttribute("type1", "target")
    button.health = CreateBar(button, 0, 27, { 0.25, 0.68, 0.62 })
    button.power = CreateBar(button, 28, 5, { 0.24, 0.46, 0.86 })
    button.nameText = button:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    button.nameText:SetPoint("TOPLEFT", button, "TOPLEFT", 9, -7)
    button.nameText:SetPoint("RIGHT", button, "RIGHT", -6, 0)
    button.nameText:SetJustifyH("LEFT")
    button.nameText:SetTextColor(1, 1, 1)
    button.nameText:SetText("-")
    local border = button:CreateTexture(nil, "BORDER")
    border:SetAllPoints(button)
    border:SetColorTexture(0.13, 0.17, 0.21, 0.9)
end

local function ApplyPosition()
    holder:ClearAllPoints()
    holder:SetPoint("TOPLEFT", UIParent, "TOPLEFT", db.x, db.y)
end

local function SavePosition()
    if not holder or Combat() then return end
    local left, top = holder:GetLeft(), holder:GetTop()
    local rootLeft, rootTop = UIParent:GetLeft(), UIParent:GetTop()
    if left and top and rootLeft and rootTop then
        db.x, db.y = math.floor(left - rootLeft + 0.5), math.floor(top - rootTop + 0.5)
    end
    ApplyPosition()
end

local function ApplySettings()
    if not holder or Combat() then
        pendingSecureUpdate = true
        return
    end
    holder:SetScale(db.scale)
    dragStrip:EnableMouse(not db.locked)
    if appliedEnabled ~= db.enabled then
        if db.enabled then
            RegisterStateDriver(holder, "visibility", VIS_MACRO)
        else
            if UnregisterStateDriver then UnregisterStateDriver(holder, "visibility") end
            holder:Hide()
        end
        appliedEnabled = db.enabled
    end
end

local function ApplySubgroup()
    if not header or not holder then return end
    if Combat() then
        pendingSecureUpdate = true
        if titleText then titleText:SetText("내 소그룹 · 전투 종료 후 갱신") end
        return
    end
    pendingSecureUpdate = false
    local group = MySubgroup()
    if not group then
        -- Never show arbitrary group 1 while our own roster slot is unknown.
        if header:IsShown() then header:Hide() end
        appliedGroup = nil
        titleText:SetText("내 소그룹 · 대기")
        return
    end
    if group ~= appliedGroup then
        header:SetAttribute("groupFilter", tostring(group))
        appliedGroup = group
    end
    if not header:IsShown() then header:Show() end
    titleText:SetText("내 소그룹 " .. group .. " · 공격대와 함께")
    UpdateAll()
end

local function CreatePanel()
    if holder or Combat() then
        pendingSecureUpdate = true
        return
    end
    holder = CreateFrame("Frame", "ForeverPartyInRaidPanel", UIParent)
    holder:SetSize(WIDTH, HEIGHT)
    holder:SetMovable(true)
    holder:SetClampedToScreen(true)
    ApplyPosition()
    local backdrop = holder:CreateTexture(nil, "BACKGROUND")
    backdrop:SetAllPoints(holder)
    backdrop:SetColorTexture(0.025, 0.035, 0.05, 0.92)

    dragStrip = CreateFrame("Frame", nil, holder)
    dragStrip:SetPoint("TOPLEFT", holder, "TOPLEFT", 0, 0)
    dragStrip:SetPoint("TOPRIGHT", holder, "TOPRIGHT", 0, 0)
    dragStrip:SetHeight(TITLE_HEIGHT)
    dragStrip:SetScript("OnMouseDown", function(_, mouse)
        if mouse == "LeftButton" and not Combat() and not db.locked then
            holder:StartMoving()
        end
    end)
    dragStrip:SetScript("OnMouseUp", function(_, mouse)
        if mouse == "LeftButton" and not Combat() then
            holder:StopMovingOrSizing()
            SavePosition()
        end
    end)
    titleText = dragStrip:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    titleText:SetPoint("CENTER", dragStrip, "CENTER", 0, 0)
    titleText:SetTextColor(0.42, 0.95, 0.84)
    titleText:SetText("내 소그룹 · 대기")

    header = CreateFrame("Frame", "ForeverPartyInRaidSecureHeader", holder, "SecureGroupHeaderTemplate")
    header:SetPoint("TOPLEFT", holder, "TOPLEFT", PAD, -TITLE_HEIGHT)
    header:SetSize(ROW_WIDTH, 5 * ROW_HEIGHT + 4 * ROW_GAP)
    header:SetAttribute("template", "SecureUnitButtonTemplate")
    header:SetAttribute("templateType", "Button")
    header:SetAttribute("initialConfigFunction", string.format("self:SetWidth(%d); self:SetHeight(%d)", ROW_WIDTH, ROW_HEIGHT))
    header:SetAttribute("point", "TOPLEFT")
    header:SetAttribute("xOffset", 0)
    header:SetAttribute("yOffset", -(ROW_HEIGHT + ROW_GAP))
    header:SetAttribute("groupFilter", "1")
    header:SetAttribute("showRaid", true)
    header:SetAttribute("showParty", false)
    header:SetAttribute("showPlayer", true)
    header:SetAttribute("showSolo", false)
    header:SetAttribute("unitsPerColumn", 5)
    header:SetAttribute("maxColumns", 1)
    header:SetAttribute("sortMethod", "INDEX")

    -- Preallocate and style all 5 secure children outside combat. No protected
    -- frame creation or style edits on GROUP_ROSTER_UPDATE in combat.
    holder:Show()
    header:SetAttribute("startingIndex", -4)
    header:Show()
    header:SetAttribute("startingIndex", 1)
    for i = 1, 5 do
        buttons[i] = header[i]
        StyleButton(buttons[i])
    end
    header:Hide()
    ApplySubgroup()
    ApplySettings()
end

local function Initialize()
    if not ForeverPartyInRaidDB then ForeverPartyInRaidDB = {} end
    db = ForeverPartyInRaidDB
    for key, value in pairs(DEFAULTS) do
        if db[key] == nil then db[key] = value end
    end
    if type(db.scale) ~= "number" or db.scale < 0.65 or db.scale > 1.65 then db.scale = 1 end
    if type(db.x) ~= "number" or type(db.y) ~= "number" then db.x, db.y = 32, -235 end
    CreatePanel()
end

local function OnEvent(_, event)
    if event == "PLAYER_LOGIN" then
        Initialize()
    elseif event == "PLAYER_REGEN_ENABLED" then
        if not holder then CreatePanel() end
        if pendingSecureUpdate then
            ApplySettings()
            ApplySubgroup()
        end
    elseif event == "PLAYER_ENTERING_WORLD" or event == "GROUP_ROSTER_UPDATE" or event == "RAID_ROSTER_UPDATE" then
        if holder then
            ApplySubgroup()
            UpdateAll()
        end
    else
        UpdateAll()
    end
end

eventFrame:RegisterEvent("PLAYER_LOGIN")
eventFrame:RegisterEvent("PLAYER_ENTERING_WORLD")
eventFrame:RegisterEvent("GROUP_ROSTER_UPDATE")
eventFrame:RegisterEvent("RAID_ROSTER_UPDATE")
eventFrame:RegisterEvent("PLAYER_REGEN_ENABLED")
eventFrame:RegisterEvent("UNIT_NAME_UPDATE")
eventFrame:RegisterEvent("UNIT_HEALTH")
eventFrame:RegisterEvent("UNIT_MAXHEALTH")
eventFrame:RegisterEvent("UNIT_POWER_UPDATE")
eventFrame:RegisterEvent("UNIT_MAXPOWER")
eventFrame:RegisterEvent("UNIT_CONNECTION")
eventFrame:SetScript("OnEvent", OnEvent)

SLASH_FOREVERPARTYINRAID1 = "/fpr"
SLASH_FOREVERPARTYINRAID2 = "/공대파티"
SlashCmdList.FOREVERPARTYINRAID = function(text)
    if not db then Info("초기화 중입니다.") return end
    local arg = string.lower((text or ""):match("^%s*(.-)%s*$"))
    if arg == "on" or arg == "켜기" then
        db.enabled = true
        ApplySettings()
        Info("공격대 내 소그룹 창 켜기" .. (Combat() and " (전투 종료 후 적용)" or ""))
    elseif arg == "off" or arg == "끄기" then
        db.enabled = false
        ApplySettings()
        Info("소그룹 창 끄기" .. (Combat() and " (전투 종료 후 적용)" or ""))
    elseif arg == "unlock" or arg == "이동" then
        db.locked = false
        ApplySettings()
        Info("이동 잠금 해제: 전투 밖에서 상단 제목을 드래그하세요.")
    elseif arg == "lock" or arg == "잠금" then
        db.locked = true
        ApplySettings()
        Info("위치 잠금" .. (Combat() and " (전투 종료 후 적용)" or ""))
    elseif arg == "reset" or arg == "초기화" then
        if Combat() then Info("위치 초기화는 전투 종료 후 가능합니다.") return end
        db.x, db.y, db.scale = 32, -235, 1
        if holder then ApplyPosition(); ApplySettings() end
        Info("위치/크기만 초기화했습니다. EUI와 다른 애드온 설정은 유지합니다.")
    elseif arg:match("^scale%s+") or arg:match("^크기%s+") then
        local scale = tonumber(arg:match("%s+([%d%.]+)$"))
        if not scale or scale < 0.65 or scale > 1.65 then
            Info("사용법: /fpr scale 1.2  (0.65 ~ 1.65)")
            return
        end
        db.scale = scale
        ApplySettings()
        Info("배율 " .. scale .. (Combat() and " (전투 종료 후 적용)" or ""))
    elseif arg == "status" or arg == "상태" then
        Info("표시 " .. (db.enabled and "켬" or "끔") .. ", 잠금 " .. (db.locked and "켬" or "끔") .. ", 배율 " .. db.scale .. ", 공격대 " .. (IsRaid() and "맞음" or "아님") .. ", 소그룹 " .. tostring(appliedGroup or "확인 대기"))
    else
        Info("명령어: /fpr on|off, /fpr unlock|lock, /fpr scale 1.2, /fpr reset, /fpr status")
        Info("EUI 공격대창은 그대로 유지하고 내 소그룹 5명만 추가 표시합니다. 전투 중 보호 설정 변경은 전투 종료 후 반영합니다.")
    end
end
