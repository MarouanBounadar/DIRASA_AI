import os
import re
import shutil
import time
import subprocess
import xml.etree.ElementTree as ET
import requests
import yt_dlp
import static_ffmpeg

from tools import extract_video_slides
try:
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"static_ffmpeg setup warning: {e}")

from config import APP_DIR
DOWNLOADS_DIR = os.path.join(APP_DIR, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def clean_filename(filename: str) -> str:
    """Removes invalid characters for Windows file systems."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def is_local_file(path_or_url: str) -> bool:
    """Checks if the given string is a valid local file path."""
    return os.path.isfile(path_or_url)

def extract_google_drive_id(url: str) -> str | None:
    """Extracts the file ID from a Google Drive share link."""
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def download_file_with_resume(url: str, dest_path: str, progress_callback=None, label: str = "Téléchargement", max_retries: int = 8) -> bool:
    """
    Downloads a file over HTTP/HTTPS with automatic resume (Range requests) and retry on network drop.
    Handles IncompleteRead, ChunkedEncodingError, Timeouts, and server disconnects gracefully.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    total_size = 0
    accept_ranges = False
    try:
        head_res = requests.head(url, headers=headers, allow_redirects=True, timeout=15)
        total_size = int(head_res.headers.get('content-length', 0))
        accept_ranges = 'bytes' in head_res.headers.get('accept-ranges', '').lower() or head_res.status_code == 206
    except Exception as e:
        print(f"HEAD check note: {e}")

    # If already downloaded and complete, return immediately
    if total_size > 0 and os.path.exists(dest_path) and os.path.getsize(dest_path) >= total_size:
        return True

    downloaded = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

    for attempt in range(1, max_retries + 1):
        if total_size > 0 and downloaded >= total_size:
            return True

        req_headers = headers.copy()
        mode = 'wb'
        if downloaded > 0 and (accept_ranges or total_size > 0):
            req_headers['Range'] = f'bytes={downloaded}-'
            mode = 'ab'
            msg = f"{label} (Reprise à {downloaded // (1024*1024)} Mo / {total_size // (1024*1024)} Mo - essai {attempt}/{max_retries})..."
        else:
            downloaded = 0
            mode = 'wb'
            msg = f"{label} (Connexion - essai {attempt}/{max_retries})..."

        if progress_callback:
            progress_callback(0.15, msg)

        try:
            with requests.get(url, headers=req_headers, stream=True, timeout=30) as r:
                # If server doesn't support Range, restart from 0
                if downloaded > 0 and r.status_code == 200:
                    downloaded = 0
                    mode = 'wb'

                if r.status_code not in (200, 206):
                    time.sleep(2)
                    continue

                if total_size == 0:
                    total_size = int(r.headers.get('content-length', 0))

                with open(dest_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                percent = min(0.8, 0.1 + (downloaded / total_size) * 0.7)
                                pct_int = int((downloaded / total_size) * 100)
                                progress_callback(percent, f"{label}: {pct_int}% ({downloaded // (1024*1024)} / {total_size // (1024*1024)} Mo)")

            if total_size == 0 or downloaded >= total_size:
                return True

        except Exception as e:
            print(f"Network interruption during download ({type(e).__name__}): {e}. Retrying with resume...")
            downloaded = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
            time.sleep(2)

    return total_size == 0 or (os.path.exists(dest_path) and os.path.getsize(dest_path) >= total_size)

def extract_bbb_info(url: str):
    """
    Detects BigBlueButton playback presentation URLs and extracts base_url and meeting_id.
    """
    match = re.search(r'(https?://[^/]+)/playback/presentation/(?:2\.[0-9]+/)?([a-f0-9-]+)', url)
    if match:
        base_url = match.group(1)
        meeting_id = match.group(2)
        return base_url, meeting_id
    return None, None

def download_bigbluebutton(url: str, progress_callback=None) -> dict:
    """
    Downloads audio directly from a BigBlueButton presentation recording.
    """
    base_url, meeting_id = extract_bbb_info(url)
    if not base_url or not meeting_id:
        raise ValueError("Lien BigBlueButton invalide.")

    if progress_callback:
        progress_callback(0.05, "Analyse de la séance BigBlueButton...")

    # Step 1: Read metadata for session title
    meeting_name = "Séance BigBlueButton"
    meta_url = f"{base_url}/presentation/{meeting_id}/metadata.xml"
    try:
        meta_res = requests.get(meta_url, allow_redirects=True, timeout=15)
        if meta_res.status_code == 200:
            root = ET.fromstring(meta_res.text)
            meeting_elem = root.find('.//meeting')
            if meeting_elem is not None and 'name' in meeting_elem.attrib:
                meeting_name = meeting_elem.attrib['name']
    except Exception as e:
        print(f"BBB metadata warning: {e}")

    # Step 2: Find the active audio / webcams stream
    candidates = [
        f"{base_url}/presentation/{meeting_id}/audio/audio.webm",
        f"{base_url}/presentation/{meeting_id}/audio/audio.ogg",
        f"{base_url}/presentation/{meeting_id}/video/webcams.webm",
        f"{base_url}/presentation/{meeting_id}/video/webcams.mp4",
        f"{base_url}/presentation/{meeting_id}/deskshare/deskshare.webm"
    ]
    chosen_url = None
    for c in candidates:
        try:
            head = requests.head(c, allow_redirects=True, timeout=10)
            if head.status_code == 200:
                chosen_url = head.url
                break
        except Exception:
            continue

    if not chosen_url:
        raise RuntimeError("Flux audio BigBlueButton introuvable pour cet enregistrement.")

    # Step 3: Stream download
    final_mp3_path = os.path.join(DOWNLOADS_DIR, f"bbb_{meeting_id}.mp3")

    # If already downloaded and converted, reuse it immediately!
    if os.path.exists(final_mp3_path) and os.path.getsize(final_mp3_path) > 1024 * 1024:
        size_mb = os.path.getsize(final_mp3_path) / (1024 * 1024)
        if progress_callback:
            progress_callback(1.0, f"Enregistrement déjà en cache local ({size_mb:.1f} Mo)")
        # Check if slides already cached or extract
        slides_dir = os.path.join(DOWNLOADS_DIR, f"slides_{meeting_id}")
        slides = []
        if os.path.exists(slides_dir):
            slides = [os.path.join(slides_dir, f) for f in os.listdir(slides_dir) if f.endswith('.jpg')]
        if not slides:
            try:
                deskshare_url = f"{base_url}/presentation/{meeting_id}/deskshare/deskshare.webm"
                target_video = deskshare_url if requests.head(deskshare_url, allow_redirects=True, timeout=5).status_code == 200 else chosen_url
                slides = extract_video_slides(target_video, slides_dir, count=4)
            except Exception:
                pass

        return {
            "audio_path": final_mp3_path,
            "title": meeting_name,
            "duration": 0,
            "file_size_mb": size_mb,
            "slides": slides
        }

    raw_ext = "webm" if "webm" in chosen_url else "mp4"
    raw_temp_path = os.path.join(DOWNLOADS_DIR, f"bbb_raw_{meeting_id}.{raw_ext}")

    # Robust resumable download with retry on network drop / IncompleteRead
    success = download_file_with_resume(chosen_url, raw_temp_path, progress_callback=progress_callback, label="Téléchargement BigBlueButton")
    if not success or not os.path.exists(raw_temp_path) or os.path.getsize(raw_temp_path) < 1024:
        raise ConnectionError("Le serveur BigBlueButton a interrompu le téléchargement après plusieurs tentatives. Vérifiez votre connexion Internet.")

    # Step 4: Extract audio to MP3 using ffmpeg
    if progress_callback:
        progress_callback(0.85, "Extraction audio MP3 haute fidélité avec FFmpeg...")

    try:
        # Optimized for speech: mono, 16kHz, 32kbps (reduces 2h audio from 80MB to 25MB for 3x faster upload)
        cmd = ["ffmpeg", "-y", "-i", raw_temp_path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "32k", final_mp3_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Remove raw video to save disk space
        if os.path.exists(raw_temp_path):
            os.remove(raw_temp_path)
    except Exception as e:
        print(f"FFmpeg conversion fallback: {e}")
        final_mp3_path = raw_temp_path

    size_mb = os.path.getsize(final_mp3_path) / (1024 * 1024)
    if progress_callback:
        progress_callback(1.0, f"Enregistrement prêt ({size_mb:.1f} Mo)")

    slides_dir = os.path.join(DOWNLOADS_DIR, f"slides_{meeting_id}")
    slides = []
    try:
        deskshare_url = f"{base_url}/presentation/{meeting_id}/deskshare/deskshare.webm"
        target_video = deskshare_url if requests.head(deskshare_url, allow_redirects=True, timeout=5).status_code == 200 else chosen_url
        slides = extract_video_slides(target_video, slides_dir, count=4)
    except Exception:
        pass

    return {
        "audio_path": final_mp3_path,
        "title": meeting_name,
        "duration": 0,
        "file_size_mb": size_mb,
        "slides": slides
    }

def download_google_drive(file_id: str, output_path: str, progress_callback=None) -> str:
    """Downloads a public/shared Google Drive file directly."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(url, stream=True)
    
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
            
    if token:
        url = f"https://drive.google.com/uc?export=download&confirm={token}&id={file_id}"
        response = session.get(url, stream=True)
        
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    percent = downloaded / total_size
                    progress_callback(percent, f"Téléchargement Drive: {int(percent * 100)}% ({downloaded // (1024*1024)} Mo)")
                    
    return output_path

def download_audio(source: str, progress_callback=None) -> dict:
    """
    Downloads or copies the audio from a URL or local file path.
    """
    source = source.strip()
    
    # CASE 1: Local file
    if is_local_file(source):
        if progress_callback:
            progress_callback(0.5, "Chargement du fichier local...")
        base_name = os.path.basename(source)
        title, _ = os.path.splitext(base_name)
        size_mb = os.path.getsize(source) / (1024 * 1024)
        if progress_callback:
            progress_callback(1.0, f"Fichier local prêt ({size_mb:.1f} Mo)")
        return {
            "audio_path": os.path.abspath(source),
            "title": title,
            "duration": 0,
            "file_size_mb": size_mb
        }

    # CASE 2: BigBlueButton Presentation Recording (e.g. SUPMTI, Moodle, Universities)
    if "/playback/presentation/" in source or "/presentation/" in source:
        return download_bigbluebutton(source, progress_callback)

    # CASE 3: Google Drive Link
    drive_id = extract_google_drive_id(source)
    if "drive.google.com" in source and drive_id:
        if progress_callback:
            progress_callback(0.1, "Téléchargement depuis Google Drive...")
        timestamp = int(time.time())
        dest_file = os.path.join(DOWNLOADS_DIR, f"drive_audio_{timestamp}.mp4")
        downloaded_file = download_google_drive(drive_id, dest_file, progress_callback)
        size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
        return {
            "audio_path": downloaded_file,
            "title": f"Séance Google Drive ({drive_id[:8]})",
            "duration": 0,
            "file_size_mb": size_mb
        }

    # CASE 4: YouTube, Zoom, Vimeo, or Direct URL via yt-dlp
    timestamp = int(time.time())
    output_template = os.path.join(DOWNLOADS_DIR, f"recording_{timestamp}_%(id)s.%(ext)s")

    def yt_dlp_hook(d):
        if progress_callback:
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded_bytes = d.get('downloaded_bytes') or 0
                if total_bytes > 0:
                    percent = downloaded_bytes / total_bytes
                    progress_callback(percent, f"Téléchargement: {int(percent * 100)}% ({downloaded_bytes // (1024*1024)} Mo)")
                else:
                    progress_callback(0.3, "Téléchargement du flux audio en cours...")
            elif d['status'] == 'finished':
                progress_callback(0.9, "Traitement et extraction audio...")

    ydl_opts = {
        'format': 'ba[ext=m4a]/ba/b',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'progress_hooks': [yt_dlp_hook],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if progress_callback:
                progress_callback(0.05, "Analyse du lien d'enregistrement...")
            info = ydl.extract_info(source, download=True)
            title = info.get('title', f"Enregistrement_{timestamp}")
            duration = info.get('duration', 0)
            
            # Find the generated mp3 file
            expected_mp3 = ydl.prepare_filename(info)
            base_without_ext, _ = os.path.splitext(expected_mp3)
            final_audio = f"{base_without_ext}.mp3"
            
            if not os.path.exists(final_audio):
                for f in os.listdir(DOWNLOADS_DIR):
                    if str(timestamp) in f and (f.endswith('.mp3') or f.endswith('.m4a') or f.endswith('.webm')):
                        final_audio = os.path.join(DOWNLOADS_DIR, f)
                        break

            size_mb = os.path.getsize(final_audio) / (1024 * 1024) if os.path.exists(final_audio) else 0.0

            if progress_callback:
                progress_callback(1.0, f"Téléchargement terminé ({size_mb:.1f} Mo)")

            return {
                "audio_path": final_audio,
                "title": title,
                "duration": duration,
                "file_size_mb": size_mb
            }
    except Exception as e:
        # Fallback if yt-dlp fails: direct requests stream if it's an audio/video url
        if source.startswith("http://") or source.startswith("https://"):
            try:
                if progress_callback:
                    progress_callback(0.2, "Tentative de téléchargement direct...")
                res = requests.get(source, stream=True, timeout=30)
                ext = "mp3"
                content_type = res.headers.get("content-type", "")
                if "mp4" in content_type:
                    ext = "mp4"
                elif "wav" in content_type:
                    ext = "wav"
                
                dest_file = os.path.join(DOWNLOADS_DIR, f"direct_recording_{timestamp}.{ext}")
                with open(dest_file, "wb") as f:
                    for chunk in res.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            f.write(chunk)
                size_mb = os.path.getsize(dest_file) / (1024 * 1024)
                return {
                    "audio_path": dest_file,
                    "title": f"Séance Directe ({timestamp})",
                    "duration": 0,
                    "file_size_mb": size_mb
                }
            except Exception as direct_err:
                raise RuntimeError(f"Échec du téléchargement du lien: {str(e)} | Direct error: {str(direct_err)}")
        raise RuntimeError(f"Erreur lors du téléchargement: {str(e)}")
