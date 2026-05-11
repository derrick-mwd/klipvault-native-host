#!/usr/bin/env python3
"""
Firefox Native Messaging Diagnostic & Fix Tool for KlipVault

This script:
1. Finds your Firefox profile(s)
2. Reads extensions.json to find the ACTUAL temporary extension ID
3. Checks if the native host manifest matches that ID
4. Auto-fixes the manifest if there's a mismatch

Run: python diagnose_firefox.py
"""

import json
import os
import platform
import sys
import glob
import re


def get_firefox_profiles_dir():
    """Find Firefox profiles directory."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        appdata = os.environ.get("APPDATA", home)
        return os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
    elif system == "Darwin":
        return os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")
    else:  # Linux
        return os.path.join(home, ".mozilla", "firefox")


def find_klipvault_extension_id():
    """Find the actual KlipVault extension ID from Firefox's extensions.json."""
    profiles_dir = get_firefox_profiles_dir()

    if not os.path.isdir(profiles_dir):
        print(f"❌ Firefox profiles directory not found: {profiles_dir}")
        return None

    # Find all profile directories
    profiles = []
    for item in os.listdir(profiles_dir):
        item_path = os.path.join(profiles_dir, item)
        if os.path.isdir(item_path):
            ext_json = os.path.join(item_path, "extensions.json")
            if os.path.isfile(ext_json):
                profiles.append((item, ext_json))

    if not profiles:
        print(f"❌ No Firefox profiles with extensions.json found in {profiles_dir}")
        return None

    klipvault_ids = []

    for profile_name, ext_json_path in profiles:
        try:
            with open(ext_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            addons = data.get("addons", [])
            for addon in addons:
                # Check multiple name fields
                name = addon.get("defaultLocale", {}).get("name", "")
                if not name:
                    name = addon.get("name", "")

                if "klipvault" in name.lower() or "clip vault" in name.lower():
                    ext_id = addon.get("id")
                    if ext_id:
                        klipvault_ids.append({
                            "profile": profile_name,
                            "id": ext_id,
                            "name": name,
                            "active": addon.get("active", False),
                            "userDisabled": addon.get("userDisabled", False),
                        })
        except Exception as e:
            print(f"⚠️  Could not read {ext_json_path}: {e}")
            continue

    return klipvault_ids


def get_native_host_manifest_path():
    """Find the native host manifest file."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        appdata = os.environ.get("APPDATA", home)
        manifest_dir = os.path.join(appdata, "Mozilla", "NativeMessagingHosts")
    elif system == "Darwin":
        manifest_dir = os.path.join(home, "Library", "Application Support", "Mozilla", "NativeMessagingHosts")
    else:  # Linux
        manifest_dir = os.path.join(home, ".mozilla", "native-messaging-hosts")

    manifest_path = os.path.join(manifest_dir, "klipvault_host.json")
    return manifest_path


def read_manifest(manifest_path):
    """Read the native host manifest."""
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Could not read manifest: {e}")
        return None


def update_manifest(manifest_path, extension_id):
    """Update the manifest with the correct extension ID."""
    manifest = read_manifest(manifest_path)
    if not manifest:
        return False

    old_ids = manifest.get("allowed_extensions", [])
    manifest["allowed_extensions"] = [extension_id]

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"✅ Updated allowed_extensions from {old_ids} to ['{extension_id}']")
        return True
    except Exception as e:
        print(f"❌ Could not write manifest: {e}")
        return False


def is_wsl():
    """Detect if running inside WSL."""
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r") as f:
            content = f.read().lower()
            return "microsoft" in content or "wsl" in content
    except Exception:
        pass
    return False


def get_windows_home_from_wsl():
    """Get Windows user home directory when running in WSL."""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell.exe", "-Command", "Write-Output $env:USERPROFILE"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            win_path = result.stdout.strip()
            if len(win_path) >= 3 and win_path[1] == ":":
                drive = win_path[0].lower()
                rest = win_path[3:].replace("\\", "/")
                return f"/mnt/{drive}/{rest}"
    except Exception:
        pass

    for drive in "cdefgh":
        users_dir = f"/mnt/{drive}/Users"
        if os.path.isdir(users_dir):
            for name in sorted(os.listdir(users_dir)):
                if name not in ("All Users", "Default", "Default User", "Public"):
                    user_path = os.path.join(users_dir, name)
                    if os.path.isdir(user_path):
                        return user_path
    return None


def get_wsl_firefox_manifest_path():
    """Get the manifest path when running in WSL (for Windows Firefox)."""
    win_home = get_windows_home_from_wsl()
    if not win_home:
        return None
    return os.path.join(win_home, "AppData", "Roaming", "Mozilla", "NativeMessagingHosts", "klipvault_host.json")


def check_firefox_registry():
    """Check if Firefox registry key exists (Windows only)."""
    if platform.system() != "Windows" and not is_wsl():
        return None

    try:
        import winreg
        key_path = r"SOFTWARE\Mozilla\NativeMessagingHosts\klipvault_host"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, None)
            return value
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print("=" * 60)
    print("  KlipVault Firefox Native Messaging Diagnostic")
    print("=" * 60)
    print()

    # 1. Find Firefox extension(s)
    print("\n--- Step 1: Finding KlipVault Firefox Extension ---")
    extensions = find_klipvault_extension_id()

    if not extensions:
        print("❌ No KlipVault extension found in Firefox.")
        print()
        print("Make sure you have:")
        print("  1. Installed the KlipVault Firefox extension")
        print("  2. Loaded it via about:debugging → This Firefox")
        print()
        print("If you just installed it, restart Firefox first.")
        return

    print(f"✅ Found {len(extensions)} KlipVault extension(s):")
    for ext in extensions:
        status = "🟢 ACTIVE" if ext["active"] and not ext["userDisabled"] else "🔴 INACTIVE"
        print(f"\n  Profile: {ext['profile']}")
        print(f"  Name:    {ext['name']}")
        print(f"  ID:      {ext['id']}")
        print(f"  Status:  {status}")

    # Use the first active extension, or just the first one
    target_ext = next((e for e in extensions if e["active"] and not e["userDisabled"]), extensions[0])
    actual_id = target_ext["id"]

    print(f"\n👉 Using extension ID: {actual_id}")
    print()

    # 2. Find native host manifest
    print("\n--- Step 2: Checking Native Host Manifest ---")

    manifest_paths = [get_native_host_manifest_path()]
    if is_wsl():
        wsl_path = get_wsl_firefox_manifest_path()
        if wsl_path:
            manifest_paths.append(wsl_path)

    manifest = None
    manifest_path = None

    for path in manifest_paths:
        print(f"\n  Checking: {path}")
        m = read_manifest(path)
        if m:
            manifest = m
            manifest_path = path
            print(f"  ✅ Manifest found")
            break
        else:
            print(f"  ❌ Not found")

    if not manifest:
        print("\n❌ No native host manifest found anywhere!")
        print("\nRun install.py first:")
        print("  python install.py")
        return

    print(f"\n  Manifest location: {manifest_path}")
    print(f"  allowed_extensions: {manifest.get('allowed_extensions', 'NOT SET')}")
    print(f"  path (host exe):    {manifest.get('path', 'NOT SET')}")

    # 3. Check for ID mismatch
    print("\n--- Step 3: Checking for ID Mismatch ---")

    allowed = manifest.get("allowed_extensions", [])
    if actual_id in allowed:
        print("✅ Extension ID matches! No fix needed.")
    else:
        print("❌ MISMATCH DETECTED!")
        print(f"  Manifest has:   {allowed}")
        print(f"  Firefox has:    {actual_id}")
        print()
        print("This happens because Firefox temporary add-ons get a random UUID")
        print("instead of using the gecko.id from the manifest.")
        print()

        # Auto-fix
        print("--- Auto-fixing manifest ---")
        if update_manifest(manifest_path, actual_id):
            print("\n✅ Manifest updated successfully!")
            print()
            print("IMPORTANT: You MUST fully restart Firefox for this to take effect.")
            print("  - Close ALL Firefox windows")
            print("  - Right-click Firefox in taskbar → Quit")
            print("  - Reopen Firefox")
            print()

            # Also check registry on Windows
            if platform.system() == "Windows" or is_wsl():
                reg_value = check_firefox_registry()
                if reg_value:
                    print(f"🔍 Firefox registry key points to: {reg_value}")
                    if reg_value == manifest_path:
                        print("✅ Registry matches manifest location")
                    else:
                        print("⚠️  Registry points to a different manifest!")
                        print("   This could cause issues.")
                else:
                    print("⚠️  No Firefox registry key found.")
                    print("   Firefox should still find the manifest via the filesystem.")
        else:
            print("❌ Failed to update manifest.")

    # 4. Check host executable exists
    print("\n--- Step 4: Checking Host Executable ---")
    host_path = manifest.get("path", "")
    if os.path.isfile(host_path):
        print(f"✅ Host executable exists: {host_path}")
    else:
        print(f"❌ Host executable NOT found: {host_path}")
        print("   Run install.py to reinstall the native host.")

    print("\n" + "=" * 60)
    print("  Diagnostic complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
