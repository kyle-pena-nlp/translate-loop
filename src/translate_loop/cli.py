import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from deep_translator import GoogleTranslator
import pyperclip

# BCP-47 codes for Google Web Speech (used by `capture`).
RECOGNIZE_CODES = {
    "english": "en-US",
    "russian": "ru-RU",
    "spanish": "es-ES",
    "french": "fr-FR",
    "german": "de-DE",
    "italian": "it-IT",
    "portuguese": "pt-PT",
    "dutch": "nl-NL",
    "polish": "pl-PL",
    "turkish": "tr-TR",
    "arabic": "ar-SA",
    "hindi": "hi-IN",
    "japanese": "ja-JP",
    "korean": "ko-KR",
    "chinese": "zh-CN",
    "chinese (simplified)": "zh-CN",
    "chinese (traditional)": "zh-TW",
    "swedish": "sv-SE",
    "norwegian": "nb-NO",
    "danish": "da-DK",
    "finnish": "fi-FI",
    "greek": "el-GR",
    "czech": "cs-CZ",
    "hungarian": "hu-HU",
    "romanian": "ro-RO",
    "slovak": "sk-SK",
    "thai": "th-TH",
    "hebrew": "he-IL",
    "indonesian": "id-ID",
    "malay": "ms-MY",
    "ukrainian": "uk-UA",
    "vietnamese": "vi-VN",
}

# macOS `say` voices by language name.
SAY_VOICES = {
    "english": "Samantha",
    "russian": "Milena",
    "spanish": "Monica",
    "french": "Thomas",
    "german": "Anna",
    "italian": "Alice",
    "portuguese": "Luciana",
    "dutch": "Xander",
    "polish": "Zosia",
    "turkish": "Yelda",
    "arabic": "Maged",
    "hindi": "Lekha",
    "japanese": "Kyoko",
    "korean": "Yuna",
    "chinese (simplified)": "Ting-Ting",
    "chinese (traditional)": "Mei-Jia",
    "chinese": "Ting-Ting",
    "swedish": "Alva",
    "norwegian": "Nora",
    "danish": "Sara",
    "finnish": "Satu",
    "greek": "Melina",
    "czech": "Zuzana",
    "hungarian": "Mariska",
    "romanian": "Ioana",
    "slovak": "Laura",
    "thai": "Kanya",
    "hebrew": "Carmit",
    "indonesian": "Damayanti",
    "malay": "Amira",
}


def say(text: str, lang: str) -> None:
    if not shutil.which("say"):
        print("[--say: 'say' command not found — macOS only]", file=sys.stderr)
        return
    if not text.strip():
        return
    voice = SAY_VOICES.get(lang.strip().lower())
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    else:
        print(f"[--say: no voice mapped for '{lang}', using default]", file=sys.stderr)
    cmd.append(text)
    subprocess.run(cmd, check=False)

CONFIG_PATH = Path.home() / ".config" / "t" / "config.json"
LOCAL_CONFIG_NAME = "config.json"
DEFAULT_CONFIG = {"from": "english", "to": "russian"}


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def ensure_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))

    merged = dict(DEFAULT_CONFIG)
    for src in (CONFIG_PATH, Path.cwd() / LOCAL_CONFIG_NAME):
        if src.exists():
            cfg = _load_json(src)
            merged.update({k: v for k, v in cfg.items() if k in ("from", "to")})
    return merged


def looks_like_path(s: str) -> bool:
    expanded = os.path.expanduser(s)
    if os.path.isfile(expanded):
        return True
    if any(ch in s for ch in ("\n", "\t")) or len(s) > 4096:
        return False
    if s.startswith(("./", "../", "/", "~/")):
        return True
    return False


def capture_from_mic(lang: str) -> str:
    import pyaudio
    import speech_recognition as sr

    rate = 16000
    chunk = 1024
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=rate,
        input=True, frames_per_buffer=chunk,
    )
    frames = []
    stop = threading.Event()

    def record():
        while not stop.is_set():
            frames.append(stream.read(chunk, exception_on_overflow=False))

    t = threading.Thread(target=record, daemon=True)
    t.start()
    try:
        input(f"[capture: recording in {lang}... press Enter to stop] ")
    finally:
        stop.set()
        t.join()
        stream.stop_stream()
        stream.close()
        pa.terminate()

    if not frames:
        return ""

    audio = sr.AudioData(b"".join(frames), rate, 2)
    r = sr.Recognizer()
    code = RECOGNIZE_CODES.get(lang.strip().lower(), "en-US")
    try:
        return r.recognize_google(audio, language=code)
    except sr.UnknownValueError:
        print("[capture: could not understand audio]", file=sys.stderr)
        return ""
    except sr.RequestError as e:
        print(f"[capture: recognition request failed: {e}]", file=sys.stderr)
        return ""


def resolve_text(token: str, src_lang: str) -> str:
    if token == "buffer":
        return pyperclip.paste()
    if token == "capture":
        return capture_from_mic(src_lang)
    if looks_like_path(token):
        expanded = os.path.expanduser(token)
        if os.path.isfile(expanded):
            return Path(expanded).read_text()
    return token


def translate(text: str, source: str, target: str) -> str:
    if not text.strip():
        return text
    return GoogleTranslator(source=source, target=target).translate(text)


def write_out(out_arg: str, content: str) -> Path:
    p = Path(os.path.expanduser(out_arg))
    if p.is_dir():
        p = p / "t_output.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="t", description="Round-trip translator.")
    parser.add_argument("--from", dest="src", help="Source language (overrides config)")
    parser.add_argument("--to", dest="dst", help="Target language (overrides config)")
    parser.add_argument("-t", dest="one_way", action="store_true",
                        help="One-way: translate into the 'from' language and stop.")
    parser.add_argument("--out", dest="out", help="Write result to file/dir unconditionally.")
    parser.add_argument("--say", dest="say", action="store_true",
                        help="Speak the result via macOS `say` with a voice for the output language.")
    parser.add_argument("text", nargs="+", help="Text, 'buffer', or a filepath.")
    args = parser.parse_args(argv)

    cfg = ensure_config()
    src_lang = args.src or cfg["from"]
    dst_lang = args.dst or cfg["to"]

    raw = " ".join(args.text)
    # Only treat a single token as buffer/capture/path; multi-token is always literal.
    if len(args.text) == 1:
        text = resolve_text(args.text[0], src_lang)
    else:
        text = raw

    if not text.strip():
        print("[no input text]", file=sys.stderr)
        return 1

    if args.one_way:
        # Single hop into the 'to' language.
        result = translate(text, source=src_lang, target=dst_lang)
        result_lang = dst_lang
    else:
        # Round trip: from -> to -> from. Result ends in the 'from' language.
        step1 = translate(text, source=src_lang, target=dst_lang)
        result = translate(step1, source=dst_lang, target=src_lang)
        result_lang = src_lang

    print(result)

    if args.out:
        path = write_out(args.out, result)
        print(f"[wrote: {path}]", file=sys.stderr)

    if args.say:
        say(result, result_lang)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
