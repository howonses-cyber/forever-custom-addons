__state = {
  inCombat=false, inRaid=true, raidIndex=7,
  groups={1,1,1,1,1,2,3,3,3,3,3,4,4,4,4},
  frames={}, protectedWrites=0, createdSecure=0, driverRegistrations=0,
  updatedHealth={}
}

local frameMethods = {}
local frameMeta = {__index=frameMethods}

function frameMethods:SetSize(w,h) self.width=w;self.height=h end
function frameMethods:SetWidth(w) self.width=w end
function frameMethods:SetHeight(h) self.height=h end
function frameMethods:SetPoint(...) self.point={...} end
function frameMethods:ClearAllPoints() self.point=nil end
function frameMethods:SetMovable(v) self.movable=v end
function frameMethods:SetClampedToScreen(v) self.clamped=v end
function frameMethods:SetScript(evt,fn) self.scripts[evt]=fn end
function frameMethods:RegisterEvent(evt) self.events[evt]=true end
function frameMethods:UnregisterEvent(evt) self.events[evt]=nil end
function frameMethods:EnableMouse(v) self.mouse=v end
function frameMethods:SetFrameLevel(v) self.frameLevel=v end
function frameMethods:RegisterForClicks(v) self.clicks=v end
function frameMethods:GetAttribute(k) return self.attributes[k] end
function frameMethods:CreateTexture()
  local t=setmetatable({scripts={},attributes={},parent=self},frameMeta)
  return t
end
function frameMethods:CreateFontString()
  local t=setmetatable({scripts={},attributes={},parent=self},frameMeta)
  return t
end
function frameMethods:SetColorTexture(...) self.color={...} end
function frameMethods:SetAllPoints(x) self.allPoints=true end
function frameMethods:SetStatusBarTexture(v) self.barTexture=v end
function frameMethods:SetMinMaxValues(a,b) self.min=a;self.max=b end
function frameMethods:SetValue(v) self.value=v end
function frameMethods:SetStatusBarColor(...) self.barColor={...} end
function frameMethods:SetJustifyH(v) self.justify=v end
function frameMethods:SetTextColor(...) self.textColor={...} end
function frameMethods:SetText(v) self.text=v end
function frameMethods:SetScale(v) self.scale=v end
function frameMethods:GetLeft() return self.left or 32 end
function frameMethods:GetTop() return self.top or 550 end
function frameMethods:StartMoving() self.moving=true end
function frameMethods:StopMovingOrSizing() self.moving=false end
function frameMethods:IsShown() return self.shown==true end
function frameMethods:Hide()
  if self.protected and __state.inCombat then error('protected Hide during combat') end
  self.shown=false
end
function frameMethods:Show()
  if self.protected and __state.inCombat then error('protected Show during combat') end
  self.shown=true
  if self.template=='SecureGroupHeaderTemplate' and self.attributes.startingIndex==-4 then
    for i=1,5 do
      if not self[i] then self[i]=CreateFrame('Button',nil,self,'SecureUnitButtonTemplate') end
      self[i].attributes.unit='raid'..(6+i)
    end
  end
end
function frameMethods:SetAttribute(k,v)
  if self.protected and __state.inCombat then
    __state.protectedWrites=__state.protectedWrites+1
    error('protected SetAttribute in combat: '..k)
  end
  self.attributes[k]=v
  if self.template=='SecureGroupHeaderTemplate' and k=='groupFilter' then
    self.filter=v
  end
end

function CreateFrame(kind,name,parent,template)
  local protected=(template=='SecureGroupHeaderTemplate' or template=='SecureUnitButtonTemplate'
    or (parent and parent.protected))
  local f=setmetatable({kind=kind,name=name,parent=parent,template=template,
    scripts={},attributes={},events={},shown=true,protected=protected},frameMeta)
  __state.frames[#__state.frames+1]=f
  if name then _G[name]=f end
  if not __mainEventFrame then __mainEventFrame=f end
  if template=='SecureGroupHeaderTemplate' then __state.createdSecure=__state.createdSecure+1 end
  return f
end

UIParent=CreateFrame('Frame','UIParent',nil,nil)
UIParent.left=0;UIParent.top=800
__mainEventFrame=nil
DEFAULT_CHAT_FRAME={ messages={},AddMessage=function(self,s) self.messages[#self.messages+1]=s end }
SlashCmdList={}
RAID_CLASS_COLORS={SHAMAN={r=0.0,g=0.44,b=0.87}}
CurveConstants={ScaleTo100={}}
function RegisterStateDriver(frame,what,macro)
  if __state.inCombat then error('RegisterStateDriver in combat') end
  frame.stateDriver=macro
  __state.driverRegistrations=__state.driverRegistrations+1
end
function UnregisterStateDriver(frame)
  if __state.inCombat then error('UnregisterStateDriver in combat') end
  frame.stateDriver=nil
end
function InCombatLockdown() return __state.inCombat end
function IsInRaid() return __state.inRaid end
function UnitInRaid(unit) return __state.raidIndex end
function GetNumGroupMembers() return #__state.groups end
function UnitIsUnit(unit,target) return unit=='raid'..__state.raidIndex and target=='player' end
function GetRaidRosterInfo(i) return 'Name'..i,0,__state.groups[i] end
function UnitExists(unit) return true end
function UnitName(unit) return 'Name'..tostring(unit) end
function UnitClass(unit) return 'Shaman','SHAMAN' end
function UnitHealthPercent(unit, actual, curve) return 72 end
function UnitPowerPercent(unit, actual, curve) return 61 end
function UnitHealth(unit) return 72 end
function UnitHealthMax(unit) return 100 end
function UnitPower(unit) return 61 end
function UnitPowerMax(unit) return 100 end
function issecretvalue(v) return false end

function __fire(event)
  assert(__mainEventFrame and __mainEventFrame.scripts.OnEvent,'missing OnEvent')
  __mainEventFrame.scripts.OnEvent(__mainEventFrame,event)
end
function __slash(text)
  SlashCmdList.FOREVERPARTYINRAID(text)
end
