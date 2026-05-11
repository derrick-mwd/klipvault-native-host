# KlipVault Video Downloader — Extension Store Description

## Short Description (Chrome Web Store / AMO — max 132 chars)

Companion extension for KlipVault (klipvault.xyz). Download videos from YouTube, TikTok, Instagram, Twitch & more with yt-dlp.

---

## Full Description

**KlipVault** is a free online video downloader at https://klipvault.xyz that lets you paste a link and get download URLs for videos from YouTube, TikTok, Instagram, X/Twitter, Reddit, Twitch, Vimeo, Dailymotion, Facebook, Bilibili, Pinterest, SoundCloud, and more.

This **companion browser extension** unlocks the full power of KlipVault by running downloads locally on your computer through [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the same open-source engine used by millions of users worldwide.

### What the extension does

- **Downloads HLS streams** (Twitch VODs, livestream replays, segmented video) that browser-only tools cannot handle
- **Extracts cookies automatically** from your browser for Instagram, X/Twitter, Reddit, and other platforms that require login
- **Routes all downloads through yt-dlp** running locally on your machine — no files are uploaded to any server
- **Works seamlessly with klipvault.xyz** — paste a link on the website, pick a format, and the extension handles the actual download
- **Supports batch downloads** and playlist extraction for YouTube and SoundCloud

### How it works

1. Visit https://klipvault.xyz and paste a video URL
2. The website fetches video metadata (title, thumbnail, available formats)
3. Click **"Download via Extension"** — the website sends the URL to this extension
4. The extension auto-extracts any needed cookies and passes everything to yt-dlp
5. yt-dlp downloads the video directly to your computer

### Why a companion extension?

Video platforms like YouTube, Instagram, and TikTok actively block server-based downloaders. By moving the actual download logic to your local machine via yt-dlp, KlipVault bypasses these restrictions entirely while keeping your data private — nothing leaves your computer except the initial metadata request.

### Requirements

- **yt-dlp** must be installed on your computer ([installation guide](https://github.com/yt-dlp/yt-dlp#installation))
- A one-time setup connects this extension to yt-dlp via Native Messaging
- Full setup instructions: https://klipvault.xyz/setup

### Permissions explained

- **downloads** — Saves video files to your computer
- **storage** — Tracks download history and daily limits locally
- **activeTab / scripting** — Detects video pages you visit (optional one-click download)
- **nativeMessaging** — Communicates with the local yt-dlp installation
- **cookies** — Extracts session cookies for authenticated platforms (Instagram, X, Reddit)

### Privacy

- All downloads happen **locally** on your machine
- No video content is uploaded to KlipVault servers
- Download history is stored **only** in your browser's local storage
- Cookie extraction is limited to the specific domain of the video being downloaded

### Free version

- 3 downloads per day (resets at midnight UTC)
- All platforms and formats supported
- No ads, no signup required

### Premium

- Unlimited daily downloads
- 4K / 8K quality
- Batch & playlist downloads
- Priority support

---

## Mozilla AMO Developer Notes (for reviewer)

This extension uses **Native Messaging** to communicate with a locally-installed Python script (`klipvault_host.py`) that invokes [yt-dlp](https://github.com/yt-dlp/yt-dlp) — an open-source, community-maintained video downloader.

**No remote code is executed.** The extension only:
1. Sends video URLs and optional cookies to the local host
2. Receives download progress updates and completion status
3. The local host runs yt-dlp as a subprocess with fully auditable command-line arguments

The extension is designed to work with the companion website https://klipvault.xyz. The website provides the user interface for pasting URLs and selecting formats; the extension provides the actual download capability by leveraging the user's local yt-dlp installation.

Source code: https://github.com/derrick-mwd/klipvault-native-host
