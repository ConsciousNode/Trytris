# Kehai audit: independent engine differential for Trytris GBA.
# Input reaches the ROM only through setKeys; ROM state is read only through the mailbox.
# Mode is chosen and the seed randomized on the title screen with keys. The reference
# engine is the attached trytris/index.html, unmodified, except in the two positive controls.
import sys, os, base64, json, re, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import run_tests_kehai as T
d, ud = T.start_headless_chrome()
b1337 = open(T.B1337_HTML_PATH,'rb').read()
assert hashlib.sha256(b1337).hexdigest().startswith('e7bd2b3a')
d.get("about:blank"); fid = d.execute_cdp_cmd("Page.getFrameTree", {})["frameTree"]["frame"]["id"]
d.execute_cdp_cmd("Page.setDocumentContent", {"frameId": fid, "html": b1337.decode()})
txt = open(T.TRYTRIS_HTML_PATH, encoding='utf-8').read()
script = re.search(r"<script>([\s\S]*?)</script>", txt).group(1)
core = script[:script.index("function runSelfTestSuite()")]
def install(name, src):
    d.execute_script(f"window.{name} = (function(){{ {src}\n return {{TETRIAMOND_SET, HEXIAMOND_SET, ACHIEVEMENT_DEFS, TrytrisEngine}}; }})();")
install('REF', core)
bad_rng = core.replace('0x6D2B79F5', '0x6D2B79F4'); assert bad_rng != core
install('REF_BADRNG', bad_rng)
bad_combo = core.replace('const COMBO_MULTIPLIERS = [1.0, 1.5, 2.0, 2.5, 3.0];', 'const COMBO_MULTIPLIERS = [1.0, 1.75, 2.0, 2.5, 3.0];'); assert bad_combo != core
install('REF_BADCOMBO', bad_combo)
d.execute_script("B1337.setRealtime(false)")
rom = base64.b64encode(open(T.ROM_MAIN,'rb').read()).decode()
JS = r"""
const [b64, refName, mode, games] = arguments; const R = window[refName];
const u8 = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
const all=[...R.TETRIAMOND_SET,...R.HEXIAMOND_SET]; const idx={}; all.forEach((p,i)=>idx[p.id]=i+1);
const tap=(k,n=1)=>{B1337.setKeys(k);B1337.runFrames(1);B1337.setKeys(0);B1337.runFrames(n);};
const res={games:0,locks:0,lockMismatch:0,boardMismatch:0,achMismatch:0,seeds:[],first:null};
B1337.loadRom(u8); const g=B1337.gba; B1337.runFrames(3);
for (let i=0;i<mode;i++) tap(0x10,2);                 // title row 0 = MODE: Right cycles
for (let gm=0; gm<games; gm++){
  tap(0x100, 3+gm*7);                                 // R: randomize seed (depends on frame counter)
  tap(0x008, 1);                                      // START
  const seed=g.read32(0x0203FC10)>>>0, mb=g.read8(0x0203FC0A); res.seeds.push(seed.toString(16));
  if (mb!==mode) return {error:'mode mismatch '+mb};
  const ref=new R.TrytrisEngine({seed, mode:['NORMAL','CURSED','HEXIAMOND'][mode]});
  const refLocks=[]; const origLock=ref.lockActivePiece.bind(ref);
  ref.lockActivePiece=function(){ const p=this.activePiece; const before={id:idx[p.def.id],rot:p.rotIndex,cells:this.getPieceWorldCells(p),lines:this.lines};
    origLock(); refLocks.push({pid:before.id,rot:before.rot,cells:before.cells.map(([r,c])=>((r&15)<<4)|(c&15)),clr:this.lines-before.lines,lvl:this.level,cmb:this.comboStreak,b2b:this.backToBackActive?1:0,score:this.score>>>0}); };
  let pc=0, pl=0, rng=(seed^0x9E3779B9)>>>0;
  for (let s=0;s<400;s++){
    if (g.read8(0x0203FC25)===1) break;
    rng=(Math.imul(rng,1664525)+1013904223)>>>0; const q=rng&255; let k=0;
    if(q<40)k=0x20;else if(q<80)k=0x10;else if(q<115)k=1;else if(q<150)k=2;else if(q<185)k=0x80;else if(q<200)k=0x40;
    B1337.setKeys(k);B1337.runFrames(1);B1337.setKeys(0);B1337.runFrames(9);
    const ct=g.read32(0x0203FC38)>>>0, lt=g.read32(0x0203FC3C)>>>0;
    if (ct-pc>64 || lt-pl>16) return {error:'ring overrun'};
    while(pc<ct){ const code=g.read8(0x0203FE00+(pc&63)*4+2);
      if(code===1)ref.moveHorizontal(-1);else if(code===2)ref.moveHorizontal(1);else if(code===3)ref.rotate(1);else if(code===4)ref.rotate(-1);else if(code===5)ref.softDrop();else if(code===6)ref.hardDrop();else if(code===7)ref.tick(null);
      pc++; }
    while(pl<lt){ const b=0x0203FF00+(pl&15)*16; const e=refLocks[pl]; res.locks++;
      const rec={pid:g.read8(b),rot:g.read8(b+1),clr:g.read8(b+2),lvl:g.read8(b+3),cmb:g.read8(b+10),b2b:g.read8(b+11)&1,score:g.read32(b+12)>>>0,cells:[0,1,2,3,4,5].map(i=>g.read8(b+4+i)).slice(0,e?e.cells.length:4)};
      if(!e || JSON.stringify(rec)!==JSON.stringify({pid:e.pid,rot:e.rot,clr:e.clr,lvl:e.lvl,cmb:e.cmb,b2b:e.b2b,score:e.score,cells:e.cells})){ res.lockMismatch++; if(!res.first) res.first={game:gm,lock:pl,rom:rec,ref:e}; }
      pl++; }
  }
  if (refLocks.length!==pl) res.lockMismatch+=Math.abs(refLocks.length-pl);
  for (let r=0;r<28;r++) for(let c=0;c<12;c++){ const rc=g.read8(0x0203FC94+r*12+c), fc=ref.board[r][c]?idx[ref.board[r][c].pieceId]:0; if(rc!==fc){res.boardMismatch++; r=99; break;} }
  let am=0; R.ACHIEVEMENT_DEFS.forEach((a,bit)=>{ if(ref.earnedAchievements.has(a.id)) am|=1<<bit; });
  if ((g.read32(0x0203FC28)>>>0)!==am) res.achMismatch++;
  res.games++;
  // back to title: if game over, SELECT; else START (pause) then SELECT
  if (g.read8(0x0203FC25)!==1) tap(0x008,1); tap(0x004,2);
}
return res;"""
out = {}
for ref in ['REF','REF_BADRNG','REF_BADCOMBO']:
    out[ref] = [d.execute_script(JS, rom, ref, m, 8) for m in range(3)]
for ref, rs in out.items():
    tot = {k: sum(r.get(k,0) for r in rs) for k in ['games','locks','lockMismatch','boardMismatch','achMismatch']}
    print(ref, tot, '| errors:', [r.get('error') for r in rs if r.get('error')], '| first:', json.dumps(next((r['first'] for r in rs if r.get('first')), None))[:300])
print('seeds NORMAL:', out['REF'][0].get('seeds'))
d.quit()
