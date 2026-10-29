# Every porter run the GUI starts (NX2A_GUI=1) stops as one tree (D-05, D-09): on POSIX by the session gui/runner.py starts it in, on Windows by a
# Job Object porter joins itself, because PySide6 cannot start a process in a new console group (no CTRL_BREAK). The stop request is SIGTERM to the group,
# or a "stop" line on stdin on every OS (EOF too: the GUI is gone). The adb server is started first, outside both, so a cancel never takes it down.
import json, os, signal, subprocess, threading

KILL_ON_JOB_CLOSE, EXTENDED_LIMITS = 0x00002000, 9   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, JobObjectExtendedLimitInformation; never BREAKAWAY_OK (0x800)


def _term(*_): raise KeyboardInterrupt   # _with_progress closes the stage and returns 130; upstream run() terminates its own child


def setup(a, on_stop):
    """Before any command runs. Returns a line for the run log when the Windows job could not be made"""
    os.environ.update(MSBUILDDISABLENODEREUSE='1', DOTNET_CLI_USE_MSBUILD_SERVER='0', UseSharedCompilation='false')   # no MSBuild node outlives the run
    if a.cmd in ('devices', 'install') or getattr(a, 'install', False): adb_server()
    if not os.environ.get('NX2A_GUI'): return None   # a terminal's own Ctrl+C stays as it is
    job, note = None, None
    if os.name == 'nt':
        try: job = _job()
        except OSError as e: note = f'Windows job: not available ({e})'
    else: signal.signal(signal.SIGTERM, _term)
    # WR-02: the watcher keeps the stop channel and fd 0 becomes the null device, so no child (adb shell above all) inherits it and reads the stop
    fd = os.dup(0); nul = os.open(os.devnull, os.O_RDONLY); os.dup2(nul, 0); os.close(nul)
    threading.Thread(target=_watch, args=(job, on_stop, getattr(a, 'progress', None) == 'json', fd), daemon=True).start()
    return note


def adb_server():
    from porter import config, toolchain
    exe = toolchain.find_adb(config.load())
    if not exe: return
    try: subprocess.run([str(exe), 'start-server'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                        start_new_session=os.name != 'nt', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired): pass   # the first adb command reports the real problem


def _k():
    import ctypes
    from ctypes import wintypes as w
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    # without restype / argtypes 64-bit handles and GetCurrentProcess's -1 pseudo-handle are truncated to int
    k.CreateJobObjectW.restype, k.CreateJobObjectW.argtypes = w.HANDLE, [ctypes.c_void_p, w.LPCWSTR]
    k.SetInformationJobObject.restype, k.SetInformationJobObject.argtypes = w.BOOL, [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.AssignProcessToJobObject.restype, k.AssignProcessToJobObject.argtypes = w.BOOL, [w.HANDLE, w.HANDLE]
    k.GetCurrentProcess.restype, k.GetCurrentProcess.argtypes = w.HANDLE, []
    k.TerminateJobObject.restype, k.TerminateJobObject.argtypes = w.BOOL, [w.HANDLE, ctypes.c_uint]
    return k


def _job():
    """A kill-on-close job holding porter: its children join it, and it dies whole with TerminateJobObject or when porter is killed"""
    import ctypes
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', w.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', w.DWORD), ('Affinity', ctypes.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', ctypes.c_ulonglong * 6), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    k = _k()
    job = k.CreateJobObjectW(None, None)
    if not job: raise ctypes.WinError(ctypes.get_last_error())
    info = Extended(); info.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(job, EXTENDED_LIMITS, ctypes.byref(info), ctypes.sizeof(info)): raise ctypes.WinError(ctypes.get_last_error())
    if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()): raise ctypes.WinError(ctypes.get_last_error())
    return job


def _watch(job, on_stop, as_json=False, fd=0):
    """Wait for "stop" or EOF on stdin (fd: setup's copy of it). os.read on the raw fd: a daemon thread blocked in sys.stdin can abort interpreter shutdown"""
    buf = b''
    while b'stop' not in buf:
        try: chunk = os.read(fd, 64)
        except OSError: chunk = b''
        if not chunk: break
        buf += chunk
    if os.name != 'nt': os.killpg(os.getpgid(0), signal.SIGTERM); return   # the same signal the GUI's own stop sends
    on_stop()   # the stage it was in goes into the log, which is closed: nothing in porter runs after the job ends
    # the line POSIX's KeyboardInterrupt path prints (cli._with_progress): the GUI shows the same stop on Windows
    try: print(json.dumps({'ev': 'say', 'msg': '[RED] interrupted'}) if as_json else '[RED] interrupted', flush=True)
    except (OSError, ValueError): pass   # stdout gone with the GUI (EOF): the job must still end
    if job: _k().TerminateJobObject(job, 130)
    # WR-01: no job, so porter ends its own tree; once porter is gone the GUI's taskkill /T no longer finds dotnet, MSBuild or clang under it
    else: subprocess.run(['taskkill', '/T', '/F', '/PID', str(os.getpid())], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    os._exit(130)
