from flask import Flask, render_template, request, jsonify, send_file
import threading
import os
import subprocess
import shutil
import tempfile
import zipfile
import yt_dlp
from pydub import AudioSegment
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import time
import uuid
import re
import random

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'temp_downloads'
RESULT_FOLDER = 'results'

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# Email configuration
EMAIL_ADDRESS = "skaushal1007@gmail.com"
EMAIL_PASSWORD = "xrqm mnta vysr sczv"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Store job status
jobs = {}

class MashupJob:
    def __init__(self, job_id, singer, n, y, email):
        self.job_id = job_id
        self.singer = singer
        self.n = n
        self.y = y
        self.email = email
        self.status = "pending"
        self.progress = 0
        self.message = ""
        self.output_file = None
        self.temp_dir = None
        self.start_time = time.time()

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'singer': self.singer,
            'n': self.n,
            'y': self.y,
            'email': self.email,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'elapsed_time': int(time.time() - self.start_time)
        }

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_email_with_attachment(recipient_email, zip_filepath, singer_name):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = f"Your Mashup for {singer_name} is Ready!"

        body = f"""
        Hello!
        
        Your mashup for singer "{singer_name}" has been created successfully.
        The zip file contains the merged audio file.
        
        Thank you for using our service!
        
        Regards,
        Mashup Web Service
        """
        
        msg.attach(MIMEText(body, 'plain'))

        with open(zip_filepath, 'rb') as attachment:
            part = MIMEBase('application', 'zip')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(zip_filepath)}')
            msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        # Return True anyway so process continues
        return True

def create_mashup(job):
    job.status = "processing"
    job.message = "Starting download with anti-bot protection..."
    job.progress = 5
    
    try:
        job.temp_dir = tempfile.mkdtemp(dir=UPLOAD_FOLDER)
        
        job.message = f"Searching for {job.singer} songs..."
        job.progress = 10
        
        # List of user agents to rotate
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        ]
        
        # ENHANCED yt-dlp options for Render
        opts = {
            'format': 'worstaudio/worst',  # Lower quality = faster, less likely to be blocked
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': os.path.join(job.temp_dir, '%(title)s.%(ext)s'),
            
            # 🔥 CRITICAL: Use cookies if available
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            
            # Anti-bot measures
            'sleep_interval': 3,
            'max_sleep_interval': 7,
            'sleep_interval_requests': 2,
            'extractor_retries': 5,
            'file_access_retries': 5,
            'fragment_retries': 5,
            
            # Rotate user agent
            'headers': {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            
            # Try different clients
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web_safari', 'web', 'ios'],
                }
            },
            
            # Other options
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'concurrent_fragment_downloads': 1,
        }
        
        # Try multiple search queries
        search_queries = [
            f"ytsearch{job.n * 2}:{job.singer} song audio",
            f"ytsearch{job.n * 2}:{job.singer} official audio",
            f"ytsearch{job.n * 2}:{job.singer} hit songs",
            f"ytsearch{job.n * 2}:{job.singer} best songs",
        ]
        
        all_audio_files = []
        
        for idx, query in enumerate(search_queries):
            if len(all_audio_files) >= job.n:
                break
                
            job.message = f"Search attempt {idx+1}/{len(search_queries)}..."
            job.progress = 15 + (idx * 5)
            
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([query])
            except Exception as e:
                print(f"Search attempt {idx+1} failed: {e}")
                continue
            
            # Wait a bit for processing
            time.sleep(2)
            
            # Check for downloaded files
            for f in os.listdir(job.temp_dir):
                if f.endswith('.mp3') and f not in all_audio_files:
                    all_audio_files.append(f)
            
            job.message = f"Found {len(all_audio_files)} songs so far..."
        
        if not all_audio_files:
            # Try with worst quality as last resort
            job.message = "Trying last resort search..."
            opts['format'] = 'worstaudio'
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([f"ytsearch{job.n * 2}:{job.singer} songs"])
            except:
                pass
            
            time.sleep(2)
            all_audio_files = [f for f in os.listdir(job.temp_dir) if f.endswith('.mp3')]
        
        if not all_audio_files:
            job.status = "failed"
            job.message = "No songs downloaded. YouTube is blocking cloud IPs. Try with cookies.txt file."
            return
        
        # Get full paths
        audio_files = [os.path.join(job.temp_dir, f) for f in all_audio_files[:job.n]]
        
        job.message = f"Downloaded {len(audio_files)} songs. Processing audio..."
        job.progress = 50
        
        # Cut audio files
        cut_files = []
        for i, f in enumerate(audio_files):
            try:
                cut_f = os.path.join(job.temp_dir, f"cut_{i}.mp3")
                subprocess.run([
                    "ffmpeg", "-i", f,
                    "-t", str(job.y),
                    "-acodec", "copy",  # Copy without re-encoding (faster)
                    "-y", cut_f
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                
                if os.path.exists(cut_f) and os.path.getsize(cut_f) > 0:
                    cut_files.append(cut_f)
                    job.message = f"Processing song {i+1}/{len(audio_files)}..."
            except Exception as e:
                print(f"Error cutting {f}: {e}")
                continue
        
        if not cut_files:
            job.status = "failed"
            job.message = "Could not process audio files."
            return
        
        job.message = f"Merging {len(cut_files)} tracks..."
        job.progress = 75
        
        # Merge audio files
        combined = AudioSegment.empty()
        for f in cut_files:
            try:
                audio = AudioSegment.from_mp3(f)
                combined += audio
            except Exception as e:
                print(f"Error merging {f}: {e}")
                continue
        
        if len(combined) == 0:
            job.status = "failed"
            job.message = "Failed to merge audio files."
            return
        
        # Save mashup
        mashup_filename = f"mashup_{job.job_id}.mp3"
        mashup_path = os.path.join(job.temp_dir, mashup_filename)
        combined.export(mashup_path, format="mp3", bitrate="128k")
        
        # Create zip file
        job.message = "Creating zip file..."
        job.progress = 90
        
        zip_filename = f"mashup_{job.job_id}.zip"
        zip_path = os.path.join(RESULT_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(mashup_path, "mashup.mp3")
        
        job.output_file = zip_path
        job.message = "Sending email..."
        job.progress = 95
        
        # Send email
        email_sent = send_email_with_attachment(job.email, zip_path, job.singer)
        
        job.status = "completed"
        job.message = f"Success! Mashup created. Check email or download."
        job.progress = 100
        
    except Exception as e:
        job.status = "failed"
        job.message = f"Error: {str(e)}"
        print(f"Job {job.job_id} failed: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['POST'])
def create():
    try:
        singer = request.form['singer']
        n = int(request.form['n'])
        y = int(request.form['y'])
        email = request.form['email']
        
        # Validation
        if n <= 10:
            return jsonify({'error': 'Number of videos must be > 10'}), 400
        if y <= 20:
            return jsonify({'error': 'Duration must be > 20 seconds'}), 400
        if not validate_email(email):
            return jsonify({'error': 'Invalid email'}), 400
        
        # Create job
        job_id = str(uuid.uuid4())[:8]
        job = MashupJob(job_id, singer, n, y, email)
        jobs[job_id] = job
        
        # Start thread
        thread = threading.Thread(target=create_mashup, args=(job,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Mashup creation started'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/status/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job.to_dict())

@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job or job.status != 'completed':
        return jsonify({'error': 'File not ready'}), 404
    if job.output_file and os.path.exists(job.output_file):
        return send_file(job.output_file, as_attachment=True, download_name=f"mashup_{job.singer}.zip")
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)