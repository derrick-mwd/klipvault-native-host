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


def find_yt_dlp():
    """Find yt-dlp binary in PATH or common locations."""
    # Try user's actual shell PATH first (Chrome's PATH is often minimal)
    # This fixes the common case where yt-dlp is installed via pip/homebrew
    # but Chrome launches the native host with a stripped-down PATH.
    shell_path = _get_shell_path()
    if shell_path:
        for directory in shell_path.split(os.pathsep):
            candidate = os.path.join(directory, "yt-dlp")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
            # Windows
            if sys.platform == "win32":
                candidate_exe = candidate + ".exe"
                if os.path.isfile(candidate_exe):
                    return candidate_exe

    # Fallback: shutil.which with the default (minimal) PATH
    path = shutil.which("yt-dlp")
    if path:
        return path

    # Common fallback locations — macOS
    mac_candidates = [
        "/usr/local/bin/yt-dlp",          # Homebrew (Intel), pip system
        "/opt/homebrew/bin/yt-dlp",       # Homebrew (Apple Silicon)
        os.path.expanduser("~/.local/bin/yt-dlp"),  # pip --user (Linux-style on mac)
        os.path.expanduser("~/bin/yt-dlp"),
        "/usr/bin/yt-dlp",
    ]
    # pip user install on macOS puts binaries in ~/Library/Python/X.Y/bin/
    try:
        import glob
        pip_user_bins = glob.glob(os.path.expanduser("~/Library/Python/*/bin/yt-dlp"))
        mac_candidates.extend(pip_user_bins)
    except Exception:
        pass

    for c in mac_candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    # Common fallback locations — Linux
    linux_candidates = [
        os.path.expanduser("~/.local/bin/yt-dlp"),
        os.path.expanduser("~/bin/yt-dlp"),
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp",
        "/bin/yt-dlp",
        os.path.expanduser("~/.yt-dlp/yt-dlp"),
    ]
    for c in linux_candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    # Windows
    if sys.platform == "win32":
        import glob
        win_candidates = [
            # Our setup guide recommends C:\yt-dlp
            r"C:\yt-dlp\yt-dlp.exe",
            # pip install puts it in Python Scripts folder
            # We need to scan actual Python install directories
        ]
        # Scan common Python Scripts folders
        python_roots = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
            os.path.expandvars(r"%APPDATA%\Python"),
            r"C:\Python",
            r"C:\Program Files\Python",
            r"C:\Program Files (x86)\Python",
        ]
        for root in python_roots:
            if not os.path.isdir(root):
                continue
            # Look for Python3x/Scripts/yt-dlp.exe
            for scripts_dir in glob.glob(os.path.join(root, "*", "Scripts")):
                candidate = os.path.join(scripts_dir, "yt-dlp.exe")
                if os.path.isfile(candidate):
                    return candidate

        # pip user install on Windows
        user_scripts = os.path.expandvars(r"%APPDATA%\Python\Python*\Scripts")
        for scripts_dir in glob.glob(user_scripts):
            candidate = os.path.join(scripts_dir, "yt-dlp.exe")
            if os.path.isfile(candidate):
                return candidate

        # Also check the user's home directory
        home = os.path.expanduser("~")
        for c in win_candidates:
            if os.path.isfile(c):
                return c
            # Check in home as well
            home_candidate = os.path.join(home, os.path.basename(c))
            if os.path.isfile(home_candidate):
                return home_candidate

    return None


def _get_shell_path():
    """
    Try to retrieve the user's actual shell PATH.
    Chrome (and other GUI apps on macOS/Linux) launch child processes with a
    minimal system PATH that doesn't include pip --user, Homebrew, etc.
    We run the user's default shell in non-interactive mode to get its PATH.
    """
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        # Use -l (login) to load profile/rc files, -c to run a command
        result = subprocess.run(
            [shell, "-l", "-c", "echo $PATH"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Fallback for Windows: try to read the registry PATH
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                path, _ = winreg.QueryValueEx(key, "Path")
                if path:
                    return path
        except Exception:
            pass
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                path, _ = winreg.QueryValueEx(key, "Path")
                if path:
                    return path
        except Exception:
            pass

    return None


def send_message(msg):
    """Send a JSON message to the browser via stdout."""
    data = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def read_message():
    """Read a length-prefixed JSON message from stdin."""
    raw = sys.stdin.buffer.read(4)
    if not raw:
        return None
    size = struct.unpack("=I", raw)[0]
    data = sys.stdin.buffer.read(size).decode("utf-8")
    return json.loads(data)


def run_yt_dlp(payload):
    """Run yt-dlp with the given payload and stream progress."""
    yt_dlp_path = find_yt_dlp()
    if not yt_dlp_path:
        send_message({
            "type": "error",
            "error": "yt-dlp not found",
            "message": "yt-dlp is not installed or not in your PATH. Install it with: pip install yt-dlp"
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
    while True:
        msg = read_message()
        if msg is None:
            break

        action = msg.get("action")
        payload = msg.get("payload", {})

        if action == "ping":
            yt_dlp = find_yt_dlp()
            send_message({
                "type": "pong",
                "ytDlpFound": yt_dlp is not None,
                "ytDlpPath": yt_dlp,
            })
        elif action == "download":
            run_yt_dlp(payload)
            send_message({"type": "done"})
        else:
            send_message({
                "type": "error",
                "error": "unknown_action",
                "message": f"Unknown action: {action}",
            })


if __name__ == "__main__":
    main()
