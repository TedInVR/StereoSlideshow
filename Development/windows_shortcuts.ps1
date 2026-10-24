$ErrorActionPreference = 'Stop'
$root = $env:STEREO_SLIDESHOW_HOME
if (-not $root) { throw 'The installed app folder was not supplied.' }
$shell = New-Object -ComObject WScript.Shell
$places = @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))
foreach ($place in $places) {
    New-Item -ItemType Directory -Force -Path $place | Out-Null
    $shortcut = $shell.CreateShortcut((Join-Path $place 'Stereo Slideshow (Experimental).lnk'))
    $shortcut.TargetPath = Join-Path $root 'Runtime\venv\Scripts\pythonw.exe'
    $shortcut.Arguments = '"' + (Join-Path $root 'Development\windows_launch.py') + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = Join-Path $root 'Runtime\StereoSlideshow.ico'
    $shortcut.Description = 'Stereo Slideshow - experimental Windows version, untested on Windows'
    $shortcut.Save()
}
