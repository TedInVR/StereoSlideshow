"""Offline OAuth/resumable protocol tests and real lossless stereo remux."""
import copy,json,sys,tempfile,threading,time,urllib.parse,urllib.request,subprocess,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import youtube_upload as y
from engine import binary
class Store:
 def __init__(self,value=None):self.value=value
 def load(self):return copy.deepcopy(self.value)
 def save(self,value):self.value=copy.deepcopy(value)
 def delete(self):self.value=None
base=dict(title='Our trip',description='My own description',tags='3D, family memories',privacy='private',made_for_kids=False,synthetic=True,channel_id='CHANNEL1')
assert y.video_metadata(base)['status']==dict(privacyStatus='private',selfDeclaredMadeForKids=False,containsSyntheticMedia=True)
for changes in ({'title':''},{'title':'a'*101},{'description':'é'*2501},{'privacy':'other'},{'made_for_kids':None},{'title':'<tag>'},{'tags':'x'*501}):
 try:y.video_metadata(dict(base,**changes));raise AssertionError('Invalid plan accepted')
 except y.YouTubeError:pass
with tempfile.TemporaryDirectory() as td:
 root=Path(td);config=root/'client.json';y.atomic_json(config,{'installed':{'client_id':'test.apps.googleusercontent.com','client_secret':'desktop-public-secret'}})
 assert y.client_config(config)['client_id'].startswith('test.')
 for wrong in ({'web':{'client_id':'test.apps.googleusercontent.com','client_secret':'x'}},{'installed':{'client_id':'bad','client_secret':'x'}}):
  y.atomic_json(root/'wrong.json',wrong)
  try:y.client_config(root/'wrong.json');raise AssertionError('Invalid client accepted')
  except y.YouTubeError:pass
 store=Store();seen=[]
 class AuthHTTP:
  def call(self,url,data=None,headers=None,method=None):
   seen.append((url,data,headers))
   if url==y.TOKEN:
    fields=urllib.parse.parse_qs(data.decode());assert fields['code']==['test-code'];assert fields['code_verifier'];return 200,{},json.dumps(dict(access_token='ACCESS',refresh_token='REFRESH',scope=' '.join(y.SCOPES),expires_in=3600)).encode()
   assert url.startswith(y.API+'channels');return 200,{},b'{"items":[{"id":"CHANNEL1","snippet":{"title":"Ted in VR"}}]}'
 def browser(url):
  args=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query);assert args['code_challenge_method']==['S256'] and args['access_type']==['offline']
  callback=args['redirect_uri'][0]
  def send():
   try:urllib.request.urlopen(callback+'?state=wrong&code=attacker',timeout=2)
   except urllib.error.HTTPError as error:assert error.code==400
   urllib.request.urlopen(callback+'?'+urllib.parse.urlencode({'state':args['state'][0],'code':'test-code'}),timeout=2).close()
  threading.Thread(target=send,daemon=True).start()
 client=y.YouTubeClient(store,AuthHTTP());channel=client.connect(config,threading.Event(),browser,lambda s:None);assert channel['id']=='CHANNEL1' and store.value['refresh_token']=='REFRESH'
 cancel=threading.Event()
 try:client.connect(config,cancel,lambda url:cancel.set(),lambda s:None);raise AssertionError('Cancelled auth accepted')
 except y.UploadCancelled:assert store.value['channel']['id']=='CHANNEL1'
 # Expired credentials refresh securely rather than requiring repeated sign-in.
 class RefreshHTTP:
  def call(self,*args):return 200,{},b'{"access_token":"FRESH","expires_in":3600}'
 store.value['expires_at']=0;refreshed=y.YouTubeClient(store,RefreshHTTP()).access();assert refreshed['access_token']=='FRESH' and refreshed['refresh_token']=='REFRESH'
 class UploadHTTP:
  def __init__(self):self.puts=[];self.metadata=None;self.stage=0
  def call(self,url,data=None,headers=None,method=None):
   if url.startswith(y.API+'channels'):return 200,{},b'{"items":[{"id":"CHANNEL1","snippet":{"title":"Ted in VR"}}]}'
   if url==y.UPLOAD:self.metadata=json.loads(data);return 200,{'Location':'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=example'},b''
   self.puts.append(headers['Content-Range']);self.stage+=1
   if self.stage==1:return 503,{},b'' # A dropped response could follow a partial write.
   if self.stage==2:assert data==b'';return 308,{'Range':'bytes=0-262143'},b''
   assert headers['Content-Range']=='bytes 262144-524287/524288';assert len(data)==262144
   return 201,{},b'{"id":"VIDEO123456","status":{"privacyStatus":"private"}}'
 source=root/'upload.mkv';source.write_bytes(b'x'*524288);http=UploadHTTP();client=y.YouTubeClient(store,http)
 class NoWait:
  def is_set(self):return False
  def wait(self,n):return False
 result=client.upload(source,base,NoWait(),lambda s:None,lambda n:None);assert result['url'].endswith('VIDEO123456') and http.metadata==y.video_metadata(base)
 try:client.upload(source,dict(base,channel_id='WRONG'),NoWait(),lambda s:None,lambda n:None);raise AssertionError('Wrong channel accepted')
 except y.YouTubeError:pass
 try:y.GoogleHTTP().call('https://evil.example/upload',b'private',{'Authorization':'Bearer SECRET'});raise AssertionError('Unexpected host accepted')
 except y.YouTubeError:pass
 # Real remux: tagged copy has correct per-eye aspect; source/audio stay intact.
 source=root/'full.mp4';subprocess.run([binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=s=640x240:d=1','-f','lavfi','-i','sine=duration=1','-c:v','libx264','-c:a','aac',str(source)],check=True)
 before=hashlib.sha256(source.read_bytes()).digest();dest=y.prepare_stereo(source,root,threading.Event(),lambda s:None)
 def probe(path):return json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-show_streams','-of','json',str(path)]))
 info=probe(dest)['streams'];assert info[0]['tags']['stereo_mode']=='left_right' and info[0]['display_aspect_ratio']=='4:3' and info[1]['codec_name']=='aac';assert hashlib.sha256(source.read_bytes()).digest()==before
 second=root/'second';second.mkdir();again=y.prepare_stereo(dest,second,threading.Event(),lambda s:None);assert probe(again)['streams'][0]['display_aspect_ratio']=='4:3'
 def audio_bytes(path):return subprocess.check_output([binary('ffmpeg'),'-v','error','-i',str(path),'-map','0:a:0','-c','copy','-f','adts','-'])
 assert audio_bytes(source)==audio_bytes(dest)
 print('OAuth state/PKCE loopback and cancellation, secure-store refresh, metadata validation, channel guard, resumable interrupted-chunk recovery, endpoint restrictions and real no-reencode stereo/audio preservation passed. No live Google upload was performed.')
