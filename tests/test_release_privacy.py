"""Release packaging excludes local account files even outside Settings."""
import json,runpy,shutil,tempfile,zipfile
from pathlib import Path
script=Path(__file__).resolve().parents[1]/'tools/package_release.py'
with tempfile.TemporaryDirectory() as td:
 root=Path(td)/'App';(root/'tools').mkdir(parents=True);(root/'Development/nested').mkdir(parents=True);(root/'Settings').mkdir()
 shutil.copyfile(script,root/'tools/package_release.py');(root/'project.json').write_text('{"version":"test"}');(root/'Development/public.py').write_text('print("public")')
 for name in ['client_secret_download.json','youtube_client.json','token.json','tokens.json','credentials.json','youtube_upload_history.json','youtube_setup.json']:(root/'Development/nested'/name).write_text('{"private":"do not release"}')
 (root/'Settings/account.json').write_text('{"private":"do not release"}')
 runpy.run_path(str(root/'tools/package_release.py'))
 with zipfile.ZipFile(Path(td)/'Stereo_Slideshow_Update_vtest.zip') as z:
  names=z.namelist();assert any(name.endswith('public.py') for name in names);assert not any('nested/' in name or '/Settings/' in name for name in names)
  assert not any(b'do not release' in z.read(name) for name in names)
print('Release excludes personal configuration, tokens, upload history and guide progress, including private filenames outside Settings.')
