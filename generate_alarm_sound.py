"""
Generates a security alarm WAV sound for ShopGuard AI.
Pattern: 880 Hz beep for 0.4s, silence for 0.1s, repeated 4 times (~2.0s total).
Output: app/src/main/res/raw/security_alarm.wav
Uses only Python standard library (wave + struct + math).
"""
import wave
import struct
import math
import os

SAMPLE_RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM

FREQ = 880          # Hz — alarm tone
BEEP_SECS = 0.4
SILENCE_SECS = 0.1
REPEATS = 4

def generate_tone(freq, duration_secs, sample_rate, amplitude=0.7):
    num_samples = int(sample_rate * duration_secs)
    samples = []
    for i in range(num_samples):
        # Slight fade-in/fade-out (10ms) to avoid click artefacts
        fade_samples = int(sample_rate * 0.01)
        if i < fade_samples:
            env = i / fade_samples
        elif i > num_samples - fade_samples:
            env = (num_samples - i) / fade_samples
        else:
            env = 1.0
        value = int(32767 * amplitude * env * math.sin(2 * math.pi * freq * i / sample_rate))
        samples.append(value)
    return samples

def generate_silence(duration_secs, sample_rate):
    return [0] * int(sample_rate * duration_secs)

output_path = os.path.join(
    os.path.dirname(__file__),
    "app", "src", "main", "res", "raw", "security_alarm.wav"
)

all_samples = []
for _ in range(REPEATS):
    all_samples.extend(generate_tone(FREQ, BEEP_SECS, SAMPLE_RATE))
    all_samples.extend(generate_silence(SILENCE_SECS, SAMPLE_RATE))

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with wave.open(output_path, "w") as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(SAMPLE_WIDTH)
    wf.setframerate(SAMPLE_RATE)
    packed = struct.pack(f"<{len(all_samples)}h", *all_samples)
    wf.writeframes(packed)

size_kb = os.path.getsize(output_path) // 1024
print(f"[OK] Generated: {output_path}")
print(f"     Samples: {len(all_samples)}, Duration: {len(all_samples)/SAMPLE_RATE:.2f}s, Size: {size_kb} KB")
