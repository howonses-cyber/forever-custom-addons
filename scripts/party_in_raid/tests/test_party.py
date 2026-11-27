#!/usr/bin/env python3
"""Native WoW Lua mock regression: no game client and no visual rendering."""
import argparse
from pathlib import Path

P = Path(__file__).resolve().parent

ASSERTIONS = r'''
assert(SLASH_FOREVERPARTYINRAID1=='/fpr')
assert(SLASH_FOREVERPARTYINRAID2=='/공대파티')
__fire('PLAYER_LOGIN')
local h=ForeverPartyInRaidSecureHeader
local p=ForeverPartyInRaidPanel
assert(h and p)
assert(__state.createdSecure==1)
assert(h:GetAttribute('showRaid')==true)
assert(h:GetAttribute('showParty')==false)
assert(h:GetAttribute('showSolo')==false)
assert(h:GetAttribute('template')=='SecureUnitButtonTemplate')
assert(h:GetAttribute('groupFilter')=='3')
assert(p.stateDriver=='[group:raid]show;hide')
for i=1,5 do
  assert(h[i] and h[i].health and h[i].power and h[i].nameText)
  assert(h[i]:GetAttribute('type1')=='target')
  assert(h[i].clicks=='AnyUp')
end
__fire('UNIT_HEALTH')
assert(h[1].health.value==72)
assert(h[1].power.value==61)
assert(h[1].health.barColor[3]==0.87)
assert(h[1].nameText.text=='Nameraid7')
local before=#__state.frames
__state.groups[7]=4
__fire('GROUP_ROSTER_UPDATE')
assert(h:GetAttribute('groupFilter')=='4')
assert(#__state.frames==before,'roster events must not create secure frames')
__state.inCombat=true
__state.groups[7]=6
__fire('GROUP_ROSTER_UPDATE')
assert(h:GetAttribute('groupFilter')=='4','no protected changes during combat')
assert(__state.protectedWrites==0)
__slash('off')
assert(p.stateDriver=='[group:raid]show;hide','combat toggle must defer')
assert(__state.protectedWrites==0)
__state.inCombat=false
__fire('PLAYER_REGEN_ENABLED')
assert(h:GetAttribute('groupFilter')=='6')
assert(p.stateDriver==nil and p:IsShown()==false)
__slash('on')
assert(p.stateDriver=='[group:raid]show;hide')
__slash('unlock')
assert(ForeverPartyInRaidDB.locked==false)
__slash('scale 1.25')
assert(ForeverPartyInRaidDB.scale==1.25 and p.scale==1.25)
__slash('scale 999')
assert(ForeverPartyInRaidDB.scale==1.25)
__slash('lock')
assert(ForeverPartyInRaidDB.locked==true)
__slash('reset')
assert(ForeverPartyInRaidDB.scale==1 and ForeverPartyInRaidDB.x==32)
__state.inRaid=false
__fire('GROUP_ROSTER_UPDATE')
assert(not h:IsShown(),'must hide on leaving raid')
__state.inRaid=true
__state.raidIndex=0
__fire('GROUP_ROSTER_UPDATE')
assert(not h:IsShown(),'unknown roster: must not show arbitrary raid group')
__state.raidIndex=7
__fire('GROUP_ROSTER_UPDATE')
assert(h:IsShown())
assert(__state.protectedWrites==0)
assert(EUIFakeFrame.original==true,'must not modify EUI')
return 1
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--addon-root',required=True)
    args=p.parse_args()
    source=Path(args.addon_root,'ForeverPartyInRaid.lua').read_text(encoding='utf8')
    mock=(P/'mock_wow.lua').read_text(encoding='utf8')
    if 'EllesmereUIRaidFrames' in source or 'ERFPartyHeader' in source:
        raise SystemExit('Forbidden direct coupling to EUI protected frames')
    if 'PartyMemberFrame' in source and 'PartyMemberFrames or' not in source:
        raise SystemExit('Forbidden Blizzard party-frame modification')
    if 'header:SetAttribute("showParty", false)' not in source:
        raise SystemExit('Missing raid-only overlay contract')
    from lupa import lua51, luajit21
    for name,backend in [('lua51',lua51),('luajit21',luajit21)]:
        lua=backend.LuaRuntime(unpack_returned_tuples=True)
        lua.execute(mock)
        lua.execute('EUIFakeFrame={original=true}')
        lua.execute(source)
        count=lua.execute(ASSERTIONS)
        assert count==1
        print(f'PASS {name}: 36 mocked party/raid visibility, secure buttons, subgroup, protected combat and saved settings assertions')
    print('PASS all native Lua tests; real Forever raid client remains untested')

if __name__=='__main__':main()
