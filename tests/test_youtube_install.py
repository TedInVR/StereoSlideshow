"""An update adds Keychain support without recreating an existing venv."""
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Development'))
import install_support as installer
with tempfile.TemporaryDirectory() as td:
 target=Path(td)/'App';python=target/'Runtime/venv/bin/python';python.parent.mkdir(parents=True);python.touch();ready=False;commands=[]
 def runtime_ok(path,full=True):return Path(path)==python and (ready or not full)
 def run(command,**kwargs):
  global ready
  commands.append(command);ready=True
 with patch.object(installer,'runtime_ok',runtime_ok),patch.object(installer.subprocess,'run',run):installer.ensure_runtime(target,Path(td))
 assert len(commands)==1 and commands[0][:4]==[str(python),'-m','pip','install'] and commands[0][-1].endswith('requirements.txt') and python.exists()
print('Existing runtime gains new dependencies through pip, without venv recreation or loss of the permanent executable.')
