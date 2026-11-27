#!/usr/bin/env python3
"""Reproducible, reviewed hotfix on the exact 2.9.2 UI build."""
import argparse, hashlib, json, zipfile
from pathlib import Path
OLD='ForeverQuestGuide_Forever_v2.9.2_UnifiedQuestCards_RewardFix.zip'
NEW='ForeverQuestGuide_Forever_v2.9.3_UnifiedCards_RewardWindow.zip'
SHA='2383f814a1e55ccbda28350209576ceb9e9859c2c3e6395a61b686bac396f8df'
ROOT='ForeverDungeonQuestGuide/'
def sha(b): return hashlib.sha256(b).hexdigest()
def build(base,output):
    assert sha(base.read_bytes())==SHA,'2.9.2 base SHA mismatch'
    with zipfile.ZipFile(base) as z:
        assert z.testzip() is None
        files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    def edit(name,old,new,count=1):
        p=ROOT+name;s=files[p].decode();assert s.count(old)==count,(name,old[:100],s.count(old));files[p]=s.replace(old,new).encode()
    for name,key in [('Core.lua','version'),('UI.lua','uiVersion'),('QuestChains.lua','chainVersion'),('QuestJourney.lua','journeyVersion'),('QuestSections.lua','questSectionsVersion'),('QuestStatus.lua','statusVersion'),('QuestTitleGroups.lua','titleGroupsVersion'),('QuestRewards.lua','rewardsVersion')]:
        edit(name,'G.'+key+'="2.9.2"','G.'+key+'="2.9.3"')
    edit('ForeverDungeonQuestGuide.toc','## Version: 2.9.2','## Version: 2.9.3')
    # Reward data readiness is not proof that an individual reward is present.
    # All live APIs are quest-ID-specific, including for quests outside the log.
    edit('QuestRewards.lua','if inLog or dataAvailable or loaded[id] then','do')
    edit('QuestRewards.lua','if type(name)=="string" and name~="" then\n     result.choices', 'if (type(name)=="string" and name~="") or (tonumber(itemId) or 0)>0 then\n     name=(type(name)=="string" and name~="") and name or nameOf(itemId)\n     result.choices')
    edit('QuestRewards.lua','if type(name)=="string" and name~="" then\n     result.fixed', 'if (type(name)=="string" and name~="") or (tonumber(itemId) or 0)>0 then\n     name=(type(name)=="string" and name~="") and name or nameOf(itemId)\n     result.fixed')
    start=''' -- Keep observed item rewards for completed quests after the log discards'''
    end=''' result.moneyText=moneyText(result.money)'''
    p=ROOT+'QuestRewards.lua';s=files[p].decode();i=s.index(start);j=s.index(end,i)
    s=s[:i]+''' -- Keep only positive game observations, separately from reference facts.
 local live=#result.choices>0 or #result.fixed>0 or (result.money or 0)>0 or (result.xp or 0)>0
 local history=G.db and G.db.questRewardHistory
 if type(history)~="table" and G.db then history={};G.db.questRewardHistory=history end
 if live then
  local previous=observed[id] or (history and history[id]) or {}
  local saved={choices=#result.choices>0 and result.choices or previous.choices or {},fixed=#result.fixed>0 and result.fixed or previous.fixed or {},money=(result.money or 0)>0 and result.money or previous.money,xp=(result.xp or 0)>0 and result.xp or previous.xp}
  observed[id]=saved
  if history then history[id]=saved end
 end
 local old=observed[id] or (history and history[id])
 local known=references[id]
 local function historical(info,source)
  local extra={choices={},fixed={},money=info.money,xp=info.xp,source=source,reference=true,referenceXP=info.xp~=nil}
  for _,key in ipairs({"choices","fixed"})do
   for _,entry in ipairs(info[key] or {}) do
    local itemId=tonumber(entry.id or entry[1]);local name=entry.name or entry[2]
    if itemId then extra[key][#extra[key]+1]={id=itemId,name=nameOf(itemId,name),count=entry.count or 1} end
   end
  end
  extra.moneyText=moneyText(extra.money)
  extra.available=#extra.choices>0 or #extra.fixed>0 or (extra.money or 0)>0 or (extra.xp or 0)>0
  return extra
 end
 local function missing(info)
  if not info then return nil end
  if #result.choices>0 then info.choices={} end
  if #result.fixed>0 then info.fixed={} end
  if (result.money or 0)>0 then info.money=nil;info.moneyText=nil end
  if (result.xp or 0)>0 then info.xp=nil end
  info.available=#info.choices>0 or #info.fixed>0 or (info.money or 0)>0 or (info.xp or 0)>0
  return info.available and info or nil
 end
 if old then result.previous=missing(historical(old,"이 캐릭터의 이전 게임 조회 기록 · 현재 지급 보장 아님")) end
 if known then result.referenceDetail=missing(historical(known,known.source)) end
 if not live then
  local fallback=result.previous or result.referenceDetail
  if fallback then
   result.choices=fallback.choices;result.fixed=fallback.fixed;result.money=fallback.money;result.xp=fallback.xp
   result.source=fallback.source;result.reference=true;result.referenceXP=fallback.referenceXP
   if result.previous then result.previous=nil else result.referenceDetail=nil end
  end
 end
 result.available=live or result.reference==true
''' + s[j:];files[p]=s.encode()
    edit('QuestRewards.lua','if not result.available then\n  if waiting[id] then','if waiting[id] then result.pending=true end\n if not result.available then\n  if waiting[id] then')
    edit('QuestRewards.lua','elseif dataAvailable then result.reason="게임에서 표시할 아이템·골드·경험치 보상을 확인하지 못했습니다."','elseif dataAvailable or loaded[id] then result.reason="퀘스트 자료 로드는 완료되었지만 보상 정보는 제공되지 않았습니다. 보상 없음으로 단정하지 않습니다."')
    edit('QuestRewards.lua','if info and info.pending then return "보상 · 게임 자료 요청 중" end','if info and info.pending and not info.available then return "보상 · 게임 자료 요청 중" end')
    edit('QuestRewards.lua','if info.source then lines[#lines+1]="출처: "..info.source end\n return lines','''if info.source then lines[#lines+1]="출처: "..info.source end
 if info.pending then lines[#lines+1]="|cff9cd9f0게임 자료도 조회 중입니다. 응답 후 갱신됩니다.|r" end
 for _,key in ipairs({"previous","referenceDetail"})do
  local extra=info[key]
  if extra and extra.available then
   lines[#lines+1]=""
   for _,line in ipairs(G.QuestRewardLines(extra))do lines[#lines+1]=line end
  end
 end
 return lines''')
    # Independent, scrollable reward window. The main quest guide stays intact.
    edit('UI.lua','local function buildUI()', '''function widgets.RewardOffset(value)
 local p=widgets.rewardPopup;if not p then return end
 local max=math.max(0,math.ceil(p.child:GetHeight()-p.scroll:GetHeight()))
 value=math.max(0,math.min(max,tonumber(value) or 0))
 p.scroll:SetVerticalScroll(value);setScrollbar(p.bar,value,max,p.scroll:GetHeight())
end
function widgets.RefreshRewardPopup(info,reset)
 local p=widgets.rewardPopup;if not p or not p:IsShown() then return end
 local id=G.selection.quest
 if not id then p:Hide();return end
 if id~=p.questId then reset=true end
 p.questId=id
 p.heading:SetText(G.GetQuestName(id))
 local rows=G.QuestRewardLines and G.QuestRewardLines(info or (G.QuestRewardInfo and G.QuestRewardInfo(id))) or {"보상 자료 확인 필요"}
 local old=reset and 0 or p.scroll:GetVerticalScroll()
 p.body:SetText(table.concat(rows,"\\n"));p.body:SetHeight(0)
 local h=math.max(1,math.ceil((p.body:GetStringHeight() or 0)+16));p.body:SetHeight(h);p.child:SetHeight(h)
 widgets.RewardOffset(old)
end
function widgets.OpenRewardPopup(id)
 if not id then return end
 local p=widgets.rewardPopup
 if not p then
  p=CreateFrame("Frame","ForeverQuestGuideRewardWindow",UIParent);widgets.rewardPopup=p
  p:SetSize(490,425);p:SetPoint("CENTER",UIParent,"CENTER",230,0);p:SetClampedToScreen(true)
  p:SetFrameStrata("FULLSCREEN_DIALOG");p:SetToplevel(true);p:EnableMouse(true);p:SetMovable(true);p:RegisterForDrag("LeftButton")
  p:SetScript("OnDragStart",function(self)if not(InCombatLockdown and InCombatLockdown())then self:StartMoving()end end)
  p:SetScript("OnDragStop",function(self)self:StopMovingOrSizing()end)
  local bg=p:CreateTexture(nil,"BACKGROUND");bg:SetAllPoints();bg:SetColorTexture(.055,.075,.095,1)
  p.border=makeBorder(p,"BORDER");paintBorder(p,p.border,0,2,{.43,.67,.77,1})
  label(p,"퀘스트 보상",16,-10,350,24,"GameFontNormalLarge",C.gold)
  button(p,"닫기",407,-10,68,25,function()p:Hide()end)
  p.heading=label(p,"",16,-44,450,42,"GameFontHighlight",C.cyan);p.heading:SetJustifyV("TOP");p.heading:SetWordWrap(true)
  p.scroll=CreateFrame("ScrollFrame",nil,p);p.scroll:SetPoint("TOPLEFT",p,"TOPLEFT",16,-95);p.scroll:SetSize(441,276)
  p.child=CreateFrame("Frame",nil,p.scroll);p.child:SetSize(441,1);p.scroll:SetScrollChild(p.child)
  p.body=label(p.child,"",0,0,434,1,"GameFontHighlight",C.gray);p.body:SetJustifyV("TOP");p.body:SetWordWrap(true);p.body:SetSpacing(5)
  p.bar=makeScrollbar(p,463,-95,276,widgets.RewardOffset)
  p.scroll:EnableMouseWheel(true);p.scroll:SetScript("OnMouseWheel",function(_,delta)widgets.RewardOffset(p.scroll:GetVerticalScroll()-delta*36)end)
  p.retry=button(p,"보상 다시 조회",16,-385,132,26,function()
   if G.RetryQuestReward then G.RetryQuestReward(G.selection.quest) end
   widgets.RefreshRewardPopup(nil,true)
  end)
  label(p,"게임 정보 우선 · 외부/과거 자료는 별도 표시",157,-385,318,26,"GameFontHighlightSmall",C.dim)
  if G.UIJourneyWidgets then G.UIJourneyWidgets.rewardPopup=p end
 end
 if G.RetryQuestReward then G.RetryQuestReward(id) end
 G.UIFit(p);p:Show();widgets.RefreshRewardPopup(nil,true)
end
local function buildUI()''')
    a=''' widgets.ToggleRewardView=function()''';b=''' widgets.rewardButton=button''';p=ROOT+'UI.lua';s=files[p].decode();i=s.index(a);j=s.index(b,i)
    s=s[:i]+''' widgets.ToggleRewardView=function()
  local id=G.selection.quest
  if not id then G.Print("보상을 확인할 퀘스트 또는 하위 단계를 먼저 선택하세요.");return end
  if GameTooltip then GameTooltip:Hide() end
  widgets.OpenRewardPopup(id)
 end
'''+s[j:];files[p]=s.encode()
    edit('UI.lua','widgets.frame:HookScript("OnHide",function()G.CloseContactPreview();','widgets.frame:HookScript("OnHide",function()if widgets.rewardPopup then widgets.rewardPopup:Hide()end;G.CloseContactPreview();')
    edit('UI.lua','if widgets.rewardButton then\n  widgets.rewardButton:SetText', 'if widgets.rewardPopup and widgets.rewardPopup:IsShown() then widgets.RefreshRewardPopup() end\n if widgets.rewardButton then\n  widgets.rewardButton:SetText')
    # Tests reproduce the old empty-but-ready condition, partial data, and popup.
    edit('tests/test_rewards_v291.lua',"check(not G.QuestRewardInfo(4024).reference,'confirmed game data not overwritten with reference')",'''check(G.QuestRewardInfo(4024).reference,'empty ready flag must not suppress sourced reference')
GetQuestLogRewardMoney=function(id)if id==91 then return 12345 elseif id==4024 then return 123 end end
local partial=G.QuestRewardInfo(4024)
check(partial.money==123 and not partial.reference and partial.referenceDetail and #partial.referenceDetail.choices==3,'partial live currency and distinct reference item choices')
GetQuestLogRewardMoney=function(id)if id==91 then return 12345 end end
G.db={}
local observed=G.QuestRewardInfo(91)
check(G.db.questRewardHistory[91] and #G.db.questRewardHistory[91].choices==2,'positive live rewards stored per character')
''')
    edit('tests/test_rewards_v291.lua',"check(G.QuestRewardInfo(77778).choices[1].id==987,'loaded non-log quest rewards by explicit ID even when HaveQuestRewardData false')",'''check(G.QuestRewardInfo(77778).choices[1].id==987,'loaded non-log quest rewards by explicit ID even when HaveQuestRewardData false')
GetNumQuestLogChoices=function(id)if id==88888 then return 1 end end
GetQuestLogChoiceInfo=function(i,id)if id==88888 then return nil,nil,1,2,true,1234 end end
check(G.QuestRewardInfo(88888).choices[1].id==1234,'quest-ID data used even before readiness, unresolved item name retained')
''')
    edit('tests/test_ui.lua','''  assert(w.detailScroll:IsShown(),"reward view should open expanded details")
  has(w.detailText:GetText(),"테스트 보상 장비")
  has(w.detailText:GetText(),"고정 보상 물품")
  eq(w.rewardButton:GetText(),"보상 닫기")
  w.rewardButton:Click()
  eq(w.rewardButton:GetText(),"보상 보기")
  assert(w.detailText:GetText()~="", "normal guide should return after rewards")''','''  local popup=assert(w.rewardPopup)
  assert(popup:IsShown(),"reward view must open independently")
  has(popup.body:GetText(),"테스트 보상 장비")
  has(popup.body:GetText(),"고정 보상 물품")
  popup:Hide()
  assert(w.overview:IsShown(),"normal guide must remain visible")
  eq(w.rewardButton:GetText(),"보상 보기")''')
    p=ROOT+'tests/test_ui.lua';s=files[p].decode();i=s.index('test("V2.9.2 reward view resets scroll');j=s.index('test("Closing browser also closes contact preview"',i)
    s=s[:i]+'''test("V2.9.3 independent reward window, exact quest, retry, wide view, close",function()
 local w=G.UIJourneyWidgets
 local oldInfo,oldLines,oldBrief=G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief
 G.QuestRewardInfo=function(id)return {id=id,available=true,choices={},fixed={},xp=1}end
 G.QuestRewardLines=function(info)return {"reward-id:"..info.id}end
 G.QuestRewardBrief=function()return "보상"end
 G.SetQuest(90101);w.rewardButton:Click();local p=assert(w.rewardPopup)
 assert(p:IsShown());has(p.heading:GetText(),G.GetQuestName(90101));has(p.body:GetText(),"reward-id:90101")
 p.scroll:SetVerticalScroll(500);G.SetQuest(90102);has(p.body:GetText(),"reward-id:90102");eq(p.scroll:GetVerticalScroll(),0)
 p.retry:Click();has(p.body:GetText(),"reward-id:90102")
 p:Hide();w.focusButton:Click();assert(w.wideRewardButton:IsShown())
 w.wideRewardButton:Click();assert(p:IsShown());assert(not w.frame.right:IsShown(),"reward popup must preserve wide mode")
 has(p.body:GetText(),"reward-id:90102");G.ShowUI(false);assert(not p:IsShown());G.ShowUI(true);w.focusButton:Click()
 G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief=oldInfo,oldLines,oldBrief;G.UIRefresh();checkPreserved()
end)
'''+s[j:];files[p]=s.encode()
    files[ROOT+'Docs/CHANGELOG_v2.9.3.txt']=('2.9.3: Unified V2.9.2 cards retained. Dedicated quest reward window, explicit retry, correct fallback for empty ready responses, separately labeled historical/reference rewards, per-character observed game reward history. Actual server and Windows rendering remain to be tested.').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,11,28,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.create_system=3;info.external_attr=0o100644<<16;z.writestr(info,data)
    with zipfile.ZipFile(output) as z: assert z.testzip() is None and set(z.namelist())==set(files)
    h=sha(output.read_bytes());print(json.dumps(dict(file=output.name,sha256=h,entries=len(files),size=output.stat().st_size)));return h
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--base',type=Path);p.add_argument('--output',type=Path);p.add_argument('--expected-sha');a=p.parse_args();h=build(a.base or a.root/'addons'/OLD,a.output or a.root/'addons'/NEW);assert not a.expected_sha or h==a.expected_sha
