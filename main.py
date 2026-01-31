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

# --- TTSEngine Class (保持不变) ---
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
            files = {"audio": (os.path.basename(file_path), f, "audio/wav")}
            data = {}
            if full_path:
                data["full_path"] = full_path
            resp = requests.post(url, files=files, data=data, timeout=30)
            resp.raise_for_status()
            return resp.json()

# --- SRT Parsing & Utils (保持不变) ---
def parse_time(time_str):
    try:
        h, m, s = time_str.split(':')
        s, ms = s.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    except ValueError:
        return 0.0

def format_time(seconds):
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

def save_srt(segments, path):
    with open(path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments):
            f.write(f"{i+1}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

def parse_srt(srt_path):
    if not os.path.exists(srt_path):
        print(f"Error: SRT file not found: {srt_path}")
        return []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\n\s*\n', content.strip())
    segments = []
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 2: continue
        time_line_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line_idx = i
                break
        if time_line_idx == -1: continue
        time_line = lines[time_line_idx]
        text_lines = lines[time_line_idx+1:]
        text = " ".join(text_lines).strip()
        try:
            start_str, end_str = time_line.split(' --> ')
            segments.append({'start': parse_time(start_str), 'end': parse_time(end_str), 'text': text})
        except: continue
    return segments

# --- Main Logic ---
def srt_to_audio(base_url, srt_file, ref_audio, output_file="output.wav"):
    print("="*50)
    print(f"SRT to Audio (Compact Mode)")
    print("="*50)

    engine = TTSEngine(base_url)
    ref_audio_abs = os.path.abspath(ref_audio)

    if not os.path.exists(ref_audio_abs):
        print(f"Error: Ref audio not found: {ref_audio_abs}")
        sys.exit(1)

    # 1. 确保服务器有参考音频
    try:
        if not engine.check_audio_exists(ref_audio_abs):
            engine.upload_audio(ref_audio_abs, full_path=ref_audio_abs)
    except Exception as e:
        print(f"Warning: Upload issue: {e}")

    # 2. 解析 SRT
    segments = parse_srt(srt_file)
    if not segments:
        print("No segments found.")
        sys.exit(1)

    # 3. 处理段落
    final_audio_list = []  # 改用列表存储，最后一次性合并，更高效且不限制长度
    sample_rate = 0
    generated_segments = []
    current_time_cursor = 0.0
    
    # 段落之间的硬性静音间隔（秒），方案A建议设为 0.1 ~ 0.3 使其自然
    gap_duration = 0.2 

    for i, seg in enumerate(segments):
        text = seg['text']
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if not clean_text: continue

        print(f"[{i+1}/{len(segments)}] Synthesizing: {clean_text[:30]}...")
        audio_bytes = engine.synthesize(clean_text, ref_audio_abs)

        if not audio_bytes:
            print("  -> Failed, skipping.")
            continue

        try:
            with io.BytesIO(audio_bytes) as bio:
                data, sr = sf.read(bio)
                data = data.astype(np.float32)
        except Exception as e:
            print(f"  -> Audio read error: {e}")
            continue

        if sample_rate == 0:
            sample_rate = sr
        elif sr != sample_rate:
            print(f"  -> SR mismatch ({sr} vs {sample_rate}), skipping.")
            continue

        # 应用淡入淡出 (防止切片边缘咔哒声)
        fade_samples = int(0.05 * sample_rate)
        if len(data) > fade_samples * 2:
            fade_curve = np.linspace(0, 1, fade_samples, dtype=np.float32)
            if len(data.shape) > 1: fade_curve = fade_curve[:, np.newaxis]
            data[:fade_samples] *= fade_curve
            data[-fade_samples:] *= fade_curve[::-1]

        # 记录新 SRT 的时间戳（紧凑模式）
        duration = len(data) / sample_rate
        generated_segments.append({
            'start': current_time_cursor,
            'end': current_time_cursor + duration,
            'text': text
        })

        # 添加到最终列表并更新游标
        final_audio_list.append(data)
        
        # 添加一小段静音 Gap
        gap_samples = int(gap_duration * sample_rate)
        if gap_samples > 0:
            shape = (gap_samples, data.shape[1]) if len(data.shape) > 1 else (gap_samples,)
            final_audio_list.append(np.zeros(shape, dtype=np.float32))
            current_time_cursor += gap_duration

        current_time_cursor += duration

    # 4. 合并并保存
    if final_audio_list:
        print(f"\nConcatenating {len(final_audio_list)} buffers...")
        combined_audio = np.concatenate(final_audio_list, axis=0)

        # 归一化
        max_val = np.max(np.abs(combined_audio))
        if max_val > 1.0:
            combined_audio /= max_val

        sf.write(output_file, combined_audio, sample_rate)
        
        output_srt = os.path.splitext(output_file)[0] + ".srt"
        save_srt(generated_segments, output_srt)
        print(f"Success! Output: {output_file} and {output_srt}")
    else:
        print("No audio was generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert SRT to Compact Audio")
    parser.add_argument("url", help="Server URL")
    parser.add_argument("srt", help="SRT file")
    parser.add_argument("ref_audio", help="Reference audio")
    parser.add_argument("-o", "--output", default="output.wav", help="Output path")
    args = parser.parse_args()

    srt_to_audio(args.url, args.srt, args.ref_audio, args.output)