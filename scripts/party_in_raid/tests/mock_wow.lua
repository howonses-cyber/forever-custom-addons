__state = {
    inRaid = true, instanceKind = "pvp", inCombat = false, group = 3, memberIndex = 7,
    protectedWrites = 0, registered = {}, buttonsCreated = 0,
    frames = {}, messages = {}, nativeDrivers = 0, healthMirror = 0, powerMirror = 0,
}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, s) table.insert(__state.messages, s) end }
local frameMeta = {}
frameMeta.__index = frameMeta
function frameMeta:RegisterEvent(event) __state.registered[event] = true end
function frameMeta:SetScript(event, fn) self.events = self.events or {}; self.events[event] = fn end
function frameMeta:SetShown(flag) self.shown = flag end
function frameMeta:IsShown() return self.shown end
function CreateFrame(kind)
    assert(kind == 'Frame', 'No extra native party frames or status bars may be created')
    local f=setmetatable({shown=false}, frameMeta)
    table.insert(__state.frames, f)
    return f
end
function IsInRaid() return __state.inRaid end
function IsInInstance() return true, __state.instanceKind end
function InCombatLockdown() return __state.inCombat end
function UnitInRaid(unit) if unit=='player' and __state.memberIndex and __state.memberIndex>0 then return __state.memberIndex end end
function UnitIsUnit(u, other) return u=='raid'..(__state.memberIndex or 0) and other=='player' end
function GetNumGroupMembers() if __state.inRaid then return 40 else return 3 end end
function GetRaidRosterInfo(index)
    if not __state.inRaid then return nil end
    if index == __state.memberIndex and __state.memberIndex and __state.memberIndex > 0 then
        return 'Player',0,__state.group
    end
    return 'Other'..index,0, (index % 8)+1
end
function issecretvalue() return false end
function RegisterStateDriver(f,key,macro)
    if __state.inCombat then __state.protectedWrites=__state.protectedWrites+1;error('protected modification in combat') end
    assert(key == 'visibility')
    f.driver=macro
    table.insert(__state.frames, f) -- not a new native frame, just a registration trace
    __state.lastMacro=macro
end
local partyContainer=setmetatable({shown=false}, frameMeta)
local partyHeader={ attributes={} }
function partyHeader:GetAttribute(key) return self.attributes[key] end
function partyHeader:SetAttribute(key, val)
    if __state.inCombat then __state.protectedWrites=__state.protectedWrites+1;error('secure write') end
    self.attributes[key]=val
end
local btn={shown=true}
function btn:IsVisible() return self.shown end
local ns={
    _partyContainerFrame=partyContainer,
    _partyHeader=partyHeader,
    _kitPortraitUnits={'player','party1','party2','party3','party4','raid1','raid2','raid3','raid4','raid5','raid6','raid7','raid8','raid9'},
    _partyUnitToButton={raid7=btn},
    _internals={},
}
function ns._RFVisWanted()
    if __state.inRaid and __state.instanceKind == "arena" then return false,true end
    if __state.inRaid then return true,false else return false,true end
end
function ns._PartyInRaid() return __state.inRaid and __state.instanceKind == "arena" end
function ns._SmallRaidGroup() return nil end
function ns._RFSyncVisDrivers()
    local p='[@raid1,exists] hide; [@party1,exists] show; hide'
    if ns._rfPartyVisMacro ~= p then
        RegisterStateDriver(partyContainer,'visibility',p)
        ns._rfPartyVisMacro=p
    end
    __state.nativeDrivers=__state.nativeDrivers+1
end
function ns.UpdateVisibility()
    __state.raidShown = ns._RFVisWanted()
    ns._RFSyncVisDrivers()
end
function ns._UpdatePartyVisibility()
    local _, visible=ns._RFVisWanted()
    __state.partyShown=visible
    ns._RFSyncVisDrivers()
    partyContainer:SetShown(visible)
    if visible and __state.inRaid then
        local group=ns._SmallRaidGroup()
        partyHeader:SetAttribute('groupFilter',group and tostring(group) or '1,2,3,4,5,6,7,8')
    end
end
function ns._UpdateButtonHealth(b,u) assert(u=='raid7' or u=='raid8'); __state.healthMirror=__state.healthMirror+1 end
function ns._ResettleButtonHealth(b) __state.maxHealth= (__state.maxHealth or 0)+1 end
function ns._internals.UpdateButton(b) assert(b==btn); __state.powerMirror=__state.powerMirror+1 end
EllesmereUI={_ModuleNS={EllesmereUIRaidFrames=ns}}
C_Timer={After=function(_,fn) fn() end}
SlashCmdList={}
function __fire(event,arg)
    for i=1,#__state.frames do
        local frame=__state.frames[i]
        if frame.events and frame.events.OnEvent then
            frame.events.OnEvent(frame,event,arg)
        end
    end
end
function __slash(command) SlashCmdList.FOREVERPARTYINRAID(command) end
__ns=ns
