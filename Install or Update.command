#!/bin/bash
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PACKAGE="$(cd "$(dirname "$0")" && pwd)"
trap 'echo; echo "Installation stopped. Please copy the error above into our chat."; read -r -p "Press Return to close."' ERR
PYTHON=""
for candidate in "$PACKAGE/Runtime/venv/bin/python" "/Applications/Stereo Slideshow/Runtime/venv/bin/python" "$HOME/Applications/Stereo Slideshow/Runtime/venv/bin/python" "$HOME/Library/Application Support/Stereo Slideshow/venv/bin/python" "$(command -v python3 || true)" /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 /opt/homebrew/opt/python@3.*/bin/python3.* /usr/bin/python3; do
 if [ -x "$candidate" ] && "$candidate" -c 'import sys,venv;sys.exit(0 if (3,9)<=sys.version_info[:2]<(3,15) else 1)' >/dev/null 2>&1; then PYTHON="$candidate";break;fi
done
if [ -z "$PYTHON" ]; then
 echo 'No working Python 3.9–3.14 was found. Please share this message for help.'
 read -r -p 'Press Return to close.';exit 1
fi
"$PYTHON" "$PACKAGE/Development/install_support.py" --package "$PACKAGE"
