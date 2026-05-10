# ClipVault Native Host

Native messaging host for the [ClipVault Extension](https://clipvault-psi.vercel.app). Enables downloading **HLS / DASH streams** (Twitch, Vimeo, and other `.m3u8` sources) by delegating downloads to a local [yt-dlp](https://github.com/yt-dlp/yt-dlp) installation.

## What This Does

The ClipVault browser extension communicates with this native host via [Chrome's Native Messaging API](https://developer.chrome.com/docs/extensions/mv3/nativeMessaging/). When you request an HLS download:

1. Extension → sends download request to this host
2. Host → spawns `yt-dlp` with the correct format and output path
3. yt-dlp → downloads and muxes the stream into an MP4/MKV
4. Host → streams real-time progress back to the extension popup

## Prerequisites

- Python 3.7+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) installed and available in your `PATH`

Install yt-dlp:

```bash
# macOS / Linux
python3 -m pip install -U yt-dlp

# Or download standalone binary
# See: https://github.com/yt-dlp/yt-dlp#installation
```

## Quick Install

### Option 1: Automatic (Recommended)

```bash
# 1. Clone this repo
git clone https://github.com/derrick-mwd/clipvault-native-host.git
cd clipvault-native-host

# 2. Run the installer
python3 install.py
```

The installer will:
- Detect your OS and browser
- Install the native host manifest to the correct directory
- Make `clipvault_host.py` executable
- Verify yt-dlp is available

### Option 2: Manual Install

See [`NATIVE_HOST_README.md`](./NATIVE_HOST_README.md) for manual installation instructions per OS.

## Files

| File | Description |
|------|-------------|
| `clipvault_host.py` | Python native messaging host — handles JSON messages from the extension, runs yt-dlp |
| `clipvault_host.json` | Browser manifest — tells Chrome/Firefox where to find the host |
| `install.py` | Cross-platform auto-installer |

## Supported Platforms

| OS | Chrome | Firefox |
|----|--------|---------|
| macOS | ✅ | ✅ |
| Linux | ✅ | ✅ |
| Windows | ✅ | ✅ |

## Troubleshooting

**"Native host not found" in extension**
→ Run `python3 install.py` again. Make sure you restarted your browser after installing.

**"yt-dlp not found"**
→ Install yt-dlp: `python3 -m pip install -U yt-dlp` and ensure it's in your PATH.

**Downloads fail immediately**
→ Check that `clipvault_host.py` is executable: `chmod +x clipvault_host.py`

For more help, see the full [Setup Guide](https://clipvault-psi.vercel.app/setup).

## License

MIT
