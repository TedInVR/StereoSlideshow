from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
version=json.loads((root/'project.json').read_text())['version']
ignored={'.git','__pycache__','Runtime','Settings','Logs','Updates','.venv','Generated Music','Stereo Slideshows'}
files=[p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts)&ignored) and p.name not in {'manifest.json','.DS_Store'} and p.suffix!='.zip']
(root/'manifest.json').write_text(json.dumps({'version':version,'sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}},indent=2)+'\n')
output=root.parent/('Stereo_Slideshow_Update_v'+version+'.zip')
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[root/'manifest.json']:z.write(p,Path('Stereo Slideshow')/p.relative_to(root))
print(output)
