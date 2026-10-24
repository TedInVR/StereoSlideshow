"""Desktop Google OAuth and resumable YouTube uploads. Credentials stay in Keychain.

Only approved Google endpoints receive credentials. Publishing is always driven
by the explicit visibility in the user's reviewed upload plan.
"""
import base64, hashlib, hmac, json, mimetypes, os, re, secrets, tempfile, time
import urllib.request, urllib.error, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from fractions import Fraction
from engine import binary
from music_generator import run_ffmpeg
from platform_support import quiet_options

SCOPES=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']
AUTH='https://accounts.google.com/o/oauth2/v2/auth'
TOKEN='https://oauth2.googleapis.com/token'
API='https://www.googleapis.com/youtube/v3/'
UPLOAD='https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'
DEFAULT_DESCRIPTION='Created with Stereo Slideshow by Ted in VR (Ted Witten).\n\n{title}\n\nStereoscopic 3D slideshow. Best enjoyed with a compatible 3D viewer or headset.'
SERVICE='com.ted.stereoslideshow.youtube'
class YouTubeError(RuntimeError):pass
class UploadCancelled(Exception):pass
class NetworkError(YouTubeError):pass

def check(cancel):
    if cancel.is_set():raise UploadCancelled()

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:json.dump(data,out,indent=2)
        os.chmod(name,0o600);os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)

def load_json(path,default=None):
    try:
        value=json.loads(Path(path).read_text())
        return value if isinstance(value,dict) else dict(default or {})
    except (OSError,ValueError):return dict(default or {})

def client_config(path):
    value=load_json(path).get('installed',{})
    if not isinstance(value,dict) or not str(value.get('client_id','')).endswith('.apps.googleusercontent.com') or not value.get('client_secret'):
        raise YouTubeError('Choose a Google OAuth client JSON created for a Desktop app. An API key or Web application client will not work. See Help → User guide → YouTube setup.')
    return {'client_id':value['client_id'],'client_secret':value['client_secret']}

class CredentialStore:
    def _keyring(self):
        try:
            import sys
            if sys.platform=='darwin':
                from keyring.backends.macOS import Keyring
            elif sys.platform=='win32':
                from keyring.backends.Windows import WinVaultKeyring as Keyring
            else:raise YouTubeError('Secure YouTube account storage is supported on macOS and Windows only. No credentials were saved.')
            return Keyring()
        except ImportError as error:raise YouTubeError('Run the installer to install secure YouTube credential storage support.') from error
    def load(self):
        try:
            text=self._keyring().get_password(SERVICE,'account')
            return json.loads(text) if text else None
        except YouTubeError:raise
        except Exception as error:raise YouTubeError('Could not read the YouTube connection from secure system credential storage. Unlock your account and try again.') from error
    def save(self,value):
        try:self._keyring().set_password(SERVICE,'account',json.dumps(value))
        except YouTubeError:raise
        except Exception as error:raise YouTubeError('Could not save the YouTube connection in secure system credential storage.') from error
    def delete(self):
        keyring=self._keyring()
        if keyring.get_password(SERVICE,'account') is not None:keyring.delete_password(SERVICE,'account')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class GoogleHTTP:
    def __init__(self):self.opener=urllib.request.build_opener(NoRedirect())
    def call(self,url,data=None,headers=None,method=None):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com','oauth2.googleapis.com') or parsed.username or parsed.password:raise YouTubeError('Google returned an unexpected server address.')
        req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
        try:
            with self.opener.open(req,timeout=30) as response:return response.status,response.headers,response.read()
        except urllib.error.HTTPError as error:
            return error.code,error.headers,error.read(65536)
        except (OSError,urllib.error.URLError) as error:raise NetworkError('Could not reach Google. Check your connection and try again.') from error

def decoded(body):
    try:return json.loads(body)
    except (ValueError,UnicodeDecodeError):raise YouTubeError('Google returned an unreadable response.')

def api_error(code,body):
    reason=''
    try:
        value=decoded(body).get('error',{})
        if isinstance(value,dict):reason=next((row.get('reason','') for row in value.get('errors',[]) if isinstance(row,dict)),'')
        elif isinstance(value,str):reason=value
    except (YouTubeError,AttributeError):pass
    messages={'quotaExceeded':'The Google project’s YouTube quota is exhausted. Try again after the quota resets.',
        'uploadLimitExceeded':'YouTube’s upload limit for this channel has been reached. Try again later.',
        'youtubeSignupRequired':'This Google account needs a YouTube channel before it can upload.',
        'invalid_grant':'The Google connection expired or was revoked. Disconnect and connect again.',
        'accessNotConfigured':'Enable YouTube Data API v3 in the Google project, then retry.',
        'insufficientPermissions':'Reconnect and grant both requested YouTube permissions.',
        'forbidden':'YouTube refused this action. Check the connected channel and its upload permissions.'}
    return YouTubeError(messages.get(reason,f'Google returned HTTP {code}'+(' ('+reason+')' if reason else '')+'. Check account permission, Google project setup and upload limits.'))

class YouTubeClient:
    def __init__(self,store=None,http=None):self.store=store or CredentialStore();self.http=http or GoogleHTTP()
    def token_request(self,fields):
        code,_,body=self.http.call(TOKEN,urllib.parse.urlencode(fields).encode(),{'Content-Type':'application/x-www-form-urlencoded'},'POST')
        if code!=200:raise api_error(code,body)
        result=decoded(body)
        if not result.get('access_token'):raise YouTubeError('Google did not return an access token.')
        return result
    def access(self,force=False):
        account=self.store.load()
        if not isinstance(account,dict):raise YouTubeError('Connect a YouTube channel first.')
        if force or account.get('expires_at',0)<time.time()+90:
            token=self.token_request(dict(client_id=account['client_id'],client_secret=account['client_secret'],refresh_token=account['refresh_token'],grant_type='refresh_token'))
            account.update(access_token=token['access_token'],expires_at=time.time()+token.get('expires_in',3600))
            if token.get('refresh_token'):account['refresh_token']=token['refresh_token']
            self.store.save(account)
        return account
    def authorized(self,url,data=None,headers=None,method=None):
        for attempt in range(2):
            account=self.access(force=attempt>0);out=dict(headers or {});out['Authorization']='Bearer '+account['access_token']
            response=self.http.call(url,data,out,method)
            if response[0]!=401:return response
        raise YouTubeError('YouTube authorization failed. Reconnect the account.')
    def channel(self):
        code,_,body=self.authorized(API+'channels?part=snippet&mine=true')
        if code!=200:raise api_error(code,body)
        rows=decoded(body).get('items',[])
        if len(rows)!=1:raise YouTubeError('Google did not select a single YouTube channel. Reconnect and choose the intended channel, including the correct Brand Account if applicable.')
        return {'id':rows[0]['id'],'title':rows[0]['snippet']['title']}
    def connect(self,config_path,cancel,open_browser,status):
        config=client_config(config_path);old=self.store.load();state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode();answer={}
        class LoopbackServer(HTTPServer):
            def get_request(self):
                sock,address=super().get_request();sock.settimeout(2);return sock,address
        class Callback(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                parsed=urllib.parse.urlsplit(self.path);query=urllib.parse.parse_qs(parsed.query)
                valid=parsed.path=='/oauth2callback' and hmac.compare_digest(query.get('state',[''])[0],state)
                if valid:
                    answer.update(code=query.get('code',[''])[0],error=query.get('error',[''])[0])
                text=b'You may close this tab and return to Stereo Slideshow.' if valid else b'Invalid authorization response.'
                self.send_response(200 if valid else 400);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(text)
        with LoopbackServer(('127.0.0.1',0),Callback) as server:
            server.timeout=.4;redirect=f'http://127.0.0.1:{server.server_port}/oauth2callback'
            params=dict(client_id=config['client_id'],redirect_uri=redirect,response_type='code',scope=' '.join(SCOPES),state=state,code_challenge=challenge,code_challenge_method='S256',access_type='offline',prompt='consent select_account')
            open_browser(AUTH+'?'+urllib.parse.urlencode(params));status('Choose your YouTube channel and approve access in the browser. Return here when finished.');deadline=time.monotonic()+600
            while not answer:
                check(cancel)
                if time.monotonic()>deadline:raise YouTubeError('YouTube sign-in timed out. Click Connect to try again.')
                server.handle_request()
        check(cancel)
        if answer.get('error') or not answer.get('code'):raise YouTubeError('Google sign-in was declined or did not finish. No new connection was saved.')
        result=self.token_request(dict(config,code=answer['code'],code_verifier=verifier,redirect_uri=redirect,grant_type='authorization_code'))
        if not result.get('refresh_token'):raise YouTubeError('Google did not grant a renewable connection. Reconnect and approve access.')
        scopes=set(result.get('scope',' '.join(SCOPES)).split())
        if not set(SCOPES)<=scopes:raise YouTubeError('Both upload and read-only channel permissions are needed. Connect again and approve both.')
        check(cancel);account=dict(config,access_token=result['access_token'],refresh_token=result['refresh_token'],expires_at=time.time()+result.get('expires_in',3600))
        self.store.save(account)
        try:
            channel=self.channel();account['channel']=channel;check(cancel);self.store.save(account);return channel
        except BaseException:
            if old:self.store.save(old)
            else:self.store.delete()
            raise
    def disconnect(self):
        # Local removal succeeds even if Google cannot currently be reached.
        account=self.store.load();self.store.delete()
        if account:
            try:self.http.call('https://oauth2.googleapis.com/revoke',urllib.parse.urlencode({'token':account.get('refresh_token','')}).encode(),{'Content-Type':'application/x-www-form-urlencoded'},'POST')
            except YouTubeError:pass
    def upload(self,path,plan,cancel,status,progress):
        check(cancel);metadata=video_metadata(plan)
        status('Checking the connected YouTube channel…');channel=self.channel()
        if channel['id']!=plan.get('channel_id'):raise YouTubeError('The connected channel changed. Review the upload screen again before sending the video.')
        path=Path(path);size=path.stat().st_size
        if size<=0:raise YouTubeError('The video file is empty.')
        code,headers,body=self.authorized(UPLOAD,json.dumps(metadata).encode(),{'Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':'video/x-matroska','X-Upload-Content-Length':str(size)},'POST')
        if code not in (200,201):raise api_error(code,body)
        session=headers.get('Location','');parsed=urllib.parse.urlsplit(session)
        if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com') or not parsed.path.startswith('/upload/'):raise YouTubeError('YouTube did not return a valid upload session.')
        offset=0;chunk_size=2*1024*1024;failures=0;query=False
        with path.open('rb') as source:
            while True:
                check(cancel)
                if query:chunk=b'';ranges=f'bytes */{size}'
                else:
                    source.seek(offset);chunk=source.read(min(chunk_size,size-offset))
                    if not chunk:query=True;continue
                    ranges=f'bytes {offset}-{offset+len(chunk)-1}/{size}'
                try:code,headers,body=self.authorized(session,chunk,{'Content-Type':'video/x-matroska','Content-Range':ranges,'Content-Length':str(len(chunk))},'PUT')
                except NetworkError:
                    code=503;headers={};body=b''
                if code in (200,201):
                    result=decoded(body);video_id=result.get('id','')
                    if not re.fullmatch(r'[A-Za-z0-9_-]{6,64}',video_id):raise YouTubeError('Upload finished, but YouTube returned no usable video ID. Check YouTube Studio before retrying to avoid a duplicate.')
                    progress(100);return {'id':video_id,'url':'https://www.youtube.com/watch?v='+video_id,'channel':channel,'privacy':result.get('status',{}).get('privacyStatus',plan['privacy'])}
                if code==308:
                    match=re.fullmatch(r'bytes=0-(\d+)',headers.get('Range',''));new=int(match.group(1))+1 if match else 0
                    if new<offset or new>size:raise YouTubeError('YouTube returned an inconsistent upload position. Check Studio before retrying.')
                    if new==offset:failures+=1
                    else:failures=0
                    if failures>6:raise YouTubeError('YouTube stopped accepting upload data. Check Studio before retrying.')
                    offset=new;query=offset==size;progress(min(99,int(offset/size*100)));status(f'Uploading to {channel["title"]}… {offset/size:.0%}')
                    continue
                if code in (429,500,502,503,504):
                    failures+=1
                    if failures>6:raise YouTubeError('The upload could not recover after several connection attempts. Check YouTube Studio before retrying; local videos are safe.')
                    status('Connection interrupted; checking how much YouTube received…')
                    if cancel.wait(min(2**failures,30)):raise UploadCancelled()
                    query=True;continue
                if code in (404,410):raise YouTubeError('The YouTube upload session expired. Start a new upload; local videos are safe.')
                raise api_error(code,body)

def video_metadata(plan):
    title=plan.get('title','').strip();description=plan.get('description','');privacy=plan.get('privacy','private');tags=[x.strip() for x in plan.get('tags','').split(',') if x.strip()]
    if not title or len(title)>100 or '<' in title or '>' in title:raise YouTubeError('Enter a video title of 1–100 characters without < or >.')
    if len(description.encode('utf-8'))>5000 or '<' in description or '>' in description:raise YouTubeError('Description must fit within 5,000 UTF-8 bytes and cannot contain < or >.')
    if sum(len(x)+(2 if ' ' in x else 0) for x in tags)+max(0,len(tags)-1)>500:raise YouTubeError('The combined tags are too long (500-character limit).')
    if privacy not in ('private','unlisted','public'):raise YouTubeError('Choose Private, Unlisted or Public.')
    if plan.get('made_for_kids') not in (True,False):raise YouTubeError('Choose whether this video is made for kids.')
    return {'snippet':{'title':title,'description':description,'tags':tags,'categoryId':'22'},'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':plan['made_for_kids'],'containsSyntheticMedia':bool(plan.get('synthetic',False))}}

def prepare_stereo(source,directory,cancel,status,half=False):
    """Reuse the established YouTube MKV stereo metadata, without re-encoding."""
    import subprocess
    source=Path(source)
    if source.suffix.lower() not in ('.mp4','.mkv','.mov','.m4v'):raise YouTubeError('Select a rectangular left/right side-by-side MP4, MOV or MKV. VR180 and anaglyph uploads are not handled by this uploader yet.')
    check(cancel);status('Preparing a tagged 3D upload copy (video and audio are copied)…')
    try:
        data=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-select_streams','v:0','-show_entries','stream=width,height,sample_aspect_ratio:stream_tags=stereo_mode','-of','json',str(source)],timeout=30,**quiet_options()))
        stream=data['streams'][0];sar=stream.get('sample_aspect_ratio','1:1');sar=Fraction(sar.replace(':','/')) if sar not in ('N/A','0:1') else Fraction(1)
        tagged=stream.get('tags',{}).get('stereo_mode')=='left_right' and sar!=1
        aspect=Fraction(stream['width'],stream['height'])*sar/(1 if half or tagged else 2)
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as error:raise YouTubeError('Could not read the selected video’s dimensions.') from error
    dest=Path(directory)/'YouTube stereo upload.mkv'
    run_ffmpeg([binary('ffmpeg'),'-v','error','-y','-i',str(source),'-map','0:v:0','-map','0:a:0?','-c','copy','-aspect',f'{aspect.numerator}:{aspect.denominator}','-metadata:s:v:0','stereo_mode=1',str(dest)],cancel)
    check(cancel)
    probe=json.loads(subprocess.check_output([binary('ffprobe'),'-v','error','-select_streams','v:0','-show_entries','stream_tags=stereo_mode','-of','json',str(dest)],timeout=30,**quiet_options()))
    if probe.get('streams',[{}])[0].get('tags',{}).get('stereo_mode')!='left_right':raise YouTubeError('The upload copy could not be verified as left/right stereo. It has not been uploaded.')
    return dest
