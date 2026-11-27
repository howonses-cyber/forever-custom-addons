#!/usr/bin/env python3
"""Mock EUI native party frame bridge on Lua 5.1 and LuaJIT; no live client."""
import argparse
from pathlib import Path

HERE=Path(__file__).parent
TEST=r'''
assert(SLASH_FOREVERPARTYINRAID1 == '/fpr')
assert(SLASH_FOREVERPARTYINRAID2 == '/공대파티')
__fire('ADDON_LOADED','ForeverPartyInRaid')
__fire('PLAYER_LOGIN')
assert(ForeverPartyInRaidDB.enabled == true)
assert(#__state.frames == 3, 'No custom visible frame or status bars')
local raid,party=__ns._RFVisWanted()
assert(raid and party, 'Both original EUI raid and party frame sets should display')
assert(__state.raidShown and __state.partyShown)
assert(__ns._partyHeader:GetAttribute('groupFilter')=='3')
assert(__state.lastMacro:find('[@raid1,exists] show;',1,true)==1)
assert(__ns._partyContainerFrame:IsShown())
assert(__ns._PartyInRaid() == true)
assert(__ns._SmallRaidGroup() == 3)
assert(#__ns._kitPortraitUnits == 45, 'extend native portraits to raid40')
__fire('UNIT_HEALTH','raid7')
assert(__state.healthMirror==1)
__fire('UNIT_MAXHEALTH','raid7')
assert(__state.healthMirror==2 and __state.maxHealth==1)
__fire('UNIT_POWER_UPDATE','raid7')
assert(__state.powerMirror==1)
__fire('UNIT_HEALTH','raid25')
assert(__state.healthMirror==2, 'Only own 5 native frames get mirrored events')
__state.group=4
__fire('GROUP_ROSTER_UPDATE')
assert(__ns._partyHeader:GetAttribute('groupFilter')=='4')
assert(__ns._SmallRaidGroup()==4)
__state.instanceKind='arena'
__fire('GROUP_ROSTER_UPDATE')
local rr,pp=__ns._RFVisWanted()
assert(not rr and pp,'arena must preserve original EUI party-only display')
__state.instanceKind='pvp'
__fire('GROUP_ROSTER_UPDATE')
assert(__state.raidShown and __state.partyShown)
__state.inCombat=true
__state.group=6
__fire('GROUP_ROSTER_UPDATE')
assert(__ns._SmallRaidGroup()==4,'Never apply subgroup changes while combat locked')
__slash('off')
assert(ForeverPartyInRaidDB.enabled==true,'defer protected changes in combat')
assert(__state.protectedWrites==0)
__state.inCombat=false
__fire('PLAYER_REGEN_ENABLED')
assert(ForeverPartyInRaidDB.enabled==false)
local r,p=__ns._RFVisWanted()
assert(r and not p, 'Disabling restores native raid-only policy')
assert(__state.raidShown and not __state.partyShown)
assert(__state.lastMacro:find('[@raid1,exists] hide;',1,true)==1)
__slash('on')
assert(__ns._SmallRaidGroup()==6)
assert(__ns._partyHeader:GetAttribute('groupFilter')=='6')
assert(__state.raidShown and __state.partyShown)
__state.inRaid=false
__fire('GROUP_ROSTER_UPDATE')
assert(not __state.raidShown and __state.partyShown)
assert(__ns._PartyInRaid()==false)
assert(__state.lastMacro:find('[@raid1,exists] hide;',1,true)==1)
__state.inRaid=true
__state.memberIndex=0
__fire('GROUP_ROSTER_UPDATE')
assert(__state.raidShown and not __state.partyShown, 'Unknown group must not bind group 1 by default')
__state.memberIndex=7
__state.group=2
__fire('GROUP_ROSTER_UPDATE')
assert(__state.partyShown and __ns._SmallRaidGroup()==2)
assert(__state.protectedWrites==0)
__slash('status')
assert(#__state.messages>=3)
return 1
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--addon-root',required=True)
    args=parser.parse_args()
    toc=Path(args.addon_root,'ForeverPartyInRaid.toc').read_text(encoding='utf8')
    source=Path(args.addon_root,'ForeverPartyInRaid.lua').read_text(encoding='utf8')
    assert 'Version: 1.1.0' in toc
    assert 'Dependencies: EllesmereUI, EllesmereUIRaidFrames' in toc
    assert 'StatusBar' not in source
    assert 'SecureGroupHeaderTemplate' not in source
    assert 'SecureUnitButtonTemplate' not in source
    assert 'SetStatusBar' not in source
    assert 'EllesmereUI._ModuleNS' in source
    assert 'ns._RFVisWanted = function' in source
    assert 'ns._UpdatePartyVisibility()' in source
    assert 'RegisterStateDriver(ns._partyContainerFrame' in source
    assert 'ns._partyUnitToButton' in source
    assert 'ns._UpdateButtonHealth' in source
    from lupa import lua51, luajit21
    for name,engine in [('lua51',lua51),('luajit21',luajit21)]:
        lua=engine.LuaRuntime(unpack_returned_tuples=True)
        lua.execute((HERE/'mock_wow.lua').read_text(encoding='utf8'))
        lua.execute('return function(...)\n' + source + '\nend')('ForeverPartyInRaid')
        assert lua.execute(TEST) == 1
        print(f'PASS {name}: native EUI party header, raid co-display, own subgroup, event mirror, combat gating, disable/restore')
    print('PASS static and Lua mock regressions; LIVE Forever client remains untested')

if __name__=='__main__':
    main()
