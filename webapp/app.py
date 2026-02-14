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

# Email configuration - APNA EMAIL DAALO
EMAIL_ADDRESS = "skaushal1007@gmail.com"      # <-- Apna email
EMAIL_PASSWORD = "xrqm mnta vysr sczv"         # <-- App password
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
        return False

def create_mashup(job):
    job.status = "processing"
    job.message = "Starting download..."
    job.progress = 10
    
    try:
        job.temp_dir = tempfile.mkdtemp(dir=UPLOAD_FOLDER)
        
        job.message = f"Downloading {job.n} songs by {job.singer}..."
        job.progress = 20
        
        opts = {
            'format': 'bestaudio/best',
            'cookiefile': 'cookies.txt',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': os.path.join(job.temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        # Search and download
        search_query = f"ytsearch{job.n}:{job.singer} song"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([search_query])
        
        # Get downloaded files
        audio_files = []
        for f in os.listdir(job.temp_dir):
            if f.endswith('.mp3'):
                audio_files.append(os.path.join(job.temp_dir, f))
        
        if not audio_files:
            job.status = "failed"
            job.message = "No songs downloaded. Try another singer."
            return
        
        job.message = f"Downloaded {len(audio_files)} songs. Cutting audio..."
        job.progress = 50
        
        # Cut audio files
        cut_files = []
        for i, f in enumerate(audio_files[:job.n]):
            cut_f = os.path.join(job.temp_dir, f"cut_{i}.mp3")
            subprocess.run([
                "ffmpeg", "-i", f,
                "-t", str(job.y),
                "-y", cut_f
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cut_files.append(cut_f)
        
        job.message = "Merging audio tracks..."
        job.progress = 75
        
        # Merge audio files
        combined = AudioSegment.empty()
        for f in cut_files:
            audio = AudioSegment.from_mp3(f)
            combined += audio
        
        # Save mashup
        mashup_path = os.path.join(job.temp_dir, f"mashup_{job.job_id}.mp3")
        combined.export(mashup_path, format="mp3")
        
        # Create zip
        job.message = "Creating zip file..."
        job.progress = 90
        
        zip_path = os.path.join(RESULT_FOLDER, f"mashup_{job.job_id}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(mashup_path, "mashup.mp3")
        
        job.output_file = zip_path
        job.message = "Sending email..."
        job.progress = 95
        
        # Send email
        send_email_with_attachment(job.email, zip_path, job.singer)
        
        job.status = "completed"
        job.message = f"Success! Check your email: {job.email}"
        job.progress = 100
        
    except Exception as e:
        job.status = "failed"
        job.message = f"Error: {str(e)}"

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

#@app.route('/download/<job_id>')
#def download(job_id):
#    job = jobs.get(job_id)
#    if not job or job.status != 'completed':
#        return jsonify({'error': 'File not ready'}), 404
#    return send_file(job.output_file, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)