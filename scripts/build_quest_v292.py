#!/usr/bin/env python3
"""Rebuild the reviewed V2.9.2 from the pinned V2.9.1 ZIP; no other addons touched."""
import argparse, hashlib, json, zipfile
from pathlib import Path
OLD='ForeverQuestGuide_Forever_v2.9.1_NestedFlame_Rewards.zip'
NEW='ForeverQuestGuide_Forever_v2.9.2_UnifiedQuestCards_RewardFix.zip'
SHA='31d2cd5ddeefc7262260b7738a0c2cd393f07199c2ed6ecfba5dabba0d42f6b4'
ROOT='ForeverDungeonQuestGuide/'
def sha(data): return hashlib.sha256(data).hexdigest()
def build(base,output):
    assert sha(base.read_bytes())==SHA,'Pinned base mismatch'
    with zipfile.ZipFile(base) as z:
        assert z.testzip() is None
        files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    def edit(name, old, new, count=1):
        path=ROOT+name; s=files[path].decode('utf-8'); assert s.count(old)==count,(name,old[:100],s.count(old));files[path]=s.replace(old,new).encode('utf-8')
    for name,key in [('Core.lua','version'),('UI.lua','uiVersion'),('QuestChains.lua','chainVersion'),('QuestJourney.lua','journeyVersion'),('QuestSections.lua','questSectionsVersion'),('QuestStatus.lua','statusVersion'),('QuestTitleGroups.lua','titleGroupsVersion'),('QuestRewards.lua','rewardsVersion')]:
        edit(name,'G.'+key+'="2.9.1"','G.'+key+'="2.9.2"')
    edit('ForeverDungeonQuestGuide.toc','## Version: 2.9.1','## Version: 2.9.2')
    # The outer story border remains blue. The nested chapter owns one neutral
    # border across its visible rows, including scroll continuation; no child cards.
    edit('UI.lua','local function refreshChainFrames(display,offset)', '''function widgets.ChapterKey(entry)
 if not entry then return nil end
 if entry.kind=="subchapter" then return entry.key end
 return entry.kind=="quest" and entry.subchapterKey or nil
end
function widgets.RefreshChapterFrames(display,offset)
 for _,group in ipairs(widgets.chapterFrames) do group:Hide();group.chapterKey=nil end
 local i,used=1,0
 while i<=QUEST_ROW_COUNT do
  local key=widgets.ChapterKey(display[offset+i])
  if not key then i=i+1 else
   local first,last=i,i
   while last<QUEST_ROW_COUNT and widgets.ChapterKey(display[offset+last+1])==key do last=last+1 end
   used=used+1;local group=widgets.chapterFrames[used]
   group.chapterKey=key;group.firstRow=first;group.lastRow=last
   group:ClearAllPoints();group:SetPoint("TOPLEFT",widgets.frame.mid,"TOPLEFT",20,-QUEST_ROW_TOP-(first-1)*QUEST_ROW_STRIDE)
   group:SetSize(widgets.frame.mid:GetWidth()-67,(last-first)*QUEST_ROW_STRIDE+QUEST_ROW_HEIGHT)
   paintBorder(group,group.border,0,2,{.4032,.4347,.4662,1})
   if widgets.ChapterKey(display[offset+first-1])==key then group.border.top:Hide() end
   if widgets.ChapterKey(display[offset+last+1])==key then group.border.bottom:Hide() end
   group:Show();i=last+1
  end
 end
end
local function refreshChainFrames(display,offset)''')
    edit('UI.lua','local cardInset=entry.subchapterKey and 26 or entry.chainKey and 12 or entry.singleSectionKey and 8 or 0\n local inset=cardInset+35','local cardInset=entry.chainKey and 12 or entry.singleSectionKey and 8 or 0\n local inset=cardInset+35+(entry.subchapterKey and 12 or 0)')
    edit('UI.lua','r.checkbox:SetPoint("LEFT",r,"LEFT",cardInset+5,0)','r.checkbox:SetPoint("LEFT",r,"LEFT",cardInset+5+(entry.subchapterKey and 12 or 0),0)')
    edit('UI.lua','paintBorder(r,r.cardBorder,cardInset,2,selected and {1,.80,.34,1} or {color[1]*.63,color[2]*.63,color[3]*.63,1})','''if entry.subchapterKey then
  -- A step is part of its parent card. A continuous dark inset and a thin
  -- timeline replace the repeated full-width card, even while scrolling.
  r.fill:ClearAllPoints();r.fill:SetPoint("TOPLEFT",r,"TOPLEFT",cardInset,entry._chapterContinuesBefore and (QUEST_ROW_STRIDE-QUEST_ROW_HEIGHT) or 0)
  r.fill:SetPoint("BOTTOMRIGHT",r,"BOTTOMRIGHT",-cardInset,0)
  r.fill:SetColorTexture(.065,.10,.14,.99)
  r.statusStripe:Hide()
  r.rail:ClearAllPoints();r.rail:SetPoint("TOPLEFT",r,"TOPLEFT",cardInset+8,entry._chapterContinuesBefore and (QUEST_ROW_STRIDE-QUEST_ROW_HEIGHT) or 0)
  r.rail:SetPoint("BOTTOMLEFT",r,"BOTTOMLEFT",cardInset+8,entry._chapterContinuesAfter and -(QUEST_ROW_STRIDE-QUEST_ROW_HEIGHT) or 6)
  r.rail:SetWidth(2);r.rail:SetColorTexture(.30,.45,.55,1);r.rail:Show()
  r.stepDot:ClearAllPoints();r.stepDot:SetPoint("LEFT",r,"LEFT",cardInset+5,0);r.stepDot:SetSize(8,8)
  r.stepDot:SetColorTexture(unpack(entry.subchapterSkipped and {.43,.46,.49,1} or {color[1],color[2],color[3],1}));r.stepDot:Show()
  if selected then
   -- Selected step gets a small gold underline, not another independent card.
   r.edge:ClearAllPoints();r.edge:SetPoint("BOTTOMLEFT",r,"BOTTOMLEFT",inset,2);r.edge:SetPoint("BOTTOMRIGHT",r,"BOTTOMRIGHT",-cardInset-5,2);r.edge:SetHeight(1);r.edge:SetColorTexture(1,.80,.34,1);r.edge:Show()
  end
 else
  paintBorder(r,r.cardBorder,cardInset,2,selected and {1,.80,.34,1} or {color[1]*.63,color[2]*.63,color[3]*.63,1})
 end''')
    # Restore edge positioning when virtual rows are reused, and use one
    # separately pooled overlay per contiguous chapter, not per child.
    edit('UI.lua','widgets.questRows={};bindWheel(mid,scrollQuest)','widgets.questRows={};widgets.chapterFrames={};bindWheel(mid,scrollQuest)')
    edit('UI.lua','bindWheel(r,scrollQuest);bindWheel(r.checkbox,scrollQuest);widgets.questRows[i]=r','r.stepDot=r:CreateTexture(nil,"OVERLAY");r.stepDot:Hide()\n  bindWheel(r,scrollQuest);bindWheel(r.checkbox,scrollQuest);widgets.questRows[i]=r')
    edit('UI.lua','group.border=makeBorder(group,"ARTWORK");group:Hide();widgets.chainFrames[i]=group','''group.border=makeBorder(group,"ARTWORK");group:Hide();widgets.chainFrames[i]=group
  local chapter=CreateFrame("Frame",nil,mid);chapter:EnableMouse(false);chapter:SetFrameLevel(widgets.questRows[1]:GetFrameLevel()+1)
  chapter.border=makeBorder(chapter,"ARTWORK");chapter:Hide();widgets.chapterFrames[i]=chapter''')
    edit('UI.lua','r.subchapterCollapsed=nil;r.rail:Hide();r.edge:Hide()','''r.subchapterCollapsed=nil;r.rail:Hide();r.edge:Hide();r.stepDot:Hide()
  r.edge:ClearAllPoints();r.edge:SetPoint("BOTTOMLEFT",r,"BOTTOMLEFT",9,0);r.edge:SetPoint("BOTTOMRIGHT",r,"BOTTOMRIGHT",-1,0);r.edge:SetHeight(2);r.edge:SetColorTexture(.28,.53,.67,.95)''')
    old='''   r:Show();r.statusText:Show();r.marker:Show()
   r.text:SetPoint("TOPLEFT",r,"TOPLEFT",24,-3);r.text:SetPoint("TOPRIGHT",r,"TOPRIGHT",-8,-3);r.text:SetHeight(18)
   r.statusText:SetPoint("BOTTOMLEFT",r,"BOTTOMLEFT",24,3);r.statusText:SetPoint("BOTTOMRIGHT",r,"BOTTOMRIGHT",-8,3);r.statusText:SetHeight(13)
   r.fill:SetColorTexture(.11,.19,.24,.99);r.marker:SetColorTexture(.42,.80,.88,1)
   r.text:SetText("|cffb4e8f7"..(entry.collapsed and "▶ " or "▼ ")..entry.label.." · 하위 단계|r")
   r.statusText:SetText("|cffa7c9da"..entry.stepsDone.."/"..entry.steps.."단계 완료"..(entry.hasAlternatives and " · 1단계는 택일" or "").." · 클릭: "..(entry.collapsed and "펼치기" or "접기").."|r")'''
    new='''   local inset=12;local color={.64,.69,.74};local complete=entry.stepsDone==entry.steps
   r.cardInset=inset;r:Show();r.marker:Hide();r.statusBadge:Show();r.badgeFill:Show();r.progressText:Show();r.statusStripe:Show()
   r.fill:ClearAllPoints();r.fill:SetPoint("TOPLEFT",r,"TOPLEFT",inset,0);r.fill:SetPoint("BOTTOMRIGHT",r,"BOTTOMRIGHT",-inset,0)
   r.fill:SetColorTexture(.075+color[1]*.075,.09+color[2]*.075,.11+color[3]*.075,.98)
   r.text:SetPoint("TOPLEFT",r,"TOPLEFT",inset+35,-3);r.text:SetPoint("TOPRIGHT",r,"TOPRIGHT",-inset-87,-3);r.text:SetHeight(16);r.text:SetTextColor(.93,.94,.96)
   r.text:SetText(shortLine((entry.collapsed and "▶ " or "▼ ")..entry.label,r:GetWidth()-2*inset-131))
   r.statusStripe:ClearAllPoints();r.statusStripe:SetPoint("TOPLEFT",r,"TOPLEFT",inset+3,-2);r.statusStripe:SetPoint("BOTTOMLEFT",r,"BOTTOMLEFT",inset+3,2);r.statusStripe:SetWidth(3);r.statusStripe:SetColorTexture(unpack(color))
   r.badgeFill:ClearAllPoints();r.badgeFill:SetPoint("TOPRIGHT",r,"TOPRIGHT",-inset-6,-3);r.badgeFill:SetSize(74,16);r.badgeFill:SetColorTexture(color[1]*.30,color[2]*.30,color[3]*.30,1)
   r.statusBadge:ClearAllPoints();r.statusBadge:SetPoint("TOPRIGHT",r,"TOPRIGHT",-inset-6,-3);r.statusBadge:SetSize(74,16);r.statusBadge:SetText(entry.stepsDone.."/"..entry.steps..(complete and " 완료" or " 단계"));r.statusBadge:SetTextColor(unpack(color))
   r.progressText:ClearAllPoints();r.progressText:SetPoint("TOPLEFT",r,"TOPLEFT",inset+35,-19);r.progressText:SetPoint("TOPRIGHT",r,"TOPRIGHT",-inset-7,-19);r.progressText:SetHeight(12)
   r.progressText:SetText((entry.collapsed and "하위 단계 펼치기" or "하위 단계 접기")..(entry.hasAlternatives and " · 첫 단계는 택일" or ""))
   r.progressText:SetTextColor(.68,.76,.82)'''
    edit('UI.lua',old,new)
    edit('UI.lua','entry._viewportContinuation=chainKey(entry) and chainKey(display[questOffset+i-1])==chainKey(entry) and i==1','''entry._viewportContinuation=chainKey(entry) and chainKey(display[questOffset+i-1])==chainKey(entry) and i==1
   entry._chapterContinuesBefore=entry.subchapterKey and widgets.ChapterKey(display[questOffset+i-1])==entry.subchapterKey and i>1
   entry._chapterContinuesAfter=entry.subchapterKey and widgets.ChapterKey(display[questOffset+i+1])==entry.subchapterKey and i<QUEST_ROW_COUNT''')
    edit('UI.lua','refreshChainFrames(display,questOffset)','refreshChainFrames(display,questOffset);widgets.RefreshChapterFrames(display,questOffset)')
    edit('UI.lua','G.UIJourneyWidgets.rewardButton=widgets.rewardButton','G.UIJourneyWidgets.rewardButton=widgets.rewardButton;G.UIJourneyWidgets.wideRewardButton=widgets.wideRewardButton;G.UIJourneyWidgets.chapterFrames=widgets.chapterFrames')
    # Recycled progress and text color must not leak between rows.
    edit('UI.lua','r.text:ClearAllPoints();r.statusText:ClearAllPoints()','r.text:ClearAllPoints();r.statusText:ClearAllPoints();r.progressText:SetTextColor(.84,.88,.93)')
    edit('UI.lua','local function detailText(text,q)','function widgets.ResetRewardScroll() lastDetailText=nil;setDetailOffset(0) end\nlocal function detailText(text,q)')
    # Reward view: never remain at a previous long guide scroll offset. Wide
    # mode exposes the same action. Closing restores previous summary/detail.
    edit('UI.lua',''' widgets.rewardButton=button(right,"보상 보기",212,-9,94,23,function()
  local id=G.selection.quest
  if not id then return end
  if widgets.rewardFocusQuest==id then widgets.rewardFocusQuest=nil
  else widgets.rewardFocusQuest=id end
  detailsExpanded=true;G.UIRefresh()
 end)''',''' widgets.ToggleRewardView=function()
  local id=G.selection.quest
  if not id then G.Print("보상을 확인할 퀘스트 또는 하위 단계를 먼저 선택하세요.");return end
  if widgets.rewardFocusQuest==id and not G.db.questListWide then
   widgets.rewardFocusQuest=nil;detailsExpanded=widgets.rewardReturnExpanded==true
  else
   if not widgets.rewardFocusQuest then widgets.rewardReturnExpanded=detailsExpanded end
   widgets.rewardFocusQuest=id;detailsExpanded=true
   if G.db.questListWide then G.db.questListWide=false;widgets.ApplyListLayout() end
   if G.RetryQuestReward then G.RetryQuestReward(id) end
  end
  lastDetailText=nil;setDetailOffset(0)
  if detailsExpanded then widgets.overview:Hide();detailScroll:Show() end
  G.UIRefresh();setDetailOffset(0)
 end
 widgets.rewardButton=button(right,"보상 보기",212,-9,94,23,widgets.ToggleRewardView)
 widgets.wideRewardButton=button(mid,"보상 보기",198,-103,100,24,widgets.ToggleRewardView);widgets.wideRewardButton:Hide()''')
    edit('UI.lua','widgets.headerInfo:SetWidth(wide and mid:GetWidth()-158 or 288)','''widgets.headerInfo:SetWidth(wide and mid:GetWidth()-268 or 288)
  widgets.wideRewardButton:ClearAllPoints();widgets.wideRewardButton:SetPoint("TOPLEFT",mid,"TOPLEFT",mid:GetWidth()-232,-103);widgets.wideRewardButton:SetShown(wide)''')
    edit('UI.lua','local q=G.selection.quest\n G.ContactPreviewSelectionChanged(q)','''local q=G.selection.quest
 if widgets.rewardFocusQuest and widgets.rewardFocusQuest~=q then
  if q then widgets.rewardFocusQuest=q;widgets.ResetRewardScroll()
  else widgets.rewardFocusQuest=nil;detailsExpanded=widgets.rewardReturnExpanded==true end
 end
 G.ContactPreviewSelectionChanged(q)''')
    edit('UI.lua','if G.selection.quest then widgets.rewardButton:Enable() else widgets.rewardButton:Disable() end','''if G.selection.quest then widgets.rewardButton:Enable();widgets.wideRewardButton:Enable() else widgets.rewardButton:Disable();widgets.wideRewardButton:Disable() end''')
    edit('UI.lua','widgets.detailHint:SetText("상세 설명 · 마우스 휠로 스크롤 · [요약 보기]로 돌아가기")','widgets.detailHint:SetText(widgets.rewardFocusQuest and "보상 정보 · 마우스 휠로 스크롤 · [보상 닫기]로 복귀" or "상세 설명 · 마우스 휠로 스크롤 · [요약 보기]로 돌아가기")')
    # Make late-data requests visible, bounded and repeatable. A successful
    # quest data event is not proof reward data exists; query ID explicitly and
    # never claim an empty result is confirmed zero rewards without readiness.
    edit('QuestRewards.lua','local waiting={}\nlocal rewardLoader','local waiting,attempted,loaded,observed={},{},{},{}\nlocal rewardLoader')
    edit('QuestRewards.lua',''' if not (C_QuestLog and type(C_QuestLog.RequestLoadQuestByID)=="function") or waiting[id] then return end
 waiting[id]=true
 local ok=pcall(C_QuestLog.RequestLoadQuestByID,id)
 if not ok then waiting[id]=nil end''',''' if not (C_QuestLog and type(C_QuestLog.RequestLoadQuestByID)=="function") or waiting[id] or attempted[id] then return end
 local token={};waiting[id]=token;attempted[id]=true
 local ok=pcall(C_QuestLog.RequestLoadQuestByID,id)
 if not ok then waiting[id]=nil end
 -- A missing server event must not leave a permanent loading spinner.
 if ok and waiting[id]==token and C_Timer and type(C_Timer.After)=="function" then
  C_Timer.After(8,function()
   if waiting[id]==token then waiting[id]=nil;if G.selection and G.selection.quest==id and G.UIRefresh then G.UIRefresh() end end
  end)
 end''')
    edit('QuestRewards.lua','local references={','''function G.RetryQuestReward(id)
 id=tonumber(id);if id and not waiting[id] then attempted[id]=nil;loaded[id]=nil end
end
local references={''')
    edit('QuestRewards.lua','if inLog or dataAvailable then','if inLog or dataAvailable or loaded[id] then')
    edit('QuestRewards.lua','if not inLog and not dataAvailable then requestReward(id) end','if not dataAvailable and not loaded[id] then requestReward(id) end')
    edit('QuestRewards.lua',''' local known=references[id]
 if known and #result.choices==0 and #result.fixed==0 then''',''' -- Keep observed item rewards for completed quests after the log discards
 -- them. Do not cache player-dependent XP/money as current values.
 if #result.choices>0 or #result.fixed>0 then
  observed[id]={choices=result.choices,fixed=result.fixed}
 elseif observed[id] then
  result.choices=observed[id].choices;result.fixed=observed[id].fixed
  result.source="이번 접속 중 확인한 게임 보상 기록";result.reference=true
 end
 local known=references[id]
 if known and #result.choices==0 and #result.fixed==0 then''')
    edit('QuestRewards.lua','result.money=result.money or known.money','if not result.money or result.money<=0 then result.money=known.money end')
    edit('QuestRewards.lua','if not result.available then result.reason="보상 자료 미확인 · 실제 퀘스트 수락/보고 화면에서 확인" end','''if not result.available then
  if waiting[id] then result.pending=true;result.reason="게임 서버에서 보상 자료 요청 중 · 응답 후 자동 갱신"
  elseif dataAvailable then result.reason="게임에서 표시할 아이템·골드·경험치 보상을 확인하지 못했습니다."
  else result.reason="보상 자료 미확인 · 보상 닫기 후 다시 열거나 실제 수락/보고 화면에서 확인" end
 end''')
    edit('QuestRewards.lua','''   waiting[id]=nil
   if success and G.selection and G.selection.quest==id and G.UIRefresh then G.UIRefresh() end''','''   waiting[id]=nil;loaded[id]=success==true or nil
   if G.selection and G.selection.quest==id and G.UIRefresh then G.UIRefresh() end''')
    edit('QuestRewards.lua','if not info or not info.available then return "보상 · 자료 확인 필요" end','if info and info.pending then return "보상 · 게임 자료 요청 중" end\n if not info or not info.available then return "보상 · 자료 확인 필요" end')
    edit('QuestRewards.lua','if not info or not info.available then return {"보상 자료 확인 필요",(info and info.reason) or "게임에서 보상을 확인하세요."} end','if not info or not info.available then return {info and info.pending and "보상 자료 요청 중" or "보상 자료 확인 필요",(info and info.reason) or "게임에서 보상을 확인하세요."} end')
    # Correct tests for bounded attempts and the pending state instead of an
    # infinite re-request loop on a successful data-load without rewards.
    edit('tests/test_rewards_v291.lua',"absent.reason:find('확인',1,true)~=nil","absent.pending and absent.reason:find('요청',1,true)~=nil")
    edit('tests/test_rewards_v291.lua',"check(requested[77777]==2,'successful load invalidates pending request')\nG.selection.quest=77777\nframe.OnEvent(frame,'QUEST_DATA_LOAD_RESULT',77777,true)\ncheck(G.uiRefreshes==1,'relevant selected quest can refresh on data availability')",'''check(requested[77777]==1,'successful quest load without rewards must not request forever')
G.selection.quest=77778
G.QuestRewardInfo(77778)
frame.OnEvent(frame,'QUEST_DATA_LOAD_RESULT',77778,false)
check(G.uiRefreshes==1,'failed relevant request clears loading and redraws')
G.RetryQuestReward(77778);G.QuestRewardInfo(77778)
check(requested[77778]==2,'explicit retry permitted after failure')
frame.OnEvent(frame,'QUEST_DATA_LOAD_RESULT',77778,true)
check(G.uiRefreshes==2,'successful relevant request refreshes')
GetNumQuestLogChoices=function(id)if id==77778 then return 1 end end
GetQuestLogChoiceInfo=function(i,id)if id==77778 then return 'loaded reward','tex',1,4,true,987 end end
check(G.QuestRewardInfo(77778).choices[1].id==987,'loaded non-log quest rewards by explicit ID even when HaveQuestRewardData false')
''')
    # The old test suite loads UI in isolation without title grouping. Add a
    # dedicated actual-renderer regression in that same fixture after old tests.
    edit('tests/test_ui.lua','test("Closing browser also closes contact preview",function()', '''test("V2.9.2 same-style chapter card and borderless child timeline",function()
 local w=G.UIJourneyWidgets
 loadAddon("QuestTitleGroups.lua")
 G.db.groupChains=true;G.db.questListCompact=true;G.db.questListWide=false
 G.selection.mode="dungeon";dungeon.ids={3801,3802,90101};w.statusButtons.all:Click();w.search:SetText("");G.UIRefresh()
 local chapter=assert(Mock.find(function(o)return o.subchapterKey and o:IsVisible() end),"missing chapter header")
 local key=chapter.subchapterKey;G.db.chainCollapsed[key]=false;G.UIRefresh()
 local first=assert(rowFor(3801));local second=assert(rowFor(3802));local normal=assert(rowFor(90101))
 assert(first.stepDot:IsShown() and second.rail:IsShown(),"child timeline missing")
 for _,edge in pairs(first.cardBorder)do assert(not edge:IsShown(),"child must not be a separate card")end
 local group=assert(Mock.find(function(o)return o.chapterKey==key and o.border and o:IsVisible()end),"chapter outer border missing")
 assert(group.lastRow-group.firstRow>=2,"parent border must include both children")
 assert(normal.cardBorder.top:IsShown() and not normal.stepDot:IsShown(),"standalone card affected by nested rendering")
 chapter:Click();assert(not rowFor(3801) and not rowFor(3802),"collapse failed")
 assert(chapter.subchapterCollapsed);eq(chapter.cardInset,12)
 chapter:Click();assert(rowFor(3801) and rowFor(3802),"expand failed")
 G.QuestTitleNestedRows=nil;G.db.chainCollapsed[key]=nil;dungeon.ids=fixtureIds;G.UIRefresh();checkPreserved()
end)
test("V2.9.2 reward view resets scroll, switches quest and is accessible in wide view",function()
 local w=G.UIJourneyWidgets
 local oldInfo,oldLines,oldBrief=G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief
 G.QuestRewardInfo=function(id)return {id=id,available=true,choices={},fixed={},xp=1}end
 G.QuestRewardLines=function(info)return {"reward-id:"..info.id}end
 G.QuestRewardBrief=function()return "보상"end
 G.SetQuest(90101);w.detailScroll:SetVerticalScroll(500);w.rewardButton:Click()
 eq(w.detailScroll:GetVerticalScroll(),0);has(w.detailText:GetText(),"reward-id:90101")
 G.SetQuest(90102);has(w.detailText:GetText(),"reward-id:90102");eq(w.rewardButton:GetText(),"보상 닫기")
 w.rewardButton:Click();w.focusButton:Click();assert(w.wideRewardButton:IsShown(),"reward button missing in wide list")
 w.wideRewardButton:Click();assert(w.frame.right:IsShown() and w.detailScroll:IsShown());eq(w.detailScroll:GetVerticalScroll(),0)
 has(w.detailText:GetText(),"reward-id:90102");w.rewardButton:Click()
 G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief=oldInfo,oldLines,oldBrief;G.UIRefresh();checkPreserved()
end)
test("Closing browser also closes contact preview",function()''')
    files[ROOT+'Docs/CHANGELOG_v2.9.2.txt']=('Forever Quest Guide 2.9.2\nUnified neutral parent cards and continuous borderless step timeline.\nReward view resets scroll, follows selected quest and is accessible in wide-list mode.\nBounded explicit-ID requests; delayed completion/error; session-observed item reward fallback.\nUnknown data remains unknown; no quest state or route changes.\n').encode()
    # Reference rewards for the specific quest chain reported by the player.
    edit('QuestRewards.lua','local references={','''local function ref(id,xp,money,choices,fixed,wowhead)
 return {xp=xp,money=money,choices=choices,fixed=fixed,source=(wowhead and "Wowhead Forever" or "ForeverQuestLog").." · 퀘스트 "..id.." · 기준 자료 (실제 지급은 게임 확인)"}
end
local references={
 [3441]=ref(3441,440),
 [3442]=ref(3442,4400,14000),
 [3443]=ref(3443,4400,14000),
 [3452]=ref(3452,4700,7500),
 [3453]=ref(3453,470,nil,nil,nil,true),
 [3454]=ref(3454,4700,nil,nil,{{10515,"Torch of Retribution"}}),
 [3462]=ref(3462,470),
 [3463]=ref(3463,7600,23000,{{10742,"Dragonflight Leggings"},{10743,"Drakefire Headguard"},{10744,"Axe of the Ebon Drake"},{270114,"Dragonscale Pants"}},nil,true),
 [3481]=ref(3481,470,nil,nil,{{10569,"Hoard of the Black Dragonflight"}}),
 [4022]=ref(4022,5450),
 [4023]=ref(4023,5450),''')
    edit('QuestRewards.lua','money=26500,','money=26500,xp=6200,')
    edit('QuestRewards.lua','if known and #result.choices==0 and #result.fixed==0 then','if known and not dataAvailable and not inLog and #result.choices==0 and #result.fixed==0 and not ((result.money or 0)>0 or (result.xp or 0)>0) then')
    edit('QuestRewards.lua','  if not result.money or result.money<=0 then result.money=known.money end','''  for _,item in ipairs(known.fixed or {}) do
   result.fixed[#result.fixed+1]={id=item[1],name=nameOf(item[1],item[2]),count=1}
  end
  result.money=known.money;result.xp=known.xp;result.referenceXP=known.xp~=nil''')
    edit('QuestRewards.lua','lines[#lines+1]="경험치: "..math.floor(info.xp)','lines[#lines+1]=(info.referenceXP and "기준 경험치(자료): " or "경험치: ")..math.floor(info.xp)')
    edit('QuestRewards.lua','out[#out+1]=math.floor(info.xp).." 경험치"','out[#out+1]=math.floor(info.xp)..(info.referenceXP and " 기준 경험치" or " 경험치")')
    edit('QuestRewards.lua','   if G.selection and G.selection.quest==id and G.UIRefresh then G.UIRefresh() end\n  end\n end)','''   local function refresh() if G.selection and G.selection.quest==id and G.UIRefresh then G.UIRefresh() end end
   if C_Timer and type(C_Timer.After)=="function" then C_Timer.After(0,refresh) else refresh() end
  end
 end)''')
    edit('tests/test_rewards_v291.lua',"flame.money==26500 and not flame.xp,'reference money is sourced and XP not invented'","flame.money==26500 and flame.xp==6200 and flame.referenceXP,'reference base XP and money labeled'")
    edit('tests/test_rewards_v291.lua',"local absent=G.QuestRewardInfo(77777)",'''local chain={3441,3442,3443,3452,3453,3454,3462,3463,3481,4022,4023,4024}
for _,id in ipairs(chain)do local r=G.QuestRewardInfo(id);check(r.available and r.reference and r.xp>0,'chain reward reference '..id) end
check(#G.QuestRewardInfo(3463).choices==4,'four source-listed choice rewards including Forever item')
check(G.QuestRewardInfo(3454).fixed[1].id==10515 and G.QuestRewardInfo(3481).fixed[1].id==10569,'chain fixed reward ids')
check(table.concat(G.QuestRewardLines(flame),'\\n'):find('기준 경험치(자료)',1,true),'reference XP is not promised live XP')
HaveQuestRewardData=function(id)return id==91 or id==4024 end
check(not G.QuestRewardInfo(4024).reference,'confirmed game data not overwritten with reference')
HaveQuestRewardData=function(id)return id==91 end
local absent=G.QuestRewardInfo(77777)''')
    files[ROOT+'Docs/RewardReferences_v2.9.2.txt']=("Reference facts, not live character rewards.\nhttps://foreverquestlog.com/quests/{questID}/ : 3441 3442 3443 3452 3454 3462 3481 4022 4023 4024.\nhttps://www.wowhead.com/forever/quest=3453/the-torch-of-retribution\nhttps://www.wowhead.com/forever/quest=3463/set-them-ablaze\nActual XP/money may differ with character level and server settings. Unknown categories are not confirmed zero.\n").encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,11,28,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.create_system=3;info.external_attr=0o100644<<16;z.writestr(info,data)
    with zipfile.ZipFile(output) as z: assert z.testzip() is None and set(z.namelist())==set(files)
    h=sha(output.read_bytes());print(json.dumps(dict(file=output.name,sha256=h,entries=len(files),size=output.stat().st_size)));return h
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--base',type=Path);p.add_argument('--output',type=Path);p.add_argument('--expected-sha');a=p.parse_args();h=build(a.base or a.root/'addons'/OLD,a.output or a.root/'addons'/NEW);assert not a.expected_sha or h==a.expected_sha
