
from flask import Flask, render_template, request, jsonify, send_file
import threading
import os
import sys
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
ALLOWED_EXTENSIONS = {'mp3'}

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

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
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_email_with_attachment(recipient_email, zip_filepath, singer_name):
    """Send email with the zip file attachment"""
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

        # Attach the zip file
        with open(zip_filepath, 'rb') as attachment:
            part = MIMEBase('application', 'zip')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(zip_filepath)}')
            msg.attach(part)

        # Send email
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
    """Background task to create mashup"""
    job.status = "processing"
    job.message = "Starting download..."
    job.progress = 10
    
    try:
        # Create temp directory for this job
        job.temp_dir = tempfile.mkdtemp(dir=UPLOAD_FOLDER)
        
        # Download songs
        job.message = f"Downloading {job.n} songs by {job.singer}..."
        job.progress = 20
        
        # yt-dlp options
        opts = {
            'format': 'ba/b',
            'cookiefile': 'cookies.txt', 
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'retries': 10,
            'fragment_retries': 10,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': os.path.join(job.temp_dir, 'song_%(playlist_index)s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'max_downloads': job.n,
            'ignoreerrors': True,
        }
        
        search_query = f"ytsearch{job.n * 2}:{job.singer} official audio"
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([search_query])
        
        # Get downloaded files
        audio_files = [os.path.join(job.temp_dir, f) for f in os.listdir(job.temp_dir) 
                      if f.endswith('.mp3')]
        
        if not audio_files:
            job.status = "failed"
            job.message = "No songs were downloaded. Please try again."
            job.progress = 0
            return
        
        job.message = f"Downloaded {len(audio_files)} songs. Cutting audio..."
        job.progress = 50
        
        # Cut audio files
        cut_files = []
        for i, f in enumerate(audio_files[:job.n]):
            cut_f = os.path.join(job.temp_dir, f"cut_{i}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", f, 
                "-t", str(job.y), 
                "-c", "copy", cut_f
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cut_files.append(cut_f)
        
        job.message = "Merging audio tracks..."
        job.progress = 75
        
        # Merge audio files
        final_mashup = AudioSegment.empty()
        for f in cut_files:
            final_mashup += AudioSegment.from_file(f)
        
        # Save mashup
        mashup_filename = f"mashup_{job.job_id}.mp3"
        mashup_path = os.path.join(job.temp_dir, mashup_filename)
        final_mashup.export(mashup_path, format="mp3")
        
        # Create zip file
        job.message = "Creating zip file..."
        job.progress = 90
        
        zip_filename = f"mashup_{job.job_id}.zip"
        zip_path = os.path.join(RESULT_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(mashup_path, mashup_filename)
            # Also add the cut files
            for i, f in enumerate(cut_files):
                zipf.write(f, f"segment_{i+1}.mp3")
        
        job.output_file = zip_path
        job.message = "Sending email..."
        job.progress = 95
        
        # Send email
        email_sent = send_email_with_attachment(job.email, zip_path, job.singer)
        
        if email_sent:
            job.status = "completed"
            job.message = f"Mashup created successfully and sent to {job.email}"
        else:
            job.status = "completed"
            job.message = f"Mashup created but email failed. File saved as {zip_filename}"
        
        job.progress = 100
        
    except Exception as e:
        job.status = "failed"
        job.message = f"Error: {str(e)}"
        print(f"Job {job.job_id} failed: {e}")
    finally:
        # Cleanup temp directory
        if job.temp_dir and os.path.exists(job.temp_dir):
            shutil.rmtree(job.temp_dir)

@app.route('/')
def index():
    """Home page with form"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Mashup Web Service</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                color: #666;
                font-weight: bold;
            }
            input[type="text"],
            input[type="number"],
            input[type="email"] {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-size: 16px;
                box-sizing: border-box;
            }
            input[type="submit"] {
                background-color: #4CAF50;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
                width: 100%;
            }
            input[type="submit"]:hover {
                background-color: #45a049;
            }
            .info {
                background-color: #e7f3fe;
                border-left: 4px solid #2196F3;
                padding: 10px;
                margin-bottom: 20px;
            }
            .error {
                color: red;
                font-size: 14px;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎵 YouTube Mashup Creator</h1>
            
            <div class="info">
                <strong>Note:</strong> 
                <ul>
                    <li>Number of videos must be > 10</li>
                    <li>Duration must be > 20 seconds</li>
                    <li>You'll receive the mashup via email</li>
                </ul>
            </div>
            
            <form action="/create" method="post">
                <div class="form-group">
                    <label for="singer">Singer Name:</label>
                    <input type="text" id="singer" name="singer" required 
                           placeholder="e.g., Sharry Maan, Asha Bhosle">
                </div>
                
                <div class="form-group">
                    <label for="n">Number of Videos (N > 10):</label>
                    <input type="number" id="n" name="n" min="11" required 
                           placeholder="e.g., 20">
                </div>
                
                <div class="form-group">
                    <label for="y">Duration per Video (Y > 20 seconds):</label>
                    <input type="number" id="y" name="y" min="21" required 
                           placeholder="e.g., 30">
                </div>
                
                <div class="form-group">
                    <label for="email">Email Address:</label>
                    <input type="email" id="email" name="email" required 
                           placeholder="your@email.com">
                </div>
                
                <input type="submit" value="Create Mashup">
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/create', methods=['POST'])
def create_mashup_route():
    """Handle mashup creation request"""
    try:
        singer = request.form['singer']
        n = int(request.form['n'])
        y = int(request.form['y'])
        email = request.form['email']
        
        # Validate inputs
        if n <= 10:
            return jsonify({'error': 'Number of videos must be greater than 10'}), 400
        
        if y <= 20:
            return jsonify({'error': 'Duration must be greater than 20 seconds'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email address'}), 400
        
        # Create job
        job_id = str(uuid.uuid4())[:8]
        job = MashupJob(job_id, singer, n, y, email)
        jobs[job_id] = job
        
        # Start background thread
        thread = threading.Thread(target=create_mashup, args=(job,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Mashup creation started',
            'status_url': f'/status/{job_id}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/status/<job_id>')
def get_status(job_id):
    """Get job status"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job.to_dict())

@app.route('/download/<job_id>')
def download_mashup(job_id):
    """Download the mashup file"""
    job = jobs.get(job_id)
    if not job or job.status != 'completed':
        return jsonify({'error': 'File not ready'}), 404
    
    if job.output_file and os.path.exists(job.output_file):
        return send_file(job.output_file, as_attachment=True)
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/docs')
def api_docs():
    """API documentation"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mashup API Documentation</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.6;
            }
            .endpoint {
                background-color: #f4f4f4;
                padding: 10px;
                margin: 10px 0;
                border-left: 4px solid #4CAF50;
            }
            code {
                background-color: #eef;
                padding: 2px 5px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <h1>Mashup API Documentation</h1>
        
        <h2>Endpoints:</h2>
        
        <div class="endpoint">
            <strong>POST /create</strong> - Create a new mashup<br>
            Parameters: singer (string), n (int), y (int), email (string)
        </div>
        
        <div class="endpoint">
            <strong>GET /status/&lt;job_id&gt;</strong> - Get job status
        </div>
        
        <div class="endpoint">
            <strong>GET /download/&lt;job_id&gt;</strong> - Download completed mashup
        </div>
        
        <p><a href="/">← Back to Home</a></p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)