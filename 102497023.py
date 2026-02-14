import sys, os, subprocess, shutil, tempfile
import yt_dlp
from pydub import AudioSegment

class YouTubeMashup:
    def __init__(self, singer, n, y, output):
        self.singer = singer
        self.n = n
        self.y = y
        self.output = output
        self.temp_dir = tempfile.mkdtemp()

    def download_logic(self):
        print(f"Step 1: Downloading {self.n} unique songs by {self.singer}...")
        opts = {
            # 'ba/b' is the secret—it grabs audio OR the whole video if audio is hidden
            'format': 'ba/b',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'retries': 10,           # If the connection drops, try again 10 times
            'fragment_retries': 10,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128', 
            }],
            'outtmpl': os.path.join(self.temp_dir, 'song_%(playlist_index)s_%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'max_downloads': self.n, 
            'ignoreerrors': True,
        }

        search_query = f"ytsearch{self.n * 2}:{self.singer} official audio -shorts -vlog"
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                ydl.download([search_query])
            except Exception as e:
                if "Maximum number of downloads reached" not in str(e):
                    print(f"Note: {e}")

    def run(self):
        try:
            self.download_logic()
            
            audio_files = [os.path.join(self.temp_dir, f) for f in os.listdir(self.temp_dir) if f.endswith('.mp3')]
            
            if not audio_files:
                print("Error: No songs downloaded. Please switch to Mobile Hotspot and try again.")
                return

            print(f"Step 2: Rapidly cutting first {self.y}s...")
            cut_files = []
            for i, f in enumerate(audio_files):
                cut_f = os.path.join(self.temp_dir, f"cut_{i}.mp3")
                subprocess.run(["ffmpeg", "-y", "-i", f, "-t", str(self.y), "-c", "copy", cut_f], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cut_files.append(cut_f)

            print("Step 3: Merging all tracks...")
            final_mashup = AudioSegment.empty()
            for f in cut_files:
                final_mashup += AudioSegment.from_file(f)
            
            final_mashup.export(self.output, format="mp3")
            print(f"\nSUCCESS! Created: {self.output}")

        except Exception as e:
            print(f"Error: {e}") 
        finally:
            shutil.rmtree(self.temp_dir)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python <RollNumber>.py <SingerName> <N> <Y> <Output>")
        sys.exit(1)

    try:
        mashup = YouTubeMashup(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
        mashup.run()
    except Exception as e:
        print(f"Input Error: {e}")