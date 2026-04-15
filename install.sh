#!/usr/bin/env bash
set -euo pipefail

if ! command -v pipx >/dev/null 2>&1; then
    echo "Error: pipx is not installed." >&2
    echo "Install it with one of:" >&2
    echo "  brew install pipx && pipx ensurepath" >&2
    echo "  python3 -m pip install --user pipx && python3 -m pipx ensurepath" >&2
    exit 1
fi

# PyAudio needs PortAudio headers at build time.
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "Error: Homebrew not found. Install from https://brew.sh then re-run." >&2
        exit 1
    fi
    if ! brew list portaudio >/dev/null 2>&1; then
        echo "Installing portaudio via Homebrew..."
        brew install portaudio
    fi
    PORTAUDIO_PREFIX="$(brew --prefix portaudio)"
    export CFLAGS="-I${PORTAUDIO_PREFIX}/include ${CFLAGS:-}"
    export LDFLAGS="-L${PORTAUDIO_PREFIX}/lib ${LDFLAGS:-}"
fi

cd "$(dirname "$0")"
pipx install . --force

# Optional: BlackHole virtual audio device for routing `--say` into meetings.
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! brew list blackhole-2ch >/dev/null 2>&1; then
        echo ""
        echo "Installing BlackHole 2ch (virtual audio device for routing --say into Meet/Slack)..."
        if brew install blackhole-2ch; then
            BLACKHOLE_INSTALLED=1
        else
            echo "[warning: BlackHole install failed — skipping setup instructions]" >&2
            BLACKHOLE_INSTALLED=0
        fi
    else
        BLACKHOLE_INSTALLED=1
    fi

    if [[ "${BLACKHOLE_INSTALLED:-0}" == "1" ]]; then
        cat <<'EOF'

────────────────────────────────────────────────────────────────────
BlackHole 2ch is installed. To route `t --say` into Google Meet / Slack
while ALSO keeping your real microphone live, you need TWO virtual devices:

A) A Multi-Output Device so `say` plays to speakers + BlackHole:

  1. Open "Audio MIDI Setup" (⌘-Space → "Audio MIDI Setup").
  2. Click the "+" in the bottom-left → "Create Multi-Output Device".
  3. Check BOTH:
       • your speakers/headphones  (so you hear it)
       • BlackHole 2ch             (so the meeting hears it)
     Rename it "Meet Output". Enable "Drift Correction" on BlackHole.
  4. Right-click it → "Use This Device For Sound Output".

B) An Aggregate Device so the meeting mic = real mic + BlackHole:

  5. Click "+" again → "Create Aggregate Device".
  6. Check BOTH:
       • your real microphone (e.g. "MacBook Air Microphone")
       • BlackHole 2ch
     Rename it "Meet Mic". Enable "Drift Correction" on BlackHole.
  7. In Google Meet / Slack, set the MICROPHONE to "Meet Mic".
     (Leave the output/speaker at whatever you normally use.)

Test:  t -t "hello from the void" --say
You'll hear it, the meeting hears it, AND your voice still goes through.

Tip: in Meet/Slack, disable noise suppression / echo cancellation —
they mangle synthesized speech and may duck the BlackHole channel.
────────────────────────────────────────────────────────────────────
EOF
    fi
fi
