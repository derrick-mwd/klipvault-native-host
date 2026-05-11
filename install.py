#!/usr/bin/env python3
"""
KlipVault Native Host Installer
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


def is_wsl():
    """Detect if running inside Windows Subsystem for Linux."""
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except Exception:
        pass
    return False


def get_windows_home_from_wsl():
    """Get Windows user home directory when running in WSL."""
    # Try wslpath first
    try:
        result = subprocess.run(["wslpath", "-u", "C:\\Users"], capture_output=True, text=True)
        if result.returncode == 0:
            users_dir = result.stdout.strip()
            # Find the non-system user folder
            for name in sorted(os.listdir(users_dir)):
                user_path = os.path.join(users_dir, name)
                if name not in ("All Users", "Default", "Default User", "Public") and os.path.isdir(user_path):
                    return user_path
    except Exception:
        pass

    # Fallback: read Windows USERPROFILE via powershell
    try:
        result = subprocess.run(
            ["powershell.exe", "-Command", "Write-Output $env:USERPROFILE"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            win_path = result.stdout.strip()
            # Convert C:\Users\zylux to /mnt/c/Users/zylux
            if len(win_path) >= 3 and win_path[1] == ":":
                drive = win_path[0].lower()
                rest = win_path[3:].replace("\\", "/")
                return f"/mnt/{drive}/{rest}"
    except Exception:
        pass

    # Last resort: scan /mnt/c/Users for a real user directory
    for drive in "cdefgh":
        users_dir = f"/mnt/{drive}/Users"
        if os.path.isdir(users_dir):
            for name in sorted(os.listdir(users_dir)):
                user_path = os.path.join(users_dir, name)
                if name not in ("All Users", "Default", "Default User", "Public") and os.path.isdir(user_path):
                    return user_path
    return None


def get_firefox_nm_dir():
    """Get Firefox NativeMessagingHosts directory."""
    system = platform.system()
    home = os.path.expanduser("~")

    if is_wsl():
        # On WSL, install to Windows Firefox location so Windows Firefox can find it
        win_home = get_windows_home_from_wsl()
        if win_home:
            return os.path.join(win_home, "AppData", "Roaming", "Mozilla", "NativeMessagingHosts")
        # Fallback
        return os.path.join("/mnt/c/Users", os.environ.get("USER", ""), "AppData", "Roaming", "Mozilla", "NativeMessagingHosts")

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
    manifest_path = os.path.join(script_dir, "klipvault_host.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest["path"] = host_script_path

    dest_manifest = os.path.join(nm_dir, "klipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅ Chrome manifest installed: {dest_manifest}")
    return True


def find_chrome_extension_id():
    """Try to auto-detect the KlipVault extension ID from Chrome's extension directories."""
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
                        if "klipvault" in name.lower() or "clip vault" in name.lower():
                            return ext_id
                    except Exception:
                        continue
    return None


def find_firefox_extension_id():
    """Try to auto-detect the KlipVault extension ID from Firefox's extensions.json.
    
    When a Firefox extension is loaded as a temporary add-on, Firefox assigns a
    random UUID instead of using the gecko.id from the manifest. We need to read
    the actual ID from Firefox's profile data.
    """
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        profiles_dir = os.path.join(os.environ.get("APPDATA", home), "Mozilla", "Firefox", "Profiles")
    elif system == "Darwin":
        profiles_dir = os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")
    else:  # Linux
        profiles_dir = os.path.join(home, ".mozilla", "firefox")

    if not os.path.isdir(profiles_dir):
        return None

    for item in os.listdir(profiles_dir):
        profile_path = os.path.join(profiles_dir, item)
        if not os.path.isdir(profile_path):
            continue
        ext_json = os.path.join(profile_path, "extensions.json")
        if not os.path.isfile(ext_json):
            continue
        try:
            with open(ext_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            for addon in data.get("addons", []):
                name = addon.get("defaultLocale", {}).get("name", "")
                if not name:
                    name = addon.get("name", "")
                if "klipvault" in name.lower() or "clip vault" in name.lower():
                    ext_id = addon.get("id")
                    if ext_id:
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
            print(f"🔍 Auto-detected KlipVault extension ID: {extension_id}")

    if not extension_id:
        print("❌ Could not detect your KlipVault extension ID.")
        print()
        print("To fix this:")
        print("  1. Open Chrome and go to chrome://extensions/")
        print("  2. Find 'KlipVault Video Downloader'")
        print("  3. Copy the Extension ID (e.g., abcdefghijklmnopqrstuvwxyzabc)")
        print("  4. Re-run: python install.py --extension-id <YOUR_ID>")
        print()
        return False

    # Write manifest + host script to a known location
    appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    nm_dir = os.path.join(appdata, "KlipVault", "NativeMessagingHosts")
    os.makedirs(nm_dir, exist_ok=True)

    # Copy the Python host script into the same directory
    dest_script = os.path.join(nm_dir, "klipvault_host.py")
    shutil.copy2(host_script_path, dest_script)

    # Create a .bat wrapper so Chrome doesn't need .py file associations
    python_exe = sys.executable  # full path to the python that ran install.py
    bat_path = os.path.join(nm_dir, "klipvault_host.bat")
    with open(bat_path, "w", newline="") as f:
        f.write('@echo off\n')
        f.write(f'"{python_exe}" "%~dp0klipvault_host.py"\n')

    # Create manifest pointing to the .bat wrapper
    manifest = {
        "name": "klipvault_host",
        "description": "KlipVault Native Messaging Host for yt-dlp",
        "path": bat_path,
        "type": "stdio",
        "allowed_origins": [
            f"chrome-extension://{extension_id}/"
        ]
    }

    dest_manifest = os.path.join(nm_dir, "klipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    # Register in registry
    key_path = r"SOFTWARE\Google\Chrome\NativeMessagingHosts\klipvault_host"
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


def to_windows_path(wsl_path):
    """Convert a WSL path to a Windows path for use in manifest JSON."""
    if wsl_path.startswith("/mnt/"):
        drive = wsl_path[5]  # e.g., 'c' from /mnt/c/...
        rest = wsl_path[7:]  # everything after /mnt/c/
        win_sep = rest.replace("/", "\\")
        return drive.upper() + ":\\" + win_sep
    return wsl_path


def install_firefox(script_dir, host_script_path):
    """Install for Firefox."""
    nm_dir = get_firefox_nm_dir()
    if not nm_dir:
        print("⚠️  Firefox Native Messaging directory not found. Skipping Firefox install.")
        return False

    os.makedirs(nm_dir, exist_ok=True)
    wsl_mode = is_wsl()

    # Auto-detect the actual Firefox extension ID (critical for temporary add-ons)
    firefox_ext_id = find_firefox_extension_id()
    if firefox_ext_id:
        print(f"🔍 Auto-detected Firefox extension ID: {firefox_ext_id}")
    else:
        print("⚠️  Could not auto-detect Firefox extension ID. Using default.")
        print("   If you loaded the extension as a temporary add-on, the ID may be wrong.")
        print("   Run diagnose_firefox.py after installation to fix this.")
        firefox_ext_id = "derrickvf82@gmail.com"

    # On Windows or WSL, Firefox requires an actual .exe for native messaging.
    # .bat files don't work because Firefox uses CreateProcessW directly.
    # We ship a tiny C wrapper (firefox_wrapper.exe) that discovers python.exe
    # via registry and runs klipvault_host.py with inherited stdio handles.
    if platform.system() == "Windows" or wsl_mode:
        dest_script = os.path.join(nm_dir, "klipvault_host.py")
        # Manual copy to avoid shutil trying to copy permissions on Windows mounts
        with open(host_script_path, "rb") as src, open(dest_script, "wb") as dst:
            dst.write(src.read())
        # Copy the pre-built wrapper exe
        wrapper_src = os.path.join(script_dir, "firefox_wrapper.exe")
        if os.path.isfile(wrapper_src):
            wrapper_dest = os.path.join(nm_dir, "firefox_wrapper.exe")
            with open(wrapper_src, "rb") as src, open(wrapper_dest, "wb") as dst:
                dst.write(src.read())
            manifest_path = wrapper_dest
            print(f"✅ Firefox wrapper copied: {wrapper_dest}")
        else:
            # Fallback to .bat if wrapper not found (should not happen)
            python_exe = sys.executable
            bat_path = os.path.join(nm_dir, "klipvault_host.bat")
            with open(bat_path, "w", newline="") as f:
                f.write('@echo off\n')
                f.write(f'"{python_exe}" "%~dp0klipvault_host.py"\n')
            manifest_path = bat_path
            print(f"⚠️  firefox_wrapper.exe not found, falling back to .bat: {bat_path}")

        # If on WSL, manifest path must be a Windows-style path in the JSON
        if wsl_mode:
            manifest_path = to_windows_path(manifest_path)
    else:
        manifest_path = host_script_path

    # Firefox manifest needs different allowed_extensions
    manifest = {
        "name": "klipvault_host",
        "description": "KlipVault Native Messaging Host for yt-dlp",
        "path": manifest_path,
        "type": "stdio",
        "allowed_extensions": [firefox_ext_id]
    }

    dest_manifest = os.path.join(nm_dir, "klipvault_host.json")
    with open(dest_manifest, "w") as f:
        json.dump(manifest, f, indent=2)

    # On Windows, also register in registry so Firefox can find it
    if platform.system() == "Windows" and not wsl_mode:
        try:
            import winreg
            key_path = r"SOFTWARE\Mozilla\NativeMessagingHosts\klipvault_host"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, dest_manifest)
            print(f"✅ Firefox registry key created: {key_path}")
        except Exception as e:
            print(f"⚠️  Could not create Firefox registry key: {e}")

    print(f"✅ Firefox manifest installed: {dest_manifest}")
    print(f"   allowed_extensions: [{firefox_ext_id}]")
    if wsl_mode:
        print(f"   (WSL mode — manifest uses Windows path: {manifest_path})")
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
    print("  KlipVault Native Messaging Host Installer")
    print("=" * 60)
    print()

    # Pre-flight checks
    if not check_python():
        sys.exit(1)

    check_yt_dlp()
    print()

    script_dir = get_script_dir()
    host_script = os.path.join(script_dir, "klipvault_host.py")

    if not os.path.isfile(host_script):
        print(f"❌ Host script not found: {host_script}")
        sys.exit(1)

    # Make executable on Unix
    if platform.system() != "Windows":
        os.chmod(host_script, 0o755)

    system = platform.system()
    installed_any = False

    if system == "Windows" or is_wsl():
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
        print("Then visit the KlipVault website and try")
        print("downloading a Twitch VOD or other HLS stream.")
    else:
        print("⚠️  No browsers were configured. Check the errors above.")
        print()
        print("You can manually copy klipvault_host.json to your browser's")
        print("NativeMessagingHosts directory. See the setup guide on the website.")

    print()


if __name__ == "__main__":
    main()
