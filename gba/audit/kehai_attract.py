# Kehai audit: replay ATTRACT-mode call logs (the ROM's own bot, which clears lines) in the reference,
# to cover scoring/combo/b2b, plus the bot-plan check against Porch Toys' makePlan on reconstructed state.
import sys, os, base64, json, re
sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(__file__),'kehai_diff.py')).read().split("rom = base64")[0])
porch = open(T.PORCH_HTML_PATH, encoding='utf-8').read()
bot = porch[porch.index("function cloneEng(e)"):porch.index("let curPiece = null;")]
for name, src in [('REFB', core), ('REFB_BADCOMBO', bad_combo)]:
    d.execute_script(f"window.{name} = (function(){{ {src}\n const ROWS=28, COLS=12; let eng=null; {bot}\n return {{TETRIAMOND_SET, HEXIAMOND_SET, TrytrisEngine, plan:(e)=>{{eng=e; return makePlan();}} }}; }})();")
d.execute_script("B1337.setRealtime(false)")
rom = base64.b64encode(open(T.ROM_MAIN,'rb').read()).decode()
JS = r"""
const [b64, refName, frames] = arguments; const R = window[refName];
const u8 = Uint8Array.from(atob(b64), c => c.charCodeAt(0)); B1337.loadRom(u8); const g=B1337.gba;
const all=[...R.TETRIAMOND_SET,...R.HEXIAMOND_SET]; const idx={}; all.forEach((p,i)=>idx[p.id]=i+1); const code2={1:'LEFT',2:'RIGHT',3:'ROT_CW',4:'ROT_CCW'};
const res={games:0,locks:0,lockMismatch:0,combo2plus:0,b2b:0,lines:0,plans:0,planMismatch:0,first:null};
let ref=null, refLocks=[], pc=0, pl=0, lastGames=-1, lastSeq=-1;
for (let f=0; f<frames; f++){
  B1337.runFrames(1);
  if (g.read8(0x0203FC09)!==4) continue;
  const games=g.read8(0x0203FDFE), ct=g.read32(0x0203FC38)>>>0, lt=g.read32(0x0203FC3C)>>>0;
  if (games!==lastGames){ lastGames=games; res.games++;
    ref=new R.TrytrisEngine({seed:g.read32(0x0203FC10)>>>0, mode:['NORMAL','CURSED','HEXIAMOND'][g.read8(0x0203FC0A)]});
    refLocks=[]; const ol=Object.getPrototypeOf(ref).lockActivePiece; const me=ref;
    ref.lockActivePiece=function(){const p=this.activePiece,l0=this.lines; ol.call(this); if(this!==me) return; refLocks.push({pid:idx[p.def.id],clr:this.lines-l0,cmb:this.comboStreak,b2b:this.backToBackActive?1:0,score:this.score>>>0,lvl:this.level});};
    pc=0; pl=0; lastSeq=-1; }
  if (ct-pc>64) return {error:'ring overrun at frame '+f};
  while(pc<ct){ const c=g.read8(0x0203FE00+(pc&63)*4+2);
    if(c===1)ref.moveHorizontal(-1);else if(c===2)ref.moveHorizontal(1);else if(c===3)ref.rotate(1);else if(c===4)ref.rotate(-1);else if(c===5)ref.softDrop();else if(c===6)ref.hardDrop();else if(c===7)ref.tick(null); pc++; }
  while(pl<lt){ const b=0x0203FF00+(pl&15)*16, e=refLocks[pl]; res.locks++;
    const rec={pid:g.read8(b),clr:g.read8(b+2),cmb:g.read8(b+10),b2b:g.read8(b+11)&1,score:g.read32(b+12)>>>0,lvl:g.read8(b+3)};
    if (e){ if(e.cmb>=2)res.combo2plus++; if(e.b2b)res.b2b++; res.lines+=e.clr; }
    if(!e||JSON.stringify(rec)!==JSON.stringify(e)){res.lockMismatch++; if(!res.first)res.first={rom:rec,ref:e};}
    pl++; }
  // bot plan check: when the plan buffer is fresh (pos==0) and the piece is new, compare with makePlan on the replayed state
  const pos=g.read8(0x0203FDFF), len=g.read8(0x0203FDE7);
  if (ref && pos===0 && ref.activePiece && !ref.gameOver && ref.activePiece!==lastSeq){ lastSeq=ref.activePiece;
    const want=R.plan ? R.plan(ref) : null; if (want){ res.plans++;
      const got=[]; for(let i=0;i<len;i++) got.push(code2[g.read8(0x0203FDE8+i)]);
      if (JSON.stringify(got)!==JSON.stringify(want)) res.planMismatch++; } }
}
return res;"""
for name in ['REFB','REFB_BADCOMBO']:
    r = d.execute_script(JS, rom, name, 60000)
    print(name, json.dumps(r)[:400])
d.quit()
