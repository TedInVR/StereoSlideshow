"""Register the user's background updater; no administrator service or credentials."""
import datetime,getpass,json,os,plistlib,subprocess,sys,threading,traceback
from pathlib import Path
from platform_support import runtime_python,quiet_options
LABEL='com.ted.stereoslideshow.automaticupdates'
INTERVAL=900

def enabled(root):
    try:return json.loads((Path(root)/'Settings/automatic_updates.json').read_text()).get('enabled',True) is True
    except FileNotFoundError:return True
    except (OSError,ValueError):return False

def set_enabled(root,value):
    path=Path(root)/'Settings/automatic_updates.json';path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(dict(enabled=bool(value))));os.replace(temporary,path)

def agent_plist(root):
    root=Path(root)
    return dict(Label=LABEL,ProgramArguments=[str(runtime_python(root)),str(root/'Development/background_update.py'),'--root',str(root)],RunAtLoad=True,StartInterval=INTERVAL,ProcessType='Background',StandardOutPath=str(root/'Logs/automatic_updates.log'),StandardErrorPath=str(root/'Logs/automatic_updates.log'))

def windows_task_xml(root):
    import xml.etree.ElementTree as E
    root=Path(root);ns='http://schemas.microsoft.com/windows/2004/02/mit/task';E.register_namespace('',ns)
    def node(parent,name,text=None,**attrs):
        child=E.SubElement(parent,'{'+ns+'}'+name,attrs)
        if text is not None:child.text=text
        return child
    task=E.Element('{'+ns+'}Task',{'version':'1.2'})
    registration=node(task,'RegistrationInfo');node(registration,'Description','Stereo Slideshow automatic updates while the app is closed. Experimental Windows edition.')
    triggers=node(task,'Triggers');trigger=node(triggers,'TimeTrigger');repeat=node(trigger,'Repetition');node(repeat,'Interval','PT15M');node(repeat,'StopAtDurationEnd','false')
    node(trigger,'StartBoundary',(datetime.datetime.now()+datetime.timedelta(minutes=1)).replace(microsecond=0).isoformat());node(trigger,'Enabled','true')
    principals=node(task,'Principals');principal=node(principals,'Principal',id='Author')
    user=getpass.getuser();domain=os.environ.get('USERDOMAIN');node(principal,'UserId',(domain+'\\' if domain else '')+user);node(principal,'LogonType','InteractiveToken');node(principal,'RunLevel','LeastPrivilege')
    settings=node(task,'Settings')
    for key,value in [('MultipleInstancesPolicy','IgnoreNew'),('DisallowStartIfOnBatteries','false'),('StopIfGoingOnBatteries','false'),('StartWhenAvailable','true'),('Enabled','true'),('ExecutionTimeLimit','PT0S')]:node(settings,key,value)
    actions=node(task,'Actions',Context='Author');execute=node(actions,'Exec');node(execute,'Command',str(runtime_python(root,True)));node(execute,'Arguments',subprocess.list2cmdline([str(root/'Development/background_update.py'),'--root',str(root)]))
    return E.tostring(task,encoding='utf-16',xml_declaration=True)

def register(root):
    root=Path(root);(root/'Logs').mkdir(parents=True,exist_ok=True)
    if sys.platform=='darwin':
        agent=Path.home()/'Library/LaunchAgents'/(LABEL+'.plist');domain='gui/'+str(os.getuid())
        if not enabled(root):
            subprocess.run(['/bin/launchctl','bootout',domain+'/'+LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
            agent.unlink(missing_ok=True);return
        agent.parent.mkdir(parents=True,exist_ok=True);data=plistlib.dumps(agent_plist(root));same=agent.exists() and agent.read_bytes()==data
        loaded=subprocess.run(['/bin/launchctl','print',domain+'/'+LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20).returncode==0
        if same and loaded:return
        if loaded:subprocess.run(['/bin/launchctl','bootout',domain+'/'+LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
        temporary=agent.with_suffix('.tmp');temporary.write_bytes(data);os.replace(temporary,agent)
        subprocess.run(['/bin/launchctl','bootstrap',domain,str(agent)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20)
    elif sys.platform=='win32':
        task=root/'Runtime/automatic_update_task.xml';task.parent.mkdir(parents=True,exist_ok=True)
        if not enabled(root):
            subprocess.run(['schtasks.exe','/Delete','/TN',LABEL,'/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,**quiet_options());return
        # A saved registration avoids resetting the repetition trigger on every launch.
        marker=root/'Runtime/automatic_update_registered.json'
        try:registered=json.loads(marker.read_text()).get('root')==str(root)
        except (OSError,ValueError):registered=False
        if registered and subprocess.run(['schtasks.exe','/Query','/TN',LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,**quiet_options()).returncode==0:return
        task.write_bytes(windows_task_xml(root))
        subprocess.run(['schtasks.exe','/Create','/TN',LABEL,'/XML',str(task),'/F'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20,**quiet_options())
        marker.write_text(json.dumps(dict(root=str(root))))

def register_in_background(root):
    def work():
        try:register(root)
        except Exception:
            path=Path(root)/'Logs/automatic_updates.log';path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a') as log:traceback.print_exc(file=log)
    thread=threading.Thread(target=work,daemon=True);thread.start();return thread
