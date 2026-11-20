"""SPH0645 I2S 마이크 단독 테스트 ― camera_server.py 없이 마이크 배선과 ALSA 설정만 확인한다.

실행: python3 test_mic.py           (조용히 2초 → 말하기 3초, 두 번 녹음해 소리 크기를 비교)
      python3 test_mic.py --play    (녹음한 말을 aplay 로 다시 들어 본다 ― 스피커 · 이어폰이 있을 때)
      python3 test_mic.py --min-gain-db 3    (현장 점검 예시: 최소 차이 3dB)
확인: 말하기와 조용한 구간의 RMS 차이를 비교한다. 수업 기준은 10dB다.

녹음 형식(16kHz · mono · S16_LE)과 장치 이름은 camera_server.py 의 VOICE_* 상수와 같다 ―
여기서 되면 PTT 녹음도 된다.
"""

import argparse
import array
import math
import subprocess
import wave

ALSA_CARD_NAME = "sndrpigooglevoi"
ALSA_DEVICE = f"plughw:CARD={ALSA_CARD_NAME},DEV=0"      # camera_server.py:VOICE_ALSA_DEVICE
SAMPLE_RATE = 16000
COURSE_MIN_GAIN_DB = 10.0


def record(path, seconds):
    subprocess.run(["arecord", "-q", "-D", ALSA_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
                    "-c", "1", "-d", str(seconds), path], check=True)


def level_db(path):
    """녹음 파일의 RMS · 최대값을 dBFS 로 (0 dBFS = 가장 큰 소리, -90 이면 무음)."""
    with wave.open(path) as wav:
        samples = array.array("h", wav.readframes(wav.getnframes()))
    if not samples:
        return -90.0, -90.0
    mean = sum(samples) / len(samples)                     # SPH0645 는 DC 오프셋이 있어 빼고 잰다
    rms = math.sqrt(sum((s - mean) ** 2 for s in samples) / len(samples))
    peak = max(abs(s - mean) for s in samples)
    to_db = lambda v: 20 * math.log10(max(v, 1) / 32768)
    return to_db(rms), to_db(peak)


parser = argparse.ArgumentParser(description="I2S 마이크 단독 테스트")
parser.add_argument("--play", action="store_true", help="녹음한 말을 다시 재생한다")
parser.add_argument("--min-gain-db", type=float, default=COURSE_MIN_GAIN_DB,
                    help="말하기 RMS가 조용한 구간보다 커야 하는 최소 차이(dB, 수업 기준 10)")
args = parser.parse_args()
if not math.isfinite(args.min_gain_db) or args.min_gain_db <= 0:
    parser.error("--min-gain-db 값은 0보다 큰 유한한 수여야 합니다")

# ① 사운드 카드 ― config.txt 의 dtparam=i2s=on · dtoverlay 가 적용돼야 보인다.
cards = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
print(cards.strip() or "(녹음 장치 없음)")
if ALSA_CARD_NAME not in cards:
    print(f"FAIL  {ALSA_CARD_NAME} 카드가 없다 ― /boot/firmware/config.txt 에")
    print("      dtparam=i2s=on / dtoverlay=googlevoicehat-soundcard 를 넣고 재부팅한다")
    raise SystemExit(1)

# ② 조용히 → 말하기 두 번 녹음
input("조용히 2초 녹음합니다. Enter 를 누르고 아무 말도 하지 마세요…")
record("/tmp/mic_quiet.wav", 2)
input("말하기 3초 녹음합니다. Enter 를 누르고 '오른쪽으로 두 칸 가' 라고 말하세요…")
record("/tmp/mic_speech.wav", 3)

quiet_rms, _ = level_db("/tmp/mic_quiet.wav")
speech_rms, speech_peak = level_db("/tmp/mic_speech.wav")
print(f"조용히  RMS {quiet_rms:6.1f} dBFS")
print(f"말하기  RMS {speech_rms:6.1f} dBFS (최대 {speech_peak:.1f})")

if args.play:
    subprocess.run(["aplay", "-q", "/tmp/mic_speech.wav"])

# ③ 판정
if speech_rms <= -85:
    print("FAIL  값이 전부 0 에 가깝다 ― DOUT(물리 38) · BCLK(12) · LRCL(35) 배선, 3V 전원을 확인한다")
    raise SystemExit(1)
if speech_peak > -1.0:
    print("WARN  소리가 잘렸다(클리핑) ― 마이크에서 조금 떨어져서 말한다")
gain_db = speech_rms - quiet_rms
criterion = "수업 기준" if args.min_gain_db == COURSE_MIN_GAIN_DB else "사용자 기준"
comparison = f"측정 차이 {gain_db:+.1f} dB, {criterion} {args.min_gain_db:g} dB"
if gain_db < args.min_gain_db:
    print(f"FAIL  말하기 RMS 증가량 부족 ({comparison})")
    raise SystemExit(1)
print(f"PASS  마이크 음량 검사 ({comparison})")
