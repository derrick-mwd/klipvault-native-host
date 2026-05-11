# Chrome Web Store / Mozilla Add-ons — Privacy Practices Justifications

Copy and paste each field into the Privacy practices tab.

---

## Single Purpose Description

This extension's single purpose is to download videos from the internet. It serves as a companion to the KlipVault website (klipvault.xyz), providing the actual download capability by invoking yt-dlp locally on the user's computer. The extension handles cookie extraction for authenticated platforms, HLS stream downloading, and batch processing.

---

## activeTab

**Justification:** The activeTab permission is used to detect when the user is browsing a video page (e.g., YouTube, Twitch) and to enable one-click downloading via the extension's toolbar popup. When the user clicks the extension icon, activeTab allows the popup to read the current page URL and initiate a download without requiring broad host permissions for all websites. No browsing data is collected, stored, or transmitted.

---

## cookies

**Justification:** The cookies permission is used exclusively to extract session cookies from the browser for specific video platforms that require authentication (Instagram, X/Twitter, Reddit, TikTok, Facebook, Pinterest). These cookies are passed directly to the local yt-dlp installation to enable downloading of private or restricted content. Cookies are never uploaded to any server, shared with third parties, or stored persistently. They are read in real-time at the moment of download and discarded immediately afterward.

---

## downloads

**Justification:** The downloads permission is required to save video files to the user's local Downloads folder. The extension uses the chrome.downloads API to initiate file saves with descriptive filenames derived from the video title. No download metadata is transmitted externally; all download activity happens locally on the user's machine via yt-dlp.

---

## Host Permissions

**Justification:** Host permissions are required for three specific purposes:

1. **https://klipvault.xyz/*** — To communicate with the KlipVault website, receive download requests, and verify premium status.

2. **https://*.googlevideo.com/***, **https://*.vimeocdn.com/***, **https://*.dmcdn.net/*** — To fetch direct video stream URLs for YouTube, Vimeo, and Dailymotion downloads initiated by the user.

3. Content script matches on **youtube.com**, **vimeo.com**, **dailymotion.com** — To detect video pages and enable one-click toolbar downloads.

No data is collected from these domains beyond what is necessary to fulfill the user's explicit download request.

---

## nativeMessaging

**Justification:** The nativeMessaging permission is required to communicate with a locally-installed Python bridge (klipvault_host.py) that invokes yt-dlp on the user's computer. The extension sends the video URL, optional cookies, and format preferences to this local process; the local process returns download progress and completion status. No data is transmitted over the internet or to any remote server. The native host runs entirely on the user's machine and its source code is publicly available at https://github.com/derrick-mwd/klipvault-native-host.

---

## Remote Code

**Justification:** This extension does NOT execute remote code. The extension communicates with yt-dlp, an open-source video downloader (https://github.com/yt-dlp/yt-dlp), which is installed locally on the user's computer via pip or standalone binary. The extension itself contains no eval(), no dynamically loaded scripts, and no code fetched from external sources. All code executed is either bundled in the extension package or runs as a local subprocess on the user's machine.

---

## scripting

**Justification:** The scripting permission is used to inject content scripts into specific video platform pages (YouTube, Vimeo, Dailymotion) and the KlipVault website. These content scripts:

1. Detect video URLs on supported pages for one-click toolbar downloads
2. Relay messages between the KlipVault website and the extension's background script
3. Set a DOM attribute to indicate the extension is installed

No user data is collected, modified, or transmitted. Scripts are injected only into the domains explicitly listed in the manifest.

---

## storage

**Justification:** The storage permission is used to persist download history and daily download counts in the browser's local storage. Specifically:

- **Download history**: A list of recently downloaded videos (title, URL, format, timestamp) displayed in the extension popup
- **Daily usage counter**: Tracks free-tier download usage (3/day) with a midnight UTC reset
- **Premium status**: A flag indicating whether the user has purchased premium access

All data is stored locally and never synced, transmitted, or shared. The user can clear this data at any time via the extension popup.

---

## Data Usage Certification

I certify that this extension's data usage complies with the Chrome Web Store Developer Program Policies and Mozilla Add-on Policies:

- ✅ No personal or sensitive user data is collected, transmitted, or shared
- ✅ All video downloads happen locally on the user's machine via yt-dlp
- ✅ Cookies are extracted only for the specific video platform being downloaded and are never stored or transmitted
- ✅ Download history is stored only in the browser's local storage
- ✅ The extension serves a single purpose: downloading videos
- ✅ No remote code execution; all code is bundled or runs as a local subprocess
- ✅ The extension is transparent about its functionality and provides a public source code repository
- ✅ Users are informed about the extension's data practices through this privacy disclosure and the website's privacy policy

---

## Additional Notes for Mozilla Reviewers

This extension uses Native Messaging to communicate with a locally-installed Python script (klipvault_host.py). This script is open-source and available at https://github.com/derrick-mwd/klipvault-native-host. It invokes yt-dlp (https://github.com/yt-dlp/yt-dlp), a well-established open-source video downloader.

The extension's design:
- The website (klipvault.xyz) provides the user interface
- The extension acts as a bridge between the website and the local yt-dlp installation
- The native host runs yt-dlp as a subprocess with standard command-line arguments
- No network requests are made by the extension to external servers beyond the KlipVault website API

The extension is not monetized through user data; revenue comes from optional premium subscriptions and display advertising on the companion website.
