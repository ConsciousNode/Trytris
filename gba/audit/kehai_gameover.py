# Kehai audit: reach game over with keys only and screenshot it
import sys, os, base64
sys.path.insert(0, os.path.dirname(__file__))
import run_tests_kehai as T
d, ud = T.start_headless_chrome(); T.load_1337boy_and_reference(d)
rom = base64.b64encode(open(T.ROM_MAIN,'rb').read()).decode()
r = d.execute_script("""
const u8=Uint8Array.from(atob(arguments[0]),c=>c.charCodeAt(0)); B1337.loadRom(u8); const g=B1337.gba;
const tap=(k,n)=>{B1337.setKeys(k);B1337.runFrames(1);B1337.setKeys(0);B1337.runFrames(n);};
B1337.runFrames(3); tap(8,2); let i=0;
while(g.read8(0x0203FC25)!==1 && i<200){ tap(0x40,3); i++; }
const at=[]; for(const extra of [0,30,120]){ B1337.runFrames(extra); at.push(Array.from(B1337.frameBuffer())); }
return {drops:i, over:g.read8(0x0203FC25), screen:g.read8(0x0203FC09), shots:at};""", rom)
from PIL import Image
for k, fb in enumerate(r['shots']):
    Image.frombytes('RGBA',(240,160),bytes(fb)).convert('RGB').resize((480,320),Image.NEAREST).save(f'/tmp/tg_go_{k}.png')
print('drops', r['drops'], 'game_over', r['over'], 'screen', r['screen']); d.quit()
