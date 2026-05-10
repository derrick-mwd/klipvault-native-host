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
    # Check PATH first
    path = shutil.which("yt-dlp")
    if path:
        return path

    # Common fallback locations
    candidates = [
        os.path.expanduser("~/.local/bin/yt-dlp"),
        os.path.expanduser("~/bin/yt-dlp"),
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp",
        os.path.expanduser("~/.yt-dlp/yt-dlp"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    # Windows
    if sys.platform == "win32":
        win_candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%APPDATA%\Python\Python3*\Scripts\yt-dlp.exe"),
            os.path.expandvars(r"%USERPROFILE%\yt-dlp.exe"),
            r"C:\Program Files\yt-dlp\yt-dlp.exe",
        ]
        import glob
        for pattern in win_candidates:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

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
