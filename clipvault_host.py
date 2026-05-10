#!/usr/bin/env python3
"""
ClipVault Native Messaging Host
Bridges the Chrome/Firefox extension to the local yt-dlp binary.

Protocol: Chrome native messaging (length-prefixed JSON)
https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import traceback

# Debug logging: write to a log file in the same directory as this script
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clipvault_host.log")

def _log(msg):
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{os.getpid()}] {msg}\n")
            f.flush()
    except Exception:
        pass

_log("=== Native host started ===")
_log(f"Python: {sys.executable}")
_log(f"Platform: {sys.platform}")
_log(f"argv: {sys.argv}")
_log(f"CWD: {os.getcwd()}")
_log(f"PATH (first 500 chars): {os.environ.get('PATH', 'NOT SET')[:500]}")


def find_yt_dlp():
    """Find yt-dlp binary in PATH or common locations.

    Returns (path, search_log) where search_log is a list of diagnostic strings.
    """
    search_log = []
    _log("find_yt_dlp: starting search...")

    # Helper to log and test a candidate
    def test(candidate, source):
        search_log.append(f"  [{source}] {candidate}")
        if sys.platform == "win32":
            # On Windows, .exe files are executable by extension.
            # os.access(..., os.X_OK) can incorrectly return False for
            # pip-installed wrappers, so we use os.path.isfile() only.
            if candidate.lower().endswith(".exe"):
                if os.path.isfile(candidate):
                    search_log.append(f"  -> FOUND: {candidate}")
                    _log(f"find_yt_dlp: FOUND at {candidate}")
                    return candidate
            else:
                # Try .exe variant first
                candidate_exe = candidate + ".exe"
                if os.path.isfile(candidate_exe):
                    search_log.append(f"  -> FOUND: {candidate_exe}")
                    _log(f"find_yt_dlp: FOUND at {candidate_exe}")
                    return candidate_exe
                # Then plain name with access check
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    search_log.append(f"  -> FOUND: {candidate}")
                    _log(f"find_yt_dlp: FOUND at {candidate}")
                    return candidate
        else:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                search_log.append(f"  -> FOUND: {candidate}")
                _log(f"find_yt_dlp: FOUND at {candidate}")
                return candidate
        return None

    # 1. Try user's actual shell PATH first
    search_log.append("Step 1: querying shell PATH...")
    shell_path, shell_err = _get_shell_path()
    if shell_path:
        search_log.append(f"  shell PATH = {shell_path[:200]}...")
        for directory in shell_path.split(os.pathsep):
            directory = directory.strip()
            if not directory:
                continue
            result = test(os.path.join(directory, "yt-dlp"), "shell PATH")
            if result:
                return result, search_log
    else:
        search_log.append(f"  shell PATH unavailable: {shell_err or 'unknown reason'}")

    # 2. Fallback: shutil.which with default (minimal) PATH
    search_log.append("Step 2: shutil.which('yt-dlp')...")
    path = shutil.which("yt-dlp")
    if path:
        search_log.append(f"  -> FOUND: {path}")
        _log(f"find_yt_dlp: FOUND via shutil.which at {path}")
        return path, search_log
    search_log.append("  not found via shutil.which")

    # 3. macOS-specific fallbacks
    if sys.platform == "darwin":
        search_log.append("Step 3: macOS fallback locations...")
        mac_candidates = [
            "/usr/local/bin/yt-dlp",
            "/opt/homebrew/bin/yt-dlp",
            os.path.expanduser("~/.local/bin/yt-dlp"),
            os.path.expanduser("~/bin/yt-dlp"),
            "/usr/bin/yt-dlp",
            "/opt/local/bin/yt-dlp",          # MacPorts
            "/opt/pkg/bin/yt-dlp",            # pkgsrc
            os.path.expanduser("~/Library/Python/3.9/bin/yt-dlp"),
            os.path.expanduser("~/Library/Python/3.10/bin/yt-dlp"),
            os.path.expanduser("~/Library/Python/3.11/bin/yt-dlp"),
            os.path.expanduser("~/Library/Python/3.12/bin/yt-dlp"),
            os.path.expanduser("~/Library/Python/3.13/bin/yt-dlp"),
        ]
        try:
            import glob
            pip_user_bins = glob.glob(os.path.expanduser("~/Library/Python/*/bin/yt-dlp"))
            mac_candidates.extend(pip_user_bins)
        except Exception:
            pass
        for c in mac_candidates:
            result = test(c, "macOS fallback")
            if result:
                return result, search_log

    # 4. Linux-specific fallbacks
    if sys.platform.startswith("linux"):
        search_log.append("Step 4: Linux fallback locations...")
        linux_candidates = [
            os.path.expanduser("~/.local/bin/yt-dlp"),
            os.path.expanduser("~/bin/yt-dlp"),
            "/usr/local/bin/yt-dlp",
            "/usr/bin/yt-dlp",
            "/bin/yt-dlp",
            "/snap/bin/yt-dlp",
            os.path.expanduser("~/.yt-dlp/yt-dlp"),
            os.path.expanduser("~/.config/yt-dlp/yt-dlp"),
        ]
        for c in linux_candidates:
            result = test(c, "Linux fallback")
            if result:
                return result, search_log

    # 5. Windows-specific fallbacks
    if sys.platform == "win32":
        search_log.append("Step 5: Windows fallback locations...")
        import glob
        win_candidates = [
            r"C:\yt-dlp\yt-dlp.exe",
            r"C:\Users\%USERNAME%\yt-dlp.exe",
            r"C:\yt-dlp.exe",
            # User-specific known locations (from install.py diagnostics)
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%APPDATA%\Python\Python310\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%APPDATA%\Python\Python311\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%APPDATA%\Python\Python312\Scripts\yt-dlp.exe"),
        ]
        # Scan common Python Scripts folders
        python_roots = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
            os.path.expandvars(r"%APPDATA%\Python"),
            r"C:\Python",
            r"C:\Program Files\Python",
            r"C:\Program Files (x86)\Python",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps"),
        ]
        for root in python_roots:
            if not os.path.isdir(root):
                search_log.append(f"  [skip] dir not found: {root}")
                continue
            for scripts_dir in glob.glob(os.path.join(root, "*", "Scripts")):
                result = test(os.path.join(scripts_dir, "yt-dlp.exe"), "Windows Python Scripts")
                if result:
                    return result, search_log

        # pip user install on Windows
        user_scripts_patterns = [
            os.path.expandvars(r"%APPDATA%\Python\Python*\Scripts"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python*\Scripts"),
        ]
        for pattern in user_scripts_patterns:
            for scripts_dir in glob.glob(pattern):
                result = test(os.path.join(scripts_dir, "yt-dlp.exe"), "Windows pip user")
                if result:
                    return result, search_log

        # Check common standalone locations
        home = os.path.expanduser("~")
        for c in win_candidates:
            c_expanded = os.path.expandvars(c)
            result = test(c_expanded, "Windows standalone")
            if result:
                return result, search_log
            # Also check in home
            home_candidate = os.path.join(home, os.path.basename(c_expanded))
            result = test(home_candidate, "Windows home")
            if result:
                return result, search_log

    search_log.append("Step 6: Exhausted all search locations. yt-dlp not found.")
    _log(f"find_yt_dlp: NOT FOUND. Log has {len(search_log)} entries.")
    return None, search_log


def _get_shell_path():
    """
    Try to retrieve the user's actual shell PATH.
    Returns (path_string, error_string).  path_string may be None.
    """
    errors = []

    # On Windows, the native host inherits Chrome's env which already has
    # the full system+user PATH. Try it first — it's the fastest and most reliable.
    if sys.platform == "win32":
        env_path = os.environ.get("PATH", "")
        if env_path:
            return env_path, None
        errors.append("os.environ PATH is empty on Windows")

    # Attempt 1: run the login shell
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        result = subprocess.run(
            [shell, "-l", "-c", "echo $PATH"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                return path, None
            errors.append("login shell returned empty PATH")
        else:
            errors.append(f"login shell exited {result.returncode}: {result.stderr.strip()[:100]}")
    except Exception as e:
        errors.append(f"login shell failed: {type(e).__name__}: {str(e)[:100]}")

    # Attempt 2: run shell without -l (some shells don't support -l)
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        result = subprocess.run(
            [shell, "-c", "echo $PATH"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                return path, None
            errors.append("shell -c returned empty PATH")
        else:
            errors.append(f"shell -c exited {result.returncode}: {result.stderr.strip()[:100]}")
    except Exception as e:
        errors.append(f"shell -c failed: {type(e).__name__}: {str(e)[:100]}")

    # Attempt 3: on macOS, read common shell config files directly
    if sys.platform == "darwin":
        try:
            home = os.path.expanduser("~")
            for rc_file in [".zshrc", ".bash_profile", ".bashrc", ".profile"]:
                rc_path = os.path.join(home, rc_file)
                if os.path.isfile(rc_path):
                    with open(rc_path, "r") as f:
                        content = f.read()
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("export PATH=") or line.startswith("PATH="):
                            # Extract PATH value
                            eq = line.find("=")
                            if eq > 0:
                                val = line[eq + 1:].strip().strip('"').strip("'")
                                if val:
                                    return val, None
            errors.append("no PATH export found in shell rc files")
        except Exception as e:
            errors.append(f"rc file read failed: {type(e).__name__}: {str(e)[:100]}")

    # Attempt 4: on Windows, read registry PATH and expand env vars
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                path_raw, _ = winreg.QueryValueEx(key, "Path")
                if path_raw:
                    # Expand %USERPROFILE%, %APPDATA%, etc.
                    path = winreg.ExpandEnvironmentStrings(path_raw)
                    if path:
                        return path, None
            errors.append("HKCU Environment Path empty")
        except Exception as e:
            errors.append(f"HKCU registry failed: {type(e).__name__}: {str(e)[:100]}")
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                path_raw, _ = winreg.QueryValueEx(key, "Path")
                if path_raw:
                    path = winreg.ExpandEnvironmentStrings(path_raw)
                    if path:
                        return path, None
            errors.append("HKLM Environment Path empty")
        except Exception as e:
            errors.append(f"HKLM registry failed: {type(e).__name__}: {str(e)[:100]}")

    return None, "; ".join(errors)


def send_message(msg):
    """Send a JSON message to the browser via stdout."""
    _log(f"SEND: {msg.get('type', msg)}")
    data = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def read_message():
    """Read a length-prefixed JSON message from stdin."""
    _log("read_message: waiting for 4-byte length...")
    raw = sys.stdin.buffer.read(4)
    if not raw:
        _log("read_message: stdin closed (no data)")
        return None
    size = struct.unpack("=I", raw)[0]
    _log(f"read_message: expecting {size} bytes")
    data = sys.stdin.buffer.read(size).decode("utf-8")
    msg = json.loads(data)
    _log(f"RECV: {msg.get('action', msg)}")
    return msg


def run_yt_dlp(payload):
    """Run yt-dlp with the given payload and stream progress."""
    yt_dlp_path, search_log = find_yt_dlp()
    if not yt_dlp_path:
        send_message({
            "type": "error",
            "error": "yt-dlp not found",
            "message": "yt-dlp is not installed or not in your PATH. Install it with: pip install yt-dlp",
            "searchLog": search_log,
        })
        return

    url = payload.get("url")
    format_id = payload.get("formatId", "best")
    title = payload.get("title", "download")
    is_hls = payload.get("isHls", False)
    cookies = payload.get("cookies", "")

    # Determine output path
    download_dir = os.path.expanduser("~/Downloads")
    if sys.platform == "win32":
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(download_dir):
        download_dir = os.path.expanduser("~")

    output_template = os.path.join(download_dir, "%(title)s [%(height)sp].%(ext)s")

    cmd = [yt_dlp_path, url, "-f", format_id, "-o", output_template]

    # Add progress output
    cmd += ["--newline", "--progress"]

    # Handle cookies if provided
    if cookies:
        cookies_path = os.path.join(os.path.expanduser("~"), ".clipvault_cookies.txt")
        with open(cookies_path, "w") as f:
            f.write(cookies)
        cmd += ["--cookies", cookies_path]

    # HLS-specific optimizations
    if is_hls:
        cmd += ["--concurrent-fragments", "4"]

    send_message({
        "type": "started",
        "message": f"Starting download with yt-dlp...",
        "ytDlpPath": yt_dlp_path,
    })

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue

            # Parse progress lines like:
            # [download]  12.3% of ~45.67MiB at  2.34MiB/s ETA 00:15
            if "[download]" in line and "%" in line:
                try:
                    parts = line.split()
                    percent = parts[1].rstrip("%")
                    send_message({
                        "type": "progress",
                        "percent": float(percent),
                        "raw": line,
                    })
                except (ValueError, IndexError):
                    send_message({"type": "log", "data": line})
            else:
                send_message({"type": "log", "data": line})

        code = proc.wait()

        if code == 0:
            send_message({
                "type": "complete",
                "message": "Download complete!",
            })
        else:
            send_message({
                "type": "error",
                "error": f"yt-dlp exited with code {code}",
                "message": "The download failed. Check the logs for details.",
            })

    except FileNotFoundError:
        send_message({
            "type": "error",
            "error": "yt-dlp not found",
            "message": f"Could not find yt-dlp at: {yt_dlp_path}",
        })
    except Exception as e:
        send_message({
            "type": "error",
            "error": type(e).__name__,
            "message": str(e),
        })
    finally:
        # Clean up temp cookies
        cookies_path = os.path.join(os.path.expanduser("~"), ".clipvault_cookies.txt")
        if os.path.exists(cookies_path):
            os.remove(cookies_path)


def main():
    try:
        while True:
            msg = read_message()
            if msg is None:
                _log("main: stdin closed, exiting")
                break

            action = msg.get("action")
            payload = msg.get("payload", {})
            _log(f"main: action={action}")

            if action == "ping":
                _log("main: handling ping...")
                yt_dlp, search_log = find_yt_dlp()
                _log(f"main: ping result: found={yt_dlp is not None}, path={yt_dlp}")
                send_message({
                    "type": "pong",
                    "ytDlpFound": yt_dlp is not None,
                    "ytDlpPath": yt_dlp,
                    "searchLog": search_log,
                })
            elif action == "download":
                _log("main: handling download...")
                run_yt_dlp(payload)
                send_message({"type": "done"})
            else:
                _log(f"main: unknown action: {action}")
                send_message({
                    "type": "error",
                    "error": "unknown_action",
                    "message": f"Unknown action: {action}",
                })
    except Exception as e:
        _log(f"CRASH: {type(e).__name__}: {str(e)}")
        _log(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"FATAL: {type(e).__name__}: {str(e)}")
        _log(traceback.format_exc())
        raise
