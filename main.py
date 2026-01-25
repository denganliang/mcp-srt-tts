import os
import re
import sys
import io
import functools
# Redirect all print to stderr to avoid interfering with MCP protocol on stdout
print = functools.partial(print, file=sys.stderr)
import argparse
import requests
import soundfile as sf
import numpy as np
from typing import Optional, List

# --- TTSEngine Class ---
class TTSEngine:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def synthesize(self, text: str, filename: str, emo_text: Optional[str] = None,
                   emo_vector: Optional[List[float]] = None) -> bytes:
        url = f"{self.base_url}/v2/synthesize"
        payload = {"text": text, "audio_path": filename}
        if emo_vector is not None:
            payload["emo_vector"] = emo_vector
        elif emo_text:
            payload["emo_text"] = emo_text

        try:
            resp = requests.post(url, json=payload, timeout=300)
            if resp.status_code != 200:
                print(f"Server Error ({resp.status_code}): {resp.text}")
                return None
            return resp.content
        except Exception as e:
            print(f"Request Error: {e}")
            return None

    def check_audio_exists(self, filename: str) -> bool:
        url = f"{self.base_url}/v1/check/audio"
        params = {"file_name": filename}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("exists", False)
        except:
            return False

    def upload_audio(self, file_path: str, full_path=None) -> dict:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        url = f"{self.base_url}/v1/upload_audio"
        with open(file_path, "rb") as f:
            # Prepare files/data
            # Note: The server expects 'full_path' in data if identifying by path
            files = {"audio": (os.path.basename(file_path), f, "audio/wav")}
            data = {}
            if full_path:
                data["full_path"] = full_path

            resp = requests.post(url, files=files, data=data, timeout=30)
            resp.raise_for_status()
            return resp.json()

# --- SRT Parsing ---
def parse_time(time_str):
    """Converts SRT time string (00:00:00,000) to seconds (float)"""
    try:
        h, m, s = time_str.split(':')
        s, ms = s.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    except ValueError:
        return 0.0

def parse_srt(srt_path):
    if not os.path.exists(srt_path):
        print(f"Error: SRT file not found: {srt_path}")
        return []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by double newlines (standard SRT block separator)
    # Handle both \n\n and \r\n\r\n
    blocks = re.split(r'\n\s*\n', content.strip())
    segments = []

    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue

        # Try to find the timestamp line (contains -->)
        time_line_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line_idx = i
                break

        if time_line_idx == -1:
            continue

        time_line = lines[time_line_idx]
        text_lines = lines[time_line_idx+1:]
        text = " ".join(text_lines).strip()

        try:
            start_str, end_str = time_line.split(' --> ')
            start_time = parse_time(start_str.strip())
            end_time = parse_time(end_str.strip())
        except ValueError:
            print(f"Skipping malformed time line: {time_line}")
            continue

        segments.append({
            'start': start_time,
            'end': end_time,
            'text': text
        })
    return segments

# --- Main Logic ---
def srt_to_audio(base_url, srt_file, ref_audio, output_file="output.wav"):
    print("="*50)
    print(f"SRT to Audio Converter")
    print(f"Server: {base_url}")
    print(f"SRT:    {srt_file}")
    print(f"Ref:    {ref_audio}")
    print("="*50)

    engine = TTSEngine(base_url)

    # 1. Upload Reference Audio
    ref_audio_abs = os.path.abspath(ref_audio)

    # Check if reference audio exists locally
    if not os.path.exists(ref_audio_abs):
        print(f"Error: Reference audio file not found locally: {ref_audio_abs}")
        sys.exit(1)

    print(f"Checking/Uploading reference audio...")
    try:
        # Always try to upload/check to ensure server has it
        # We use the absolute path as the key/filename on server side as per original logic
        if not engine.check_audio_exists(ref_audio_abs):
            print("  -> Uploading...")
            engine.upload_audio(ref_audio_abs, full_path=ref_audio_abs)
        else:
            print("  -> Exists on server.")
    except Exception as e:
        print(f"Warning: Issue verifying reference audio on server: {e}")
        print("Attempting to proceed anyway...")

    # 2. Parse SRT
    print(f"Parsing SRT file...")
    segments = parse_srt(srt_file)
    if not segments:
        print("No valid segments found in SRT.")
        sys.exit(1)

    # Calculate total duration needed
    last_end_time = max(s['end'] for s in segments)
    total_duration = last_end_time + 1.0
    print(f"Found {len(segments)} segments. Total timeline: {total_duration:.2f}s")

    # 3. Process segments
    final_audio = None
    sample_rate = 0

    success_count = 0
    next_available_sample = 0

    for i, seg in enumerate(segments):
        text = seg['text']
        start_time = seg['start']
        end_time = seg['end']

        # Clean text
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if not clean_text:
            continue

        print(f"[{i+1}/{len(segments)}] {start_time:.2f}s -> {clean_text[:40]}...")

        # Call TTS
        audio_bytes = engine.synthesize(clean_text, ref_audio_abs)

        if not audio_bytes:
            print("  -> Failed to synthesize, skipping.")
            continue

        # Convert bytes to numpy array
        try:
            with io.BytesIO(audio_bytes) as bio:
                data, sr = sf.read(bio)
        except Exception as e:
            print(f"  -> Error reading audio data: {e}")
            continue

        # Apply fade in/out to avoid clicks and stiff transitions
        fade_duration = 0.05 # 50ms
        fade_samples = int(fade_duration * sr)
        if fade_samples > 0 and fade_samples * 2 < len(data):
            fade_curve = np.linspace(0, 1, fade_samples, dtype=np.float32)
            if len(data.shape) > 1:
                fade_curve = fade_curve[:, np.newaxis]

            # Fade In
            data[:fade_samples] = data[:fade_samples] * fade_curve
            # Fade Out
            data[-fade_samples:] = data[-fade_samples:] * fade_curve[::-1]

        # Initialize final buffer if first time
        if final_audio is None:
            sample_rate = sr
            total_samples = int(total_duration * sample_rate)
            # Check channels
            channels = 1
            if len(data.shape) > 1:
                channels = data.shape[1]
                final_audio = np.zeros((total_samples, channels), dtype=np.float32)
            else:
                final_audio = np.zeros(total_samples, dtype=np.float32)
            print(f"  -> Initialized audio buffer: {sample_rate}Hz, {channels}ch")

        # Handle sample rate mismatch
        if sr != sample_rate:
            print(f"  -> Warning: Sample rate mismatch ({sr} vs {sample_rate}). Skipping.")
            continue

        # Calculate insertion point
        start_sample = int(start_time * sample_rate)

        # Auto-shift to avoid overlap
        if start_sample < next_available_sample:
            shift_sec = (next_available_sample - start_sample) / sample_rate
            print(f"  -> Adjusting timing: +{shift_sec:.2f}s to avoid overlap")
            start_sample = next_available_sample

        end_sample = start_sample + len(data)
        next_available_sample = end_sample

        # Handle overflow (extend buffer)
        if end_sample > len(final_audio):
             new_len = int(end_sample + sample_rate * 10)
             if len(final_audio.shape) > 1:
                new_arr = np.zeros((new_len, final_audio.shape[1]), dtype=np.float32)
             else:
                new_arr = np.zeros(new_len, dtype=np.float32)
             new_arr[:len(final_audio)] = final_audio
             final_audio = new_arr

        # Add audio to buffer
        if len(final_audio.shape) > 1 and len(data.shape) == 1:
             data = np.column_stack((data, data))

        final_audio[start_sample:end_sample] += data
        success_count += 1

    # 4. Save Output
    if final_audio is not None and success_count > 0:
        print(f"\nSaving result to {output_file}...")

        # Trim unused buffer (silence at the end)
        if next_available_sample > 0 and next_available_sample < len(final_audio):
             final_audio = final_audio[:next_available_sample]

        # Normalize to prevent clipping from mixing
        max_val = np.max(np.abs(final_audio))
        if max_val > 1.0:
            print(f"  -> Normalizing volume (peak {max_val:.2f})...")
            final_audio = final_audio / max_val

        sf.write(output_file, final_audio, sample_rate)
        print("Success!")
    else:
        print("No audio generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert SRT subtitles to Audio using Remote TTS")
    parser.add_argument("url", help="HTTP Service URL (e.g. http://127.0.0.1:8000)")
    parser.add_argument("srt", help="Path to SRT subtitle file")
    parser.add_argument("ref_audio", help="Path to reference audio file (timbre)")
    parser.add_argument("-o", "--output", default="output.wav", help="Output file path (default: output.wav)")

    args = parser.parse_args()

    srt_to_audio(args.url, args.srt, args.ref_audio, args.output)
