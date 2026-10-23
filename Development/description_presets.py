"""Named reusable music descriptions, kept separately from project settings."""
import json,os,uuid
from pathlib import Path
DEFAULT_DESCRIPTIONS={
    'Nu-disco K-pop — Glossy female lead':'Nu-disco K-pop, sidechain-pumped synth layers, a sleek midtempo four-on-the-floor groove, sultry female lead with crisp phrasing and layered chorus vocals, clipped clavinet riffs over glossy bass and tight electronic drums',
    'Ska + electroswing — Spring-reverb guitar':'Ska and electroswing with spring-reverb guitar skank, a buoyant syncopated swing groove, male vocals, punchy tenor saxophone section over offbeat guitar chops and a bouncy bass line',
    'Ska + electroswing — Vintage sample crackle':'Ska and electroswing with swing-era sample crackle, electro-swing sample chops, offbeat ska guitar and punchy brass over a bouncing swung beat; upbeat midtempo feel; male vocals with a clear, playful delivery',
    'Nu-disco K-pop + electroswing — Female hooks':'Nu-disco K-pop fused with electroswing, a sleek, danceable four-on-the-floor pulse; slap electric bass, swung brass accents, and filtered disco-string loops; confident female pop vocals with crisp rhythmic phrasing and layered hooks; glossy synths and tightly polished drums',
    'J-pop — Breathy female lead':'J-pop, sleek midtempo groove, breathy female lead with playful phrasing, glossy digital reverb, muted funk guitar over crisp programmed drums and rounded synth bass',
    'Hypnotic synthwave — Arpeggios and tape warmth':'Hypnotic synthwave with an arpeggiated monosynth driving the pulse, a steady midtempo electronic groove, female vocals with sustained melodic phrasing, tape saturation and soft tape hiss',
    'Dixieland — Playful female vocal':'Dixieland, buoyant swing; clarinet runs over jaunty piano, tuba, and punchy brass; female vocal with playful phrasing; roomy brass bleed',
}
class PresetError(ValueError):pass
class DescriptionPresets:
    def __init__(self,path):self.path=Path(path)
    def load(self):
        if not self.path.exists():return dict(DEFAULT_DESCRIPTIONS)
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError) as error:raise PresetError('Could not read saved descriptions. The existing file has been kept unchanged.') from error
        if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('descriptions'),dict):raise PresetError('Saved descriptions have an unsupported format. The file has been kept unchanged.')
        result=data['descriptions']
        if any(not isinstance(name,str) or not name.strip() or not isinstance(text,str) for name,text in result.items()) or len({name.casefold() for name in result})!=len(result):raise PresetError('Saved descriptions contain invalid entries. The file has been kept unchanged.')
        return result
    def write(self,descriptions):
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_name('.'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as file:
                json.dump({'version':1,'descriptions':descriptions},file,ensure_ascii=False,indent=2);file.flush();os.fsync(file.fileno())
            temporary.replace(self.path)
        finally:temporary.unlink(missing_ok=True)
    def save(self,name,text,replace=False):
        name=name.strip()
        if not name:raise PresetError('Give this description a name.')
        if len(name)>80:raise PresetError('Use a name of 80 characters or fewer.')
        if not text.strip():raise PresetError('Type a description before saving it.')
        descriptions=self.load();existing=next((key for key in descriptions if key.casefold()==name.casefold()),None)
        if existing is not None:
            if not replace:raise PresetError('A saved description already has that name.')
            del descriptions[existing]
        descriptions[name]=text;self.write(descriptions);return name
    def remove(self,name):
        descriptions=self.load()
        if name in descriptions:del descriptions[name];self.write(descriptions)
