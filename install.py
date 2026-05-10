#!/usr/bin/env python3
"""
ClipVault Native Host Installer
Sets up the native messaging host for Chrome and Firefox.

Usage:
    python install.py

This will:
1. Detect your browser (Chrome, Chromium, Firefox)
2. Copy the host manifest to the correct directory
3. Register the host with your browser
4. Verify yt-dlp is installed
"""

import json
import os
import platform
import shutil
import subprocess
import sys


def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def find_yt_dlp():
    return shutil.which("yt-dlp")


def get_chrome_nm_dir():
    """Get Chrome/Chromium NativeMessagingHosts directory."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Darwin":
        return os.path.join(home, "Library/Application Support/Google/Chrome/NativeMessagingHosts")
    elif system == "Linux":
        # Try Chromium first, then Chrome
        candidates = [
            os.path.join(home, ".config/chromium/NativeMessagingHosts"),
            os.path.join(home, ".config/google-chrome/NativeMessagingHosts"),
            os.path.join(home, ".config/BraveSoftware/Brave-Browser/NativeMessagingHosts"),
        ]
        for c in candidates:
            if os.path.isdir(os.path.dirname(c)):
                return c
        return candidates[1]  # Default to Chrome
    elif system == "Windows":
        return None  # Windows uses registry, not a directory
    return None


def get_firefox_nm_dir():
    """Get Firefox NativeMessagingHosts directory."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Darwin":
        return os.path.join(home, "Library/Application Support/Mozilla/NativeMessagingHosts")
    elif system == "Linux":
        return os.path.join(home, ".mozilla/native-messaging-hosts")
    elif system == "Windows":
        return os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "NativeMessagingHosts")
    return None


def install_chrome(script_dir, host_script_path):
    """Install for Chrome/Chromium on macOS/Linux."""
    nm_dir = get_chrome_nm_dir()
    if not nm_dir:
        print("⚠️  Chrome Native Messaging directory not found. Skipping Chrome install.")
        return False

    os.makedirs(nm_dir, exist_ok=True)

    # Create manifest with absolute path
    manifest_path = os.path.join(script_dir, "clipvault_host.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest["path"] = host_script_path

    dest_manifest = os.path.join(nm_dir, "clipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅ Chrome manifest installed: {dest_manifest}")
    return True


def find_chrome_extension_id():
    """Try to auto-detect the ClipVault extension ID from Chrome's extension directories."""
    if platform.system() != "Windows":
        return None

    # Chrome stores extensions in %LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\Extensions\
    chrome_data = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    if not os.path.isdir(chrome_data):
        return None

    # Scan all profiles
    for profile_name in os.listdir(chrome_data):
        ext_dir = os.path.join(chrome_data, profile_name, "Extensions")
        if not os.path.isdir(ext_dir):
            continue

        for ext_id in os.listdir(ext_dir):
            ext_path = os.path.join(ext_dir, ext_id)
            if not os.path.isdir(ext_path):
                continue

            # Look for version subdirectories
            for version in os.listdir(ext_path):
                manifest_file = os.path.join(ext_path, version, "manifest.json")
                if os.path.isfile(manifest_file):
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        name = manifest.get("name", "")
                        # Match our extension name (could be localized or plain)
                        if "clipvault" in name.lower() or "clip vault" in name.lower():
                            return ext_id
                    except Exception:
                        continue
    return None


def install_chrome_windows(script_dir, host_script_path, extension_id=None):
    """Install for Chrome on Windows via registry."""
    try:
        import winreg
    except ImportError:
        print("⚠️  Could not import winreg. Skipping Chrome Windows install.")
        return False

    # Auto-detect extension ID if not provided
    if not extension_id:
        extension_id = find_chrome_extension_id()
        if extension_id:
            print(f"🔍 Auto-detected ClipVault extension ID: {extension_id}")

    if not extension_id:
        print("❌ Could not detect your ClipVault extension ID.")
        print()
        print("To fix this:")
        print("  1. Open Chrome and go to chrome://extensions/")
        print("  2. Find 'ClipVault Video Downloader'")
        print("  3. Copy the Extension ID (e.g., abcdefghijklmnopqrstuvwxyzabc)")
        print("  4. Re-run: python install.py --extension-id <YOUR_ID>")
        print()
        return False

    # Write manifest + host script to a known location
    appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    nm_dir = os.path.join(appdata, "ClipVault", "NativeMessagingHosts")
    os.makedirs(nm_dir, exist_ok=True)

    # Copy the Python host script into the same directory
    dest_script = os.path.join(nm_dir, "clipvault_host.py")
    shutil.copy2(host_script_path, dest_script)

    # Create a .bat wrapper so Chrome doesn't need .py file associations
    python_exe = sys.executable  # full path to the python that ran install.py
    bat_path = os.path.join(nm_dir, "clipvault_host.bat")
    with open(bat_path, "w", newline="") as f:
        f.write('@echo off\n')
        f.write(f'"{python_exe}" "%~dp0clipvault_host.py"\n')

    # Create manifest pointing to the .bat wrapper
    manifest = {
        "name": "clipvault_host",
        "description": "ClipVault Native Messaging Host for yt-dlp",
        "path": bat_path,
        "type": "stdio",
        "allowed_origins": [
            f"chrome-extension://{extension_id}/"
        ]
    }

    dest_manifest = os.path.join(nm_dir, "clipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    # Register in registry
    key_path = r"SOFTWARE\Google\Chrome\NativeMessagingHosts\clipvault_host"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, dest_manifest)
        print(f"✅ Chrome registry key created: {key_path}")
        print(f"✅ Chrome manifest installed: {dest_manifest}")
        print(f"✅ Host script copied to: {dest_script}")
        print(f"✅ Launcher wrapper created: {bat_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create Chrome registry key: {e}")
        return False


def install_firefox(script_dir, host_script_path):
    """Install for Firefox."""
    nm_dir = get_firefox_nm_dir()
    if not nm_dir:
        print("⚠️  Firefox Native Messaging directory not found. Skipping Firefox install.")
        return False

    os.makedirs(nm_dir, exist_ok=True)

    # On Windows, copy script to same dir and use .bat wrapper
    if platform.system() == "Windows":
        dest_script = os.path.join(nm_dir, "clipvault_host.py")
        shutil.copy2(host_script_path, dest_script)
        python_exe = sys.executable
        bat_path = os.path.join(nm_dir, "clipvault_host.bat")
        with open(bat_path, "w", newline="") as f:
            f.write('@echo off\n')
            f.write(f'"{python_exe}" "%~dp0clipvault_host.py"\n')
        manifest_path = bat_path
    else:
        manifest_path = host_script_path

    # Firefox manifest needs different allowed_origins
    manifest = {
        "name": "clipvault_host",
        "description": "ClipVault Native Messaging Host for yt-dlp",
        "path": manifest_path,
        "type": "stdio",
        "allowed_extensions": ["clipvault@velocityforge.com"]
    }

    dest_manifest = os.path.join(nm_dir, "clipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅ Firefox manifest installed: {dest_manifest}")
    return True


def check_yt_dlp():
    """Check if yt-dlp is installed and provide install instructions."""
    yt_dlp = find_yt_dlp()
    if yt_dlp:
        print(f"✅ yt-dlp found: {yt_dlp}")
        return True

    print("❌ yt-dlp NOT found!")
    print()
    print("Install yt-dlp with one of these methods:")
    print()
    print("  pip install yt-dlp")
    print("  pip3 install yt-dlp")
    print("  python3 -m pip install yt-dlp")
    print()
    print("Or download the standalone binary:")
    print("  https://github.com/yt-dlp/yt-dlp/releases")
    print()
    print("Make sure it's in your PATH after installation.")
    return False


def check_python():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print(f"❌ Python {version.major}.{version.minor} is too old. Python 3.7+ required.")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def main():
    # Parse command-line args
    extension_id = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--extension-id":
        extension_id = sys.argv[2]

    print("=" * 60)
    print("  ClipVault Native Messaging Host Installer")
    print("=" * 60)
    print()

    # Pre-flight checks
    if not check_python():
        sys.exit(1)

    check_yt_dlp()
    print()

    script_dir = get_script_dir()
    host_script = os.path.join(script_dir, "clipvault_host.py")

    if not os.path.isfile(host_script):
        print(f"❌ Host script not found: {host_script}")
        sys.exit(1)

    # Make executable on Unix
    if platform.system() != "Windows":
        os.chmod(host_script, 0o755)

    system = platform.system()
    installed_any = False

    if system == "Windows":
        if install_chrome_windows(script_dir, host_script, extension_id):
            installed_any = True
    else:
        if install_chrome(script_dir, host_script):
            installed_any = True

    if install_firefox(script_dir, host_script):
        installed_any = True

    print()
    if installed_any:
        print("=" * 60)
        print("  ✅ Installation complete!")
        print("=" * 60)
        print()
        print("Restart your browser for changes to take effect.")
        print()
        print("Then visit https://clipvault-psi.vercel.app and try")
        print("downloading a Twitch VOD or other HLS stream.")
    else:
        print("⚠️  No browsers were configured. Check the errors above.")
        print()
        print("You can manually copy clipvault_host.json to your browser's")
        print("NativeMessagingHosts directory. See the setup guide on the website.")

    print()


if __name__ == "__main__":
    main()
