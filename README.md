## Assignment-7: Mashup

## 📋 Overview

This project consists of two primary components developed as per the assignment requirements:
- Program 1: A command-line Python application for creating musical mashups by downloading, processing, and merging YouTube audio.
- Program 2: A Flask-based web service that provides a graphical user interface for the Mashup tool, allowing users to generate and receive their custom audio files via email.

## Program 1: Mashup Command Line Tool

### Description

A Python utility that automates the creation of a mashup from a specified singer's YouTube catalog. The program downloads videos, extracts audio, trims them to a specific duration, and merges them into a single output file.

### Usage
The program must be run via the command line using the following syntax:
```bash
python <RollNumber>.py <SingerName> <NumberOfVideos> <AudioDuration> <OutputFileName>
```

**Command Line Arguments:**
- **SingerName:** Name of the artist to search for.
- **NumberOfVideos:** Number of videos to process (N > 10).
- **AudioDuration:** Seconds to trim from the start of each video (Y > 20).
- **OutputFileName:** The name of the resulting .mp3 file.

### Example

```bash
python 102497023.py "Guru Randhawa" 11 30 Guru_Randhawa_Mashup.mp3
```

---

## Program 2: YouTube Mashup Web Service

### Description
This Flask-based web service provides a graphical interface for Program 1. It automates the entire pipeline—from searching YouTube to delivering a custom audio mashup directly to the user's inbox in a compressed format.

### Features

- **Automated Audio Pipeline:** Integrated with Program 1's logic to search, download, trim, and merge audio files.
- **ZIP Packaging:** Automatically compresses the final output into a .zip file before transmission.
- **Email Integration:** Sends the .zip file to the user's validated email address.

### User Interface
<img src="assets/web_interface.jpeg" alt="Web UI">

### Initial Status
<img src="assets/initial_status.jpeg" alt="Web UI">

### Final Status
<img src="assets/final_status.jpeg" alt="Web UI">

### Mashup Result Email
<img src="assets/email.jpeg" alt="Email Delivery">

---

## Procedure to Run Locally

### 1. Setup Environment

Install the necessary Python libraries for audio processing and web hosting:
```bash
pip install -r requirements.txt
```

**Note:** FFmpeg must be installed on the system and its `/bin` folder must be added to the System PATH. 

### 2. (Optional) Configure Email Delivery

Email delivery uses [Resend](https://resend.com) — a modern email REST API that works on cloud platforms like Render (unlike SMTP which is blocked).

To enable email delivery, set these environment variables:
```bash
set RESEND_API_KEY=re_your_api_key_here
set EMAIL_FROM=mashup@mail.yourdomain.com
```

> **Note:** Resend requires a verified custom domain to send emails to arbitrary recipients. Without a domain, the app runs in **download-only mode** — users download the mashup zip directly from the browser.

### 3. Start the Service

```bash
python webapp/app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## Cloud Deployment Limitation

**⚠️ YouTube blocks cloud server IPs.** Platforms like Render, Heroku, and AWS block or get blocked by YouTube's anti-bot systems — outbound SMTP ports (587/465) are blocked by the platform, and YouTube rejects download requests from known datacenter IP ranges. This means the full mashup pipeline (download → process → deliver) **only works when run locally**. The Flask UI deploys fine, but `yt-dlp` downloads will fail on cloud servers.

---

## Important Notes

- Ensure `ffmpeg/bin` is added to your environment variables. The script will look for the global `ffmpeg` command to process audio.
- **Never hardcode API keys or credentials.** Use environment variables or a `.env` file (which is gitignored).
- For high-traffic artists (e.g., Asha Bhosle), a fresh `cookies.txt` must be in the webapp directory. This mimics a browser session to avoid "403 Forbidden" errors.
- Stable internet is required for downloading YouTube content.

--- 

## Technical Highlights

- **Non-Blocking Architecture:** Implemented Python Threading to move the audio processing pipeline (download/cut/merge) off the main web thread, keeping the Flask UI responsive.
- **Adaptive Error Catching:** Configured the `yt-dlp` exception handler to recognize "Maximum downloads reached" as a successful completion signal rather than a fatal crash.
- **Live Progress Tracking:** Utilized JavaScript Polling (`setInterval`) to fetch real-time job status from a dedicated server-side endpoint every 2 seconds.
- **Resource Management:** Automated cleanup using the `shutil` and `tempfile` modules to ensure all temporary audio fragments are deleted immediately after the ZIP file is generated.
- **Anti-Bot Formatting:** Forced `ba/b` (Best Audio) format selection to reduce the footprint of requests and minimize the risk of being flagged by YouTube's automated systems.
- **Graceful Fallback:** Download button always available regardless of email configuration status.
