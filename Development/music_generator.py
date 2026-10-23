"""Local ACE-Step REST integration and exact-length soundtrack assembly."""
import json, math, os, platform, shutil, signal, subprocess, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path
from engine import binary,music_duration

ERAS=['Any era','1920s','1930s','1940s','1950s','1960s','1970s','1980s','1990s','2000s','Modern']
GENRES=['Use description only','Pop','Jazz','Rock and roll','Swing / big band','Blues','Country','Folk / acoustic','Classical / chamber','Orchestral film score','Ambient','Electronic / synthwave','Soul / funk','Latin / bossa nova','Ragtime','Surf rock','Music box / fairground','Barbershop harmony']
MOODS=['Warm and nostalgic','Happy and upbeat','Peaceful and reflective','Romantic','Playful','Dramatic and cinematic','Mysterious','Adventurous']
class MusicError(RuntimeError):pass
class MusicCancelled(Exception):pass

STYLE_KEYS=('era','genre','mood','details','music_mode','voice','language','topic','lyrics')
VOICES=['No preference','Male lead','Female lead','Male and female duet','Group / choir']
LANGUAGES={'English':'en','Spanish':'es','French':'fr','German':'de','Italian':'it','Portuguese':'pt','Japanese':'ja','Korean':'ko','Chinese (Mandarin)':'zh','Hindi':'hi'}

def make_prompt(era,genre,mood,details='',mode='instrumental',voice='No preference'):
    period='timeless' if era=='Any era' else era+'-inspired'
    if mode!='instrumental':genre=genre.replace('-inspired instrumental',' harmony')
    genre='' if genre=='Use description only' else genre
    vocal='Instrumental soundtrack, no vocals, no singing, no speech.' if mode=='instrumental' else 'A song with clearly sung lyrics. '+({'Male lead':'Male lead vocals.','Female lead':'Female lead vocals.','Male and female duet':'Male and female duet vocals.','Group / choir':'Group vocals and choir harmonies.'}.get(voice,''))
    style=' '.join(part for part in [period,genre.lower()] if part)
    return f'{style}. {mood.lower()}. {vocal} A clear melody, balanced arrangement, musical opening and a resolving ending. '+details.strip()

def validate_music_options(options,seconds):
    mode=options.get('music_mode','instrumental')
    if mode not in ('instrumental','topic','lyrics'):raise MusicError('Choose Instrumental, Write a song about a topic, or Use my lyrics.')
    if mode!='instrumental' and seconds>600:raise MusicError('Vocal songs support up to ten minutes in this version. Shorten the slideshow or choose Instrumental for a longer soundtrack.')
    if mode=='topic' and not options.get('topic','').strip():raise MusicError('Enter a subject for the song.')
    if mode=='lyrics' and not options.get('lyrics','').strip():raise MusicError('Enter your lyrics before generating a song.')
    if options.get('language','English') not in LANGUAGES:raise MusicError('Choose a supported vocal language.')

def generation_request(options,seconds):
    validate_music_options(options,seconds);mode=options.get('music_mode','instrumental')
    prompt=make_prompt(options['era'],options['genre'],options['mood'],options.get('details',''),mode,options.get('voice','No preference'))
    payload=dict(prompt=prompt,lyrics='[Instrumental]' if mode=='instrumental' else options.get('lyrics','') if mode=='lyrics' else '',audio_duration=seconds,audio_format='wav',batch_size=1,use_random_seed=True,thinking=mode=='topic',use_cot_caption=False,use_cot_language=False,task_type='text2music',use_format=False)
    if mode!='instrumental':payload['vocal_language']=LANGUAGES[options.get('language','English')]
    if mode=='topic':
        payload.update(sample_mode=True,sample_query=f"Write and sing a {seconds:g}-second song in {options.get('language','English')} about: {options['topic'].strip()}. Style: {prompt} Write concise original lyrics that fit this duration, with a complete ending. Singing is required.")
    return payload

def section_lengths(seconds):
    if not math.isfinite(seconds) or seconds<=0:raise MusicError('The slideshow needs a positive duration.')
    n=max(1,math.ceil((seconds-2)/598))
    return [max(10,(seconds+2*(n-1))/n)]*n

def local_url(url):
    parsed=urllib.parse.urlsplit(url.strip())
    if parsed.scheme!='http' or parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise MusicError('Use a local address such as http://127.0.0.1:8001.')
    try:parsed.port
    except ValueError:raise MusicError('The local server port is not valid.')
    return url.strip().rstrip('/')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class AceClient:
    def __init__(self,url,token=''):
        self.url=local_url(url);self.token=token;self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def open(self,path,payload=None):
        url=urllib.parse.urljoin(self.url+'/',path)
        if urllib.parse.urlsplit(url).netloc!=urllib.parse.urlsplit(self.url).netloc:raise MusicError('The music server returned an unexpected download address.')
        headers={'Content-Type':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        try:return self.opener.open(request,timeout=8)
        except urllib.error.HTTPError as e:
            if e.code in (401,403):raise MusicError('ACE-Step requires an API key. Enter it in Generator setup.') from e
            raise MusicError(f'ACE-Step returned HTTP {e.code}. Check that this is the REST API server, not its browser interface.') from e
        except (OSError,urllib.error.URLError) as e:raise MusicError('Cannot reach the local ACE-Step API. Choose its installed folder in Generator setup, or start its API server.') from e
    def request(self,path,payload=None):
        with self.open(path,payload) as response:
            try:data=json.load(response)
            except ValueError:raise MusicError('The selected server did not return an ACE-Step API response.')
        if not isinstance(data,dict):raise MusicError('Unexpected ACE-Step response.')
        if data.get('error') or data.get('code',200)!=200:raise MusicError(str(data.get('error') or 'Music generation failed.')[:350])
        return data.get('data',data)
    def health(self):
        result=self.request('/health')
        if not isinstance(result,dict) or result.get('service')!='ACE-Step API' or result.get('status')!='ok':raise MusicError('This address is not an ACE-Step REST API server.')
    def generate(self,prompt,seconds,cancel,status,payload=None,result_info=None):
        check_cancel(cancel)
        submitted=self.request('/release_task',payload if payload is not None else dict(prompt=prompt,lyrics='[Instrumental]',audio_duration=seconds,audio_format='wav',batch_size=1,use_random_seed=True,thinking=False,use_cot_caption=False,use_cot_language=False,task_type='text2music'))
        task=submitted.get('task_id') if isinstance(submitted,dict) else None
        if not task:raise MusicError('ACE-Step did not return a generation task ID.')
        started=time.monotonic()
        while True:
            check_cancel(cancel)
            if time.monotonic()-started>7200:raise MusicError('Music generation exceeded two hours. Check the ACE-Step log before retrying.')
            rows=self.request('/query_result',{'task_id_list':[task]})
            for row in rows if isinstance(rows,list) else []:
                if row.get('task_id')!=task:continue
                if row.get('status')==2:
                    if payload and payload.get('sample_mode'):raise MusicError('ACE-Step could not write or generate this song. Topic mode needs its language model loaded. Check Logs/music_generator_server.log; supplying your own lyrics does not require the lyric-writing model.')
                    raise MusicError('ACE-Step could not generate this selection. Try a shorter slideshow or check its log.')
                if row.get('status')==1:
                    result=row.get('result',[])
                    try:result=json.loads(result) if isinstance(result,str) else result
                    except ValueError:raise MusicError('ACE-Step returned an unreadable music result.')
                    if not isinstance(result,list) or not result or not result[0].get('file'):raise MusicError('ACE-Step finished without an audio file.')
                    if result_info is not None:result_info.append(result[0])
                    return result[0]['file']
            status(f'Creating music… {int(time.monotonic()-started)} seconds elapsed')
            if cancel.wait(2):raise MusicCancelled()
    def download(self,url,path,cancel):
        with self.open(url) as source,Path(path).open('wb') as dest:
            while True:
                check_cancel(cancel);block=source.read(65536)
                if not block:break
                dest.write(block)

def check_cancel(cancel):
    if cancel.is_set():raise MusicCancelled()

def find_installation():
    home=Path.home()
    for parent in [home/'Applications',Path('/Applications'),home/'Downloads',home/'Documents',home/'AI',home]:
        if not parent.is_dir():continue
        for folder in sorted(parent.glob('*')):
            if not folder.is_dir() or not any(t in folder.name.lower() for t in ('ace-step','acestep','a-step')):continue
            for root in [folder,folder/'Development',folder/'ACE-Step-1.5']:
                if (root/'acestep/api_server.py').is_file():return str(root)
    return ''

def launch_command(folder,port):
    root=Path(folder).expanduser().resolve()
    if not (root/'acestep/api_server.py').is_file():raise MusicError('Choose the ACE-Step project folder containing acestep/api_server.py. This installation may need an ACE-Step update to support its REST API.')
    args=['--host','127.0.0.1','--port',str(port)]
    # Portable ACE-Step distributions use both spellings. A copied .venv
    # may contain dangling links to the packager's machine; is_file skips them.
    candidates=['.venv/bin/python','.venv/bin/python3','venv/bin/python']
    for directory in ['python_embeded','python_embedded']:
        candidates.extend(f'{directory}/bin/{name}' for name in ['python3.11','python3','python'])
    for relative in candidates:
        python=root/relative
        if python.is_file() and os.access(python,os.X_OK):return root,[str(python),'-m','acestep.api_server']+args
    uv=shutil.which('uv')
    for candidate in [Path.home()/'.local/bin/uv',Path.home()/'.cargo/bin/uv',Path('/opt/homebrew/bin/uv')]:
        if not uv and candidate.is_file():uv=str(candidate)
    if uv:return root,[uv,'run','--offline','acestep-api']+args
    raise MusicError('The installed ACE-Step Python environment was not found. Open its existing launcher once to finish setup, then choose its project folder here.')

class LocalServer:
    def __init__(self):self.process=None;self.log=None
    def ensure(self,client,folder,logs,cancel,status,need_lm=False):
        try:client.health();return
        except MusicError:
            if not folder:raise
        parsed=urllib.parse.urlsplit(client.url)
        if parsed.hostname not in ('127.0.0.1','localhost'):raise MusicError('Automatic startup uses localhost or 127.0.0.1.')
        root,command=launch_command(folder,parsed.port or 80)
        logs.mkdir(parents=True,exist_ok=True);self.log=(logs/'music_generator_server.log').open('ab')
        env=os.environ.copy();env['TOKENIZERS_PARALLELISM']='false'
        if need_lm:env['ACESTEP_INIT_LLM']='true'
        if platform.system()=='Darwin' and platform.machine()=='arm64':env['ACESTEP_LM_BACKEND']='mlx'
        self.process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            check_cancel(cancel)
            if self.process.poll() is not None:raise MusicError('ACE-Step stopped during startup. See Logs/music_generator_server.log. Its installation or dependencies may need updating.')
            try:client.health();return
            except MusicError:pass
            status('Starting the local music engine and loading its models…')
            if cancel.wait(2):raise MusicCancelled()
        raise MusicError('ACE-Step did not become ready within 15 minutes. See Logs/music_generator_server.log.')
    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:os.killpg(self.process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:self.process.wait(5)
            except subprocess.TimeoutExpired:
                try:os.killpg(self.process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                self.process.wait()
        if self.log:self.log.close()

def run_ffmpeg(command,cancel):
    import tempfile
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
        try:
            while process.poll() is None:
                if cancel.wait(.1):raise MusicCancelled()
            if process.returncode:
                errors.seek(0);raise MusicError('Could not prepare the generated soundtrack. '+errors.read().decode(errors='replace')[-400:])
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(2)
                except subprocess.TimeoutExpired:process.kill();process.wait()

def assemble(files,seconds,output,cancel,repeat=True):
    # Normalize each model result to its requested length before joining; a short
    # model result is repeated rather than adding an unexpectedly silent tail.
    requests=section_lengths(seconds);command=[binary('ffmpeg'),'-hide_banner','-loglevel','error','-y']
    for path in files:
        if not repeat and music_duration(path,cancel)+.25<seconds:raise MusicError('ACE-Step returned a song shorter than the slideshow. Try another take; vocal songs are not looped to repeat their lyrics.')
        command+=(['-stream_loop','-1'] if repeat else [])+['-i',str(path)]
    graph=[]
    for i,length in enumerate(requests):graph.append(f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={length:.9f},asetpts=PTS-STARTPTS[a{i}]')
    label='a0'
    for i in range(1,len(files)):
        out=f'join{i}';graph.append(f'[{label}][a{i}]acrossfade=d=2:c1=tri:c2=tri[{out}]');label=out
    samples=round(seconds*48000);graph.append(f'[{label}]atrim=end_sample={samples},asetpts=PTS-STARTPTS[final]')
    command+=['-filter_complex',';'.join(graph),'-map','[final]','-c:a','pcm_s24le',str(output)]
    run_ffmpeg(command,cancel)

def generate_soundtrack(options,seconds,output,cancel,status):
    import tempfile
    validate_music_options(options,seconds)
    client=AceClient(options.get('url','http://127.0.0.1:8001'),options.get('token',''));server=LocalServer();output=Path(output)
    try:
        mode=options.get('music_mode','instrumental');result_info=[]
        server.ensure(client,options.get('folder',''),Path(options['logs']),cancel,status,need_lm=mode=='topic')
        prompt=make_prompt(options['era'],options['genre'],options['mood'],options.get('details',''),mode,options.get('voice','No preference'))
        with tempfile.TemporaryDirectory(prefix='stereo-music-') as temp:
            files=[];lengths=section_lengths(seconds)
            for i,length in enumerate(lengths):
                def update(text):status(f'Section {i+1} of {len(lengths)} — '+text)
                update('Requesting new music…');url=client.generate(prompt,length,cancel,update,payload=generation_request(options,length),result_info=result_info)
                path=Path(temp)/f'section{i}.wav';client.download(url,path,cancel);files.append(path)
            check_cancel(cancel);status('Matching the soundtrack to the slideshow length…');output.parent.mkdir(parents=True,exist_ok=True)
            pending=output.with_name(output.stem+'.partial.wav')
            try:assemble(files,seconds,pending,cancel,repeat=mode=='instrumental');check_cancel(cancel);pending.replace(output)
            finally:pending.unlink(missing_ok=True)
        output.with_suffix('.json').write_text(json.dumps(dict(prompt=prompt,requested_seconds=seconds,sections=len(lengths),mode=mode,voice=options.get('voice','No preference'),language=options.get('language','English'),topic=options.get('topic','') if mode=='topic' else '',lyrics=(result_info[0].get('lyrics','') if result_info else '') or (options.get('lyrics','') if mode=='lyrics' else ''),engine='ACE-Step 1.5',created=time.strftime('%Y-%m-%d %H:%M:%S')),indent=2))
        return str(output)
    finally:server.stop()
