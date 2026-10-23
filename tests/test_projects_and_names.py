import sys,tempfile,json,shutil,threading,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
from project_bundle import *
from output_names import *
with tempfile.TemporaryDirectory() as td:
 root=Path(td);(root/'a').mkdir();(root/'b').mkdir();first=root/'a/photo.jpg';second=root/'b/photo.jpg';clip=root/'a/clip.mp4';song=root/'a/song.wav'
 for path,content in [(first,b'first'),(second,b'second'),(clip,b'clip'),(song,b'song')]:path.write_bytes(content)
 snapshot=dict(settings={'title':'Our Trip'},media=[{'path':str(second),'sound':True},{'path':str(first),'sound':True},{'path':str(clip),'sound':False}],music=[str(song),str(song)],captions={str(first):'',str(second):'Second photo',str(clip):'Our clip'})
 project=new_project_path(root,'Our Trip');save_project(project,snapshot)
 data=read_project(project);assert [Path(x['resolved']).read_bytes() for x in data['media']]==[b'second',b'first',b'clip'];assert not data['media'][2]['sound'];assert len(data['music'])==2 and data['music'][0]['path']==data['music'][1]['path'];assert data['captions'][data['media'][1]['resolved']]==''
 count=len(list((project.parent/'Media').iterdir()));save_project(project,snapshot);assert len(list((project.parent/'Media').iterdir()))==count
 original=project.read_bytes();bad=dict(snapshot,music=[str(root/'missing.wav')])
 try:save_project(project,bad);raise AssertionError('missing source accepted')
 except ProjectError:pass
 assert project.read_bytes()==original
 cancel=threading.Event();cancel.set()
 try:save_project(project,snapshot,cancel);raise AssertionError('cancel ignored')
 except ProjectCancelled:pass
 assert project.read_bytes()==original
 moved=root/'Moved Project';shutil.move(project.parent,moved);shutil.rmtree(root/'a');shutil.rmtree(root/'b');project=moved/project.name;data=read_project(project)
 assert all(Path(item['resolved']).is_file() for item in data['media']+data['music'])
 raw=json.loads(project.read_text());raw['media'][0]['path']='../escape.jpg';project.write_text(json.dumps(raw))
 try:read_project(project);raise AssertionError('path escape accepted')
 except ProjectError:pass
 names=export_paths(root,'Mom at the Beach',1080,240);assert names['sbs'].name=='Mom at the Beach_StereoSlideshow_Full_SBS_3D_1080p_4min.mp4'
 assert export_paths(root,'Trip',2160,243)['sbs'].name.endswith('_2160p_4min03sec.mp4')
 assert re.match(r'\d{8}_StereoSlideshow_',export_paths(root,' ',540,44)['sbs'].name)
 names['sbs'].write_bytes(b'keep');nextnames=export_paths(root,'Mom at the Beach',1080,240);assert nextnames['sbs']!=names['sbs'] and names['sbs'].read_bytes()==b'keep'
 assert safe_title('Bad:/\\Name\nHere')=='Bad Name Here';assert len(safe_title('🦋'*100).encode())<=120
print('Portable project/order/duplicate names/music/captions/mute, incremental save, cancellation/failed-save safety, path validation and export names/collision checks passed.')
