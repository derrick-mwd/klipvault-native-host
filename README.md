# KlipVault Native Messaging Host

This small Python script bridges the KlipVault browser extension to your local **yt-dlp** installation, enabling downloads of HLS streams (Twitch, etc.), complex multi-segment videos, and anything else yt-dlp handles.

## What it does

- Receives download requests from the KlipVault extension
- Spawns yt-dlp with the correct arguments
- Streams real-time progress back to the extension popup
- Saves files to your `~/Downloads` folder
- Automatically cleans up temporary cookie files

## Prerequisites

1. **Python 3.7+** (usually pre-installed on macOS/Linux)
2. **yt-dlp** — install with:
   ```bash
   pip install yt-dlp
   # or
   pip3 install yt-dlp
   # or
   python3 -m pip install yt-dlp
   ```

## Quick Install

### macOS / Linux

```bash
cd ~/Downloads/klipvault-extension/native-host
python3 install.py
```

### Windows

```cmd
cd %USERPROFILE%\Downloads\klipvault-extension\native-host
python install.py
```

> **Restart your browser** after running the installer.

## Manual Install (if automatic fails)

### Chrome / Chromium / Brave

1. Copy `klipvault_host.py` to a permanent location (e.g. `~/.clipvault/`)
2. Edit `klipvault_host.json` and set `"path"` to the **absolute** path of `klipvault_host.py`
3. Copy the edited `klipvault_host.json` to:
   - **macOS**: `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`
   - **Linux**: `~/.config/google-chrome/NativeMessagingHosts/` (or `chromium/`)
   - **Windows**: Set registry key `HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\klipvault_host` to the full path of `klipvault_host.json`

### Firefox

1. Same as above, but copy to:
   - **macOS**: `~/Library/Application Support/Mozilla/NativeMessagingHosts/`
   - **Linux**: `~/.mozilla/native-messaging-hosts/`
   - **Windows**: `%APPDATA%\Mozilla\NativeMessagingHosts\`

## Verify it works

1. Open the KlipVault extension popup
2. Click the ℹ️ info icon — it shows whether the native host is connected
3. Or visit https://clipvault-psi.vercel.app, paste a Twitch VOD URL, and click **Get Download Link** → **Open in Extension**

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Native host not found" | Run `install.py` again, then fully restart your browser |
| "yt-dlp not found" | Install yt-dlp: `pip install yt-dlp` |
| Downloads fail silently | Check that yt-dlp works standalone: `yt-dlp --version` |
| Windows registry error | Run Command Prompt as Administrator |
| Firefox only, Chrome works | Firefox manifest uses `allowed_extensions` — verify the extension ID matches |

## Uninstall

Delete the `klipvault_host.json` manifest from your browser's NativeMessagingHosts directory (and remove the Windows registry key if applicable).
