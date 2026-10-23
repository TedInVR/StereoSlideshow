import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from description_presets import *
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'Settings/music_descriptions.json';store=DescriptionPresets(path)
 assert len(store.load())==7 and store.load()==DEFAULT_DESCRIPTIONS
 text='Quiet piano, warm strings.\nA playful melodic surprise — no drums.'
 store.save('Piano memories',text);assert DescriptionPresets(path).load()['Piano memories']==text
 try:store.save('PIANO MEMORIES','overwrite');raise AssertionError('Duplicate overwritten')
 except PresetError:pass
 assert store.load()['Piano memories']==text
 store.save('Piano memories','Edited',replace=True);assert store.load()['Piano memories']=='Edited'
 name=next(iter(DEFAULT_DESCRIPTIONS));store.remove(name);assert name not in DescriptionPresets(path).load() and len(store.load())==7
 before=path.read_bytes()
 for name,text in [('',text),('Empty',' ')]:
  try:store.save(name,text);raise AssertionError('Blank accepted')
  except PresetError:pass
 assert path.read_bytes()==before
 path.write_text('broken JSON')
 try:store.save('New','Some text');raise AssertionError('Corrupt file overwritten')
 except PresetError:pass
 assert path.read_text()=='broken JSON'
print('Seven exact starter descriptions, multiline Unicode persistence, update/case collision, removal, blank validation and corrupt-file preservation passed.')
