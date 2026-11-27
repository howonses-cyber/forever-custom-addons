#!/usr/bin/env python3
"""Rebuild the reviewed guide-rendering hotfix from the SHA-pinned V2.9.3 ZIP."""
import argparse, hashlib, json, zipfile
from pathlib import Path
OLD='ForeverQuestGuide_Forever_v2.9.3_UnifiedCards_RewardWindow.zip'
NEW='ForeverQuestGuide_Forever_v2.9.4_GuideRecovery_RewardIsolation.zip'
BASE_SHA='556cb0c362a3ed0c89b3d48998cc198b26eeb6f4d3a9e79bb76cff25f6927385'
ROOT='ForeverDungeonQuestGuide/'
def sha(data): return hashlib.sha256(data).hexdigest()
def build(base, output):
    assert sha(base.read_bytes())==BASE_SHA, 'V2.9.3 base hash mismatch'
    with zipfile.ZipFile(base) as z:
        assert z.testzip() is None
        files={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    def edit(name,old,new,count=1):
        path=ROOT+name;s=files[path].decode();assert s.count(old)==count,(name,old[:90],s.count(old));files[path]=s.replace(old,new).encode()
    for name,key in [('Core.lua','version'),('UI.lua','uiVersion'),('QuestChains.lua','chainVersion'),('QuestJourney.lua','journeyVersion'),('QuestSections.lua','questSectionsVersion'),('QuestStatus.lua','statusVersion'),('QuestTitleGroups.lua','titleGroupsVersion'),('QuestRewards.lua','rewardsVersion')]:
        edit(name,'G.'+key+'="2.9.3"','G.'+key+'="2.9.4"')
    edit('ForeverDungeonQuestGuide.toc','## Version: 2.9.3','## Version: 2.9.4')
    # Normalize fields from DBs that serialize numeric requirements as strings.
    edit('QuestData.lua','local min=G.GetQuestMinLevel(id);if min>0 then','local min=tonumber(G.GetQuestMinLevel(id)) or 0;if min>0 then')
    edit('QuestData.lua',''' if type(skill)=="table" and tonumber(skill[1]) and tonumber(skill[2]) and skill[1]>0 then out[#out+1]=(skill[1]==186 and "채광" or "전문기술 #"..skill[1]).." "..skill[2] end''',''' local skillId,skillLevel
 if type(skill)=="table" then skillId,skillLevel=tonumber(skill[1]),tonumber(skill[2]) end
 if skillId and skillLevel and skillId>0 then out[#out+1]=(skillId==186 and "채광" or "전문기술 #"..skillId).." "..skillLevel end''')
    edit('QuestData.lua',''' if type(rep)=="table" and tonumber(rep[1]) and tonumber(rep[2]) and rep[1]>0 then
  local threshold=({[0]="중립",[3000]="약간 우호적",[9000]="우호적",[21000]="매우 우호적",[42000]="확고한 동맹"})[rep[2]] or tostring(rep[2])''',''' local repId,repLevel
 if type(rep)=="table" then repId,repLevel=tonumber(rep[1]),tonumber(rep[2]) end
 if repId and repLevel and repId>0 then
  local threshold=({[0]="중립",[3000]="약간 우호적",[9000]="우호적",[21000]="매우 우호적",[42000]="확고한 동맹"})[repLevel] or tostring(repLevel)''')
    edit('QuestData.lua','(rep[1]==529 and "은빛 여명회" or "평판 #"..rep[1])','(repId==529 and "은빛 여명회" or "평판 #"..repId)')
    # Reward data may be late, incomplete or stale. Keep it outside the guide path.
    edit('QuestRewards.lua','local dbName=ItemDB and G.DBGet and G.DBGet(ItemDB,id,"name")','local dbName=ItemDB and safe(G.DBGet,ItemDB,id,"name")')
    edit('QuestRewards.lua','if G.KoreanName and name then return G.KoreanName("item",id,name) or name end','if G.KoreanName and type(name)=="string" then return safe(G.KoreanName,"item",id,name) or name end')
    edit('QuestRewards.lua','local inLog=G.IsInLog and G.IsInLog(id)==true','local inLog=safe(G.IsInLog,id)==true')
    edit('QuestRewards.lua',''' local history=G.db and G.db.questRewardHistory
 if type(history)~="table" and G.db then history={};G.db.questRewardHistory=history end''',''' local history=G.db and G.db.questRewardHistory
 if type(history)~="table" and G.db then history={};G.db.questRewardHistory=history end
 local function validRecord(record)
  return type(record)=="table" and record or nil
 end
 local function validItems(items)
  return type(items)=="table" and items or {}
 end''')
    edit('QuestRewards.lua','local previous=observed[id] or (history and history[id]) or {}','local previous=validRecord(observed[id]) or validRecord(history and history[id]) or {}')
    edit('QuestRewards.lua','result.choices or previous.choices or {},fixed=#result.fixed>0 and result.fixed or previous.fixed or {},money=(result.money or 0)>0 and result.money or previous.money,xp=(result.xp or 0)>0 and result.xp or previous.xp','result.choices or validItems(previous.choices),fixed=#result.fixed>0 and result.fixed or validItems(previous.fixed),money=(result.money or 0)>0 and result.money or tonumber(previous.money),xp=(result.xp or 0)>0 and result.xp or tonumber(previous.xp)')
    edit('QuestRewards.lua','local old=observed[id] or (history and history[id])','local old=validRecord(observed[id]) or validRecord(history and history[id])')
    edit('QuestRewards.lua','money=info.money,xp=info.xp,source=source,reference=true,referenceXP=info.xp~=nil','money=tonumber(info.money),xp=tonumber(info.xp),source=source,reference=true,referenceXP=tonumber(info.xp)~=nil')
    edit('QuestRewards.lua','''   for _,entry in ipairs(info[key] or {}) do
    local itemId=tonumber(entry.id or entry[1]);local name=entry.name or entry[2]
    if itemId then extra[key][#extra[key]+1]={id=itemId,name=nameOf(itemId,name),count=entry.count or 1} end
   end''','''   for _,entry in ipairs(validItems(info[key])) do
    if type(entry)=="table" then
     local itemId=tonumber(entry.id or entry[1]);local name=entry.name or entry[2]
     if itemId and itemId>0 then extra[key][#extra[key]+1]={id=itemId,name=nameOf(itemId,type(name)=="string" and name or nil),count=math.max(1,tonumber(entry.count) or 1)}
     elseif type(name)=="string" and name~="" then extra[key][#extra[key]+1]={name=name,count=math.max(1,tonumber(entry.count) or 1)} end
    end
   end''')
    # Optional reward diagnostics must not abort the main guide. Avoid repeated chat spam.
    edit('UI.lua','function widgets.RewardOffset(value)', '''function widgets.RecordExtraError(section,err)
 local message=tostring(err or "응답 형식 확인 필요")
 G.uiOptionalErrors=G.uiOptionalErrors or {}
 if G.uiOptionalErrors[section]~=message then
  G.uiOptionalErrors[section]=message
  if G.Print then G.Print(section.." 확인 오류 · "..message) end
 end
end
function widgets.TryExtra(section,fn,...)
 if type(fn)~="function" then return nil end
 local ok,value=pcall(fn,...)
 if not ok then widgets.RecordExtraError(section,value);return nil end
 return value
end
function widgets.RewardRows(id,info)
 info=info or widgets.TryExtra("보상 조회",G.QuestRewardInfo,id)
 if type(info)~="table" then
  return {"보상 자료를 읽지 못했습니다.","공략은 계속 사용할 수 있습니다. [보상 다시 조회]로 재시도하세요."},nil
 end
 local lines=widgets.TryExtra("보상 표시",G.QuestRewardLines,info)
 if type(lines)~="table" or #lines==0 then return {"보상 표시 자료 확인 필요","[보상 다시 조회]로 재시도하세요."},info end
 local clean={}
 for _,line in ipairs(lines) do if type(line)=="string" then clean[#clean+1]=line end end
 if #clean==0 then clean={"보상 표시 자료 확인 필요"} end
 return clean,info
end
function widgets.RewardOffset(value)''')
    edit('UI.lua',''' p.heading:SetText(G.GetQuestName(id))
 local rows=G.QuestRewardLines and G.QuestRewardLines(info or (G.QuestRewardInfo and G.QuestRewardInfo(id))) or {"보상 자료 확인 필요"}''',''' p.heading:SetText(widgets.TryExtra("보상 제목",G.GetQuestName,id) or ("퀘스트 "..id))
 local rows,reward=widgets.RewardRows(id,info)
 widgets.rewardCacheId=id;widgets.rewardCache=reward
 local brief=reward and widgets.TryExtra("보상 요약",G.QuestRewardBrief,reward)
 widgets.rewardPreview=type(brief)=="string" and brief or "보상 · 자료 확인 필요"
 if widgets.detailHint and not detailsExpanded then widgets.detailHint:SetText(shortLine(widgets.rewardPreview,480)) end''')
    edit('UI.lua','''  local info=q and G.QuestRewardInfo and G.QuestRewardInfo(q)
  itemTooltip(self,info and G.QuestRewardLines and G.QuestRewardLines(info) or {"퀘스트 보상","퀘스트를 선택하세요."})''','''  itemTooltip(self,{"퀘스트 보상",q and "클릭하면 선택한 퀘스트의 보상 창이 열립니다." or "퀘스트를 선택하세요."})''')
    edit('UI.lua','if G.RetryQuestReward then G.RetryQuestReward(G.selection.quest) end','widgets.TryExtra("보상 재조회",G.RetryQuestReward,G.selection.quest)')
    edit('UI.lua','if G.RetryQuestReward then G.RetryQuestReward(id) end','widgets.TryExtra("보상 재조회",G.RetryQuestReward,id)')
    # Extract the normal overview renderer, and render it before optional detail builders.
    path=ROOT+'UI.lua';s=files[path].decode()
    a=s.index('  local displayName=desc.name\n',s.index('function G.UIRefresh()'))
    b=s.index('  if widgets.rewardFocusQuest==q then\n',a)
    overview=s[a:b].replace('  lines[#lines+1]="\\n확인용 퀘스트 번호: "..q\n', "")
    overview=overview.replace('local displayName=desc.name','local displayName=desc.name or (widgets.TryExtra("퀘스트 이름",G.GetQuestName,q) or ("퀘스트 "..q))')
    overview=overview.replace('displayName=displayName.." · "..G.TitleChapterStepLabel(q,1)','displayName=displayName.." · "..(widgets.TryExtra("연계 단계 이름",G.TitleChapterStepLabel,q,1) or "진행 단계")')
    overview=overview.replace('local reportName=G.QuestContactName and G.QuestContactName(q,"turnin")','local reportName=widgets.TryExtra("보고 대상",G.QuestContactName,q,"turnin")')
    overview=overview.replace('(G.QuestObjectiveText and G.QuestObjectiveText(q))','widgets.TryExtra("퀘스트 목표",G.QuestObjectiveText,q)')
    # Ensure all five bodies are updated even before extended data is consulted.
    helper='''function widgets.RenderGuideSummary(q,desc,j,status,isSkipped,startItem,progress)
'''+overview+'''end
function widgets.PrimeGuide(q)
 if not q then return end
 local j=widgets.TryExtra("기본 공략",journey,q)
 local status=widgets.TryExtra("퀘스트 상태",questStatus,q) or {key="unknown",label="기록 확인",detail="실제 퀘스트 기록을 확인하세요."}
 if type(j)~="table" then j={title="진행 정보 확인",verb="확인 필요",location="실제 위치 확인 필요",detail="게임 퀘스트 로그에서 목표를 확인하세요.",nextText="자료가 로드되면 다시 확인하세요."} end
 local desc={name=widgets.TryExtra("퀘스트 이름",G.GetQuestName,q),goal=widgets.TryExtra("퀘스트 목표",G.QuestObjectiveText,q)}
 widgets.RenderGuideSummary(q,desc,j,status,false,nil,nil)
 if detailQuest~=q then
  local rows={"지금 할 일: "..tostring(j.title or "확인 필요"),"장소: "..tostring(j.location or "위치 확인 필요"),tostring(j.detail or "게임 로그 확인"),"다음: "..tostring(j.nextText or "진행 상황 확인")}
  detailText(table.concat(rows,"\\n"),q)
 end
 if widgets.rewardButton then widgets.rewardButton:Enable();widgets.wideRewardButton:Enable() end
end
'''
    s=s[:a]+'''  lines[#lines+1]="\\n확인용 퀘스트 번호: "..q
  detailText(table.concat(lines,"\\n"),q)
'''+s[s.index('\n else\n  widgets.rewardPreview="보상 · 퀘스트 선택 후 확인"',b):]
    s=s.replace('function G.UIRefresh()\n',helper+'function G.UIRefresh()\n',1)
    marker=''' if pendingScrollAnchor and G.QuestFindAnchor then
'''
    assert s.count(marker)==1
    s=s.replace(marker,''' -- Commit the basic guide as soon as the selected ID is determined.
 -- Do not let a failing secondary pane leave five empty headings.
 if G.selection.quest then widgets.PrimeGuide(G.selection.quest) end
'''+marker,1)
    old='''  local desc=G.QuestDetails(q);local j=journey(q);local chain=chainByQuest[q];local startItem=G.QuestStartItemGuide and G.QuestStartItemGuide(q)
  local reward=G.QuestRewardInfo and G.QuestRewardInfo(q)
  widgets.rewardPreview=reward and G.QuestRewardBrief and G.QuestRewardBrief(reward) or "보상 · 확인 필요"
  local status=questStatus(q)
  local isSkipped=G.TitleBranchSkipped and G.TitleBranchSkipped(q)'''
    new='''  local desc=widgets.TryExtra("퀘스트 상세",G.QuestDetails,q) or {name=G.GetQuestName(q),all={},one={}}
  local j=journey(q);local chain=chainByQuest[q];local startItem=widgets.TryExtra("시작 아이템",G.QuestStartItemGuide,q)
  widgets.rewardPreview="보상 · [보상 보기]에서 확인"
  if widgets.rewardCacheId==q and widgets.rewardCache then
   widgets.rewardPreview=widgets.TryExtra("보상 요약",G.QuestRewardBrief,widgets.rewardCache) or widgets.rewardPreview
  end
  local status=questStatus(q)
  local isSkipped=G.TitleBranchSkipped and G.TitleBranchSkipped(q)
  local progress=(status.key=="active" or status.key=="turnin") and objectiveProgress(q) or nil
  widgets.RenderGuideSummary(q,desc,j,status,isSkipped,startItem,progress)
  -- Optional detail text is independent of the overview and navigation buttons.
  local ok,why=pcall(function()'''
    assert s.count(old)==1;s=s.replace(old,new,1)
    # Remove duplicate declaration within optional block.
    old2='''  local progress=(status.key=="active" or status.key=="turnin") and objectiveProgress(q) or nil
  if progress and progress.available then'''
    assert s.count(old2)==1;s=s.replace(old2,'''  if progress and progress.available then''',1)
    old3='''  for _,line in ipairs(G.JourneyDetailLines(q)) do lines[#lines+1]=line end
  if G.QuestRewardLines then
   lines[#lines+1]="\\n|cff9cd9f0퀘스트 보상|r"
   for _,text in ipairs(G.QuestRewardLines(reward)) do lines[#lines+1]=text end
  end'''
    new3='''  local journeyLines=widgets.TryExtra("상세 동선",G.JourneyDetailLines,q)
  if type(journeyLines)=="table" then
   for _,line in ipairs(journeyLines) do if type(line)=="string" then lines[#lines+1]=line end end
  else
   lines[#lines+1]="지금 할 일: "..tostring(j.title or "확인 필요")
   lines[#lines+1]="장소: "..tostring(j.location or "위치 확인 필요")
   lines[#lines+1]=tostring(j.detail or "게임 퀘스트 로그 확인")
   lines[#lines+1]="다음: "..tostring(j.nextText or "진행 상황 확인")
   lines[#lines+1]="추가 동선 자료 확인 필요 · 기본 공략은 유지됩니다."
  end
  lines[#lines+1]="\\n|cff9cd9f0퀘스트 보상|r · 위 [보상 보기]에서 별도 조회"'''
    assert s.count(old3)==1;s=s.replace(old3,new3,1)
    s=s.replace('local walkthrough=G.WalkthroughDetails and G.WalkthroughDetails(q)','local walkthrough=widgets.TryExtra("자세한 수행 방법",G.WalkthroughDetails,q)',1)
    old4='''  detailText(table.concat(lines,"\\n"),q)

 else
  widgets.rewardPreview="보상 · 퀘스트 선택 후 확인"'''
    new4='''  detailText(table.concat(lines,"\\n"),q)
  end)
  if not ok then
   widgets.RecordExtraError("상세 공략",why)
   widgets.relationshipInfo:SetText("추가 공략 자료 확인 필요 · 기본 공략 유지")
   local rows={"지금 할 일: "..tostring(j.title or "확인 필요"),"장소: "..tostring(j.location or "위치 확인 필요"),tostring(j.detail or "게임 로그 확인"),"다음: "..tostring(j.nextText or "진행 상황 확인"),"","일부 상세 자료를 읽지 못했습니다. 기본 공략과 지도 버튼은 계속 사용할 수 있습니다."}
   detailText(table.concat(rows,"\\n"),q)
  end
 else
  widgets.rewardPreview="보상 · 퀘스트 선택 후 확인"'''
    assert s.count(old4)==1;s=s.replace(old4,new4,1)
    s=s.replace(' if widgets.rewardPopup and widgets.rewardPopup:IsShown() then widgets.RefreshRewardPopup() end\n','',1)
    tail=''' widgets.navStatus:SetText(displayText(G.guideFeedback or ("지도 길찾기: "..(G.navStatus or "대기"))))
end'''
    assert s.count(tail)==1
    s=s.replace(tail,''' widgets.navStatus:SetText(displayText(G.guideFeedback or ("지도 길찾기: "..(G.navStatus or "대기"))))
 if widgets.rewardPopup and widgets.rewardPopup:IsShown() then
  widgets.TryExtra("보상 창 갱신",widgets.RefreshRewardPopup)
 end
end''',1)
    files[path]=s.encode()
    # Tests load the real reward provider as well as fault-injecting the UI boundary.
    edit('tests/test_ui.lua','test("Closing browser also closes contact preview"', '''test("V2.9.4 reward exceptions cannot blank or interrupt any guide field",function()
 local w=G.UIJourneyWidgets;local oldInfo,oldLines,oldBrief=G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief
 local reads=0
 G.QuestRewardInfo=function()reads=reads+1;error("injected reward provider failure")end
 G.QuestRewardLines=function()error("injected reward formatter failure")end
 G.QuestRewardBrief=function()error("injected reward summary failure")end
 for _,id in ipairs({90101,90102,3801,90105}) do
  G.SetQuest(id);has(w.detailHead:GetText(),G.GetQuestName(id))
  for i=1,5 do assert(w.overviewRows[i].text:GetText()~="","empty guide field "..i)end
  has(w.detailText:GetText(),"지금 할 일")
 end
 eq(reads,0,"guide refresh must not query live rewards")
 G.SetQuest(90101);w.rewardButton:Click();assert(w.rewardPopup:IsShown());has(w.rewardPopup.body:GetText(),"보상 자료를 읽지 못했습니다")
 local before=reads;G.SetQuest(90102);assert(reads>before);has(w.detailHead:GetText(),G.GetQuestName(90102));has(w.rewardPopup.heading:GetText(),G.GetQuestName(90102))
 G.QuestRewardInfo=function(id)return {id=id,available=true,choices={},fixed={},xp=10} end
 w.rewardPopup.retry:Click();has(w.rewardPopup.body:GetText(),"보상 표시 자료 확인 필요")
 w.rewardPopup:Hide();G.QuestRewardInfo,G.QuestRewardLines,G.QuestRewardBrief=oldInfo,oldLines,oldBrief;G.UIRefresh();checkPreserved()
end)
test("V2.9.4 malformed optional details do not leave a blank or stale guide",function()
 local w=G.UIJourneyWidgets;local details,journeyLines,walk=G.QuestDetails,G.JourneyDetailLines,G.WalkthroughDetails
 G.QuestDetails=function()error("injected quest metadata fault")end
 G.JourneyDetailLines=function()error("injected journey detail fault")end
 G.WalkthroughDetails=function()error("injected walkthrough fault")end
 G.SetQuest(90101);has(w.detailHead:GetText(),G.GetQuestName(90101));has(w.detailText:GetText(),"지금 할 일")
 for i=1,5 do assert(w.overviewRows[i].text:GetText()~="")end
 G.SetQuest(90102);has(w.detailHead:GetText(),G.GetQuestName(90102));has(w.detailText:GetText(),"기본 공략")
 w.detailToggle:Click();assert(w.detailScroll:IsShown());has(w.detailText:GetText(),"지금 할 일");w.detailToggle:Click()
 G.QuestDetails,G.JourneyDetailLines,G.WalkthroughDetails=details,journeyLines,walk;G.UIRefresh();checkPreserved()
end)
test("V2.9.4 real reward module with stale history is integrated with guide",function()
 local w=G.UIJourneyWidgets
 loadAddon("QuestRewards.lua")
 G.db.questRewardHistory={[90101]={choices="bad",fixed={{id=777,count="3",name="검사 보상"},true},xp="50"},[90102]=true}
 HaveQuestRewardData=function()return true end
 G.SetQuest(90101);has(w.detailHead:GetText(),G.GetQuestName(90101));w.rewardButton:Click()
 has(w.rewardPopup.body:GetText(),"검사 보상");has(w.rewardPopup.body:GetText(),"×3")
 G.SetQuest(90102);has(w.detailHead:GetText(),G.GetQuestName(90102));has(w.rewardPopup.body:GetText(),"보상 자료 확인 필요")
 w.rewardPopup:Hide();G.db.questRewardHistory=nil;HaveQuestRewardData=nil;G.UIRefresh();checkPreserved()
end)
test("Closing browser also closes contact preview"''')
    edit('tests/test_rewards_v291.lua','check(G.QuestRewardBrief({available=false})', '''G.db.questRewardHistory[77779]={choices="invalid",fixed={{id=4321,name="기존 기록",count="2"},false},money="100",xp="42"}
local restored=G.QuestRewardInfo(77779)
check(restored.available and restored.reference and restored.fixed[1].count==2 and restored.xp==42,'legacy reward history types normalized')
G.db.questRewardHistory[77780]=true
check(not G.QuestRewardInfo(77780).available,'malformed legacy record does not throw')
check(G.QuestRewardBrief({available=false})''')
    files[ROOT+'Docs/CHANGELOG_v2.9.4.txt']=('V2.9.4: Core five-step guide is rendered before optional metadata; reward network requests are restricted to the independent reward window; optional lookup/format exceptions are visible and isolated. Legacy reward history and numeric quest requirements normalized. New mock regressions exercise exceptions and actual reward module integration. Exact live-client exception is not established without the client Lua error log.').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,11,28,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.create_system=3;info.external_attr=0o100644<<16;z.writestr(info,data)
    with zipfile.ZipFile(output) as z: assert z.testzip() is None and set(z.namelist())==set(files)
    h=sha(output.read_bytes());print(json.dumps(dict(file=output.name,sha256=h,entries=len(files),size=output.stat().st_size)));return h
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--base',type=Path);p.add_argument('--output',type=Path);p.add_argument('--expected-sha');a=p.parse_args();h=build(a.base or a.root/'addons'/OLD,a.output or a.root/'addons'/NEW);assert not a.expected_sha or h==a.expected_sha
