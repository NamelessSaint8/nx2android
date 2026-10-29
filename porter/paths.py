# Where things are: the repository (and the nxnative subtree in it), the player's own folder (settings, the APK signing key).
# When frozen the bundle's resource root is read-only (a signed .app, a DMG, Program Files): the port builds from a copy of its engine in the player's folder.
import os, shutil, stat, sys
from pathlib import Path

FROZEN = getattr(sys, 'frozen', False)
if FROZEN and sys.platform == 'darwin': REPO = Path(sys.executable).parent.parent / 'Resources'   # inside a .app the data files are in Contents/Resources
elif FROZEN: REPO = Path(sys.executable).parent   # the bundle: nxnative/ beside nx2android.exe
else: REPO = Path(__file__).resolve().parent.parent
LOCAL_TOOLS = REPO / 'tools'   # a developer's toolchains next to the repository (not committed); the player installs their own


def user_dir():
    """The player's nx2android folder: %APPDATA%\\nx2android on Windows, ~/Library/Application Support/nx2android on a Mac, ~/.config/nx2android elsewhere.
    NX2A_HOME overrides it (tests)"""
    if os.environ.get('NX2A_HOME'): d = Path(os.environ['NX2A_HOME'])
    elif os.name == 'nt': d = Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / 'nx2android'
    elif sys.platform == 'darwin': d = Path.home() / 'Library/Application Support/nx2android'
    else: d = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'nx2android'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _engine():
    """The engine a frozen port builds from: <user dir>/engine/<ENGINE id>/nxnative, a writable copy of the bundle's nxnative/ made on first use
    (dotnet build writes obj/ into the engine's projects, and nothing may be written into the bundle)"""
    try: eid = (REPO / 'ENGINE').read_text(encoding='utf-8').strip()
    except OSError: eid = ''
    if not eid.isalnum(): return REPO / 'nxnative'   # a bundle built before the copy existed
    base = user_dir() / 'engine'; dst = base / eid
    if (dst / 'nxnative').is_dir(): return dst / 'nxnative'
    tmp = base / f'{eid}.tmp-{os.getpid()}'   # copy aside, then one rename: a racing porter (the GUI starts three at once) never sees half a copy
    shutil.copytree(REPO / 'nxnative', tmp / 'nxnative', symlinks=True)
    for root, dirs, files in os.walk(tmp):   # copystat carries a DMG's or a chmod a-w bundle's read-only modes: dotnet could not create obj/ there
        for n in dirs + files:
            p = os.path.join(root, n)
            if not os.path.islink(p): os.chmod(p, os.stat(p).st_mode | stat.S_IWUSR)
    try: os.rename(tmp, dst)
    except OSError:
        if not (dst / 'nxnative').is_dir(): raise
        shutil.rmtree(tmp, ignore_errors=True)   # another porter got there first
    return dst / 'nxnative'


NXNATIVE = _engine() if FROZEN else REPO / 'nxnative'
DM = NXNATIVE / 'dm'


def player_tools():   # the toolchains `porter tools --download` fetched for the player: android-ndk-r27c/, dotnet/, platform-tools/
    return user_dir() / 'toolchains'


def signing_key():   # one key per player: every app they port keeps its signer, so a new port installs over the last one
    return user_dir() / 'signing-key.json'
