import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from deep_translator import GoogleTranslator
import pyperclip

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
DEFAULT_CONFIG = {"from": "english", "to": "russian"}


def ensure_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        return dict(DEFAULT_CONFIG)
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        cfg = {}
    merged = dict(DEFAULT_CONFIG)
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


def resolve_text(token: str) -> str:
    if token == "buffer":
        return pyperclip.paste()
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
    # Only treat a single token as buffer/path; multi-token is always literal.
    if len(args.text) == 1:
        text = resolve_text(args.text[0])
    else:
        text = raw

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
