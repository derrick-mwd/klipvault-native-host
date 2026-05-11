# KlipVault Extension

Browser extension for downloading videos from YouTube, Vimeo, Dailymotion and more.

## Features

- **One-click downloads** from the KlipVault website
- **Download manager** with queue and history
- **No server bandwidth** — downloads go directly from the video host to your disk
- **CORS bypass** — uses `chrome.downloads` API to download from any origin
- Works alongside [klipvault.xyz](https://klipvault.xyz)

## Install (Developer Mode)

1. Download `klipvault-extension-v1.zip` from Releases
2. Unzip to a folder
3. Open Chrome → `chrome://extensions/`
4. Enable **Developer mode** (toggle top-right)
5. Click **Load unpacked** → select the unzipped folder
6. Done! The extension icon appears in your toolbar

## How It Works

1. Go to [klipvault.xyz](https://klipvault.xyz) and paste a video URL
2. Select a format and click **Get Download Link**
3. Click **Open in Extension** → the extension downloads the file directly
4. Or click **Copy Direct Link** and paste into VLC, JDownloader, or IDM

## Architecture

```
Website (klipvault.xyz)
  ├── Extracts video metadata (~5KB JSON from server)
  ├── Shows format list
  └── Sends download command via postMessage → Extension

Extension
  ├── Content Script: listens for postMessage from website
  ├── Background Worker: handles chrome.downloads.download()
  └── Popup: download manager UI with history

Video Host (googlevideo.com, etc.)
  └── Direct download via chrome.downloads API (no CORS, no proxy)
```

## Permissions

- `downloads` — to save video files to disk
- `storage` — to persist download history
- `activeTab` + `scripting` — to detect video pages

## Build from Source

No build step required — this is vanilla JS/CSS. Just load the folder as an unpacked extension.

## Monetization

The extension supports a premium tier:
- **Free**: 3 downloads/day, up to 1080p60
- **Premium** — $14.99 lifetime or $2.99/mo:
  - Unlimited daily downloads
  - 4K / 8K video quality
  - Batch & playlist downloads
  - No daily limits

## License

MIT — Velocity Forge
