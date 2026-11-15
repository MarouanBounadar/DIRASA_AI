import os
import re
import subprocess
import time
import threading
import static_ffmpeg

try:
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"static_ffmpeg setup note: {e}")

from config import APP_DIR
DOWNLOADS_DIR = os.path.join(APP_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def get_audio_input_device() -> str:
    """
    Detects the primary microphone name on Windows using FFmpeg dshow.
    Returns the device name or alternative device string.
    """
    try:
        cmd = ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        output = res.stderr

        # Look for audio devices
        # Example pattern: "Microphone Name" (audio)
        audio_matches = re.findall(r'"([^"]+)"\s+\(audio\)', output)
        if audio_matches:
            # Prefer real hardware microphones over virtual cables
            for name in audio_matches:
                if "Virtual" not in name and "Stereo Mix" not in name:
                    return f"audio={name}"
            return f"audio={audio_matches[0]}"
        
        # Look for alternative name: Alternative name "@device_cm_..."
        alt_matches = re.findall(r'Alternative name\s+"(@device_cm_[^"]+)"', output)
        if alt_matches:
            return f"audio={alt_matches[0]}"
    except Exception as e:
        print(f"Device discovery note: {e}")

    # Fallback default
    return "audio=default"

class AudioRecorder:
    def __init__(self):
        self.process = None
        self.start_time = None
        self.is_recording = False
        self.output_path = None
        self.device = None

    def start(self, output_filename: str = None) -> str:
        """
        Starts recording audio in the background directly from laptop/PC microphone.
        """
        if self.is_recording:
            return self.output_path

        timestamp = int(time.time())
        if not output_filename:
            output_filename = f"enregistrement_amphi_{timestamp}.mp3"

        self.output_path = os.path.join(DOWNLOADS_DIR, output_filename)
        self.device = get_audio_input_device()

        # Command: record directly to 32kbps mono 16kHz MP3 for instant AI analysis
        cmd = [
            "ffmpeg", "-y", "-f", "dshow",
            "-i", self.device,
            "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-b:a", "32k",
            self.output_path
        ]

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.is_recording = True
        self.start_time = time.time()
        return self.output_path

    def stop(self) -> str:
        """
        Stops the recording process gracefully and finalizes the audio file.
        """
        if not self.is_recording:
            return self.output_path

        try:
            if self.process and self.process.poll() is None:
                # Send 'q' to ffmpeg to stop gracefully
                try:
                    self.process.communicate(input=b'q', timeout=3)
                except Exception:
                    self.process.terminate()
                    time.sleep(0.5)
        except Exception as e:
            print(f"Error stopping recorder: {e}")

        self.is_recording = False
        self.process = None
        return self.output_path

    def get_elapsed_seconds(self) -> int:
        if not self.is_recording or not self.start_time:
            return 0
        return int(time.time() - self.start_time)
