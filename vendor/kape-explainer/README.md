# KAPE Explainer

Make narrated explainer videos in **your own voice**, with **your own mascot** presenting and **your own brand**
on screen - 1920x1080 at 60fps, 3D camera moves, every animation landing on the word you say.

You tell Claude the topic. It writes the script in your speaking style, you record it (or generate it with your
ElevenLabs voice clone), and Claude builds the whole film: storyboard, scenes, presenter, music, render.

A Claude Code plugin by [BrewedOps](https://brewedops.com).

---

## What you need

| | |
|---|---|
| **Claude Code** | Any paid Claude plan. A film uses several parallel agents, so expect a long session (1-3 hours). |
| **Your voice** | An [ElevenLabs](https://elevenlabs.io) voice clone (best), or a clean recording of yourself reading the script in one take. |
| **A computer** | Windows 10/11 or macOS. A dedicated GPU makes the final render much faster (without one it still works, just slower). About 5 GB of free disk. |
| **Tools** | Node.js 20+, Python 3.10+ (3.12 recommended), ffmpeg. The setup check tells you exactly what is missing. |
| **Optional** | Your own mascot (transparent PNGs, see below), your logo, a background track you have the rights to. |

## Install

**1. Install the tools** (skip what you already have)

Windows (PowerShell):

```powershell
winget install OpenJS.NodeJS.LTS Python.Python.3.12 Gyan.FFmpeg
py -3.12 -m pip install numpy pillow scipy faster-whisper
```

macOS (Terminal, needs [Homebrew](https://brew.sh)):

```bash
brew install node python@3.12 ffmpeg
python3.12 -m pip install numpy pillow scipy faster-whisper
```

Then the video engine's helper skills (both systems):

```bash
npx hyperframes skills update general-video hyperframes-animation media-use
```

**2. Install the skills** - open a terminal in this folder (the one with `install.mjs`) and run:

```bash
node install.mjs
```

It copies the two skills (`kape-explainer` + the `spatial-film` engine it runs on) into `~/.claude/skills/`
and checks your machine. Restart Claude Code once after it finishes.

**3. Start** - in any folder, tell Claude:

> make a kape explainer about how email marketing works

The first time, Claude runs the setup check and asks a few questions to build your profile (your brand name,
logo, colours, how you talk, which mascot). That profile lives in `~/.kape-explainer/profile/` and every film
after that uses it.

## How a film gets made

1. **Script** - Claude writes it in your voice (about 200 words = 90 seconds) and gives you voice settings.
2. **You record** - one MP3. Your voice is never edited, only levelled; the picture moves to your words.
3. **Storyboard** - Claude shows you every scene first. Nothing gets built until you say "go".
4. **Build** - parallel agents build the scenes; your mascot presents on the left, your logo sits in the corner.
5. **Render** - 1080p60 MP4 plus a web version, with a check that proves the picture is in sync with your voice.

## Your own mascot

KAPE (the guy with glasses and a coffee mug) is the default presenter so your first film works right away. To use your own character,
make **one transparent PNG per pose**, all the same character at roughly the same size:

| File | Required? | What it shows |
|---|---|---|
| `poses/idle.png` | required | standing, neutral |
| `poses/point.png` | required | pointing toward the right side of the screen |
| `poses/wave.png`, `present.png`, `think.png`, `thumbs-up.png`, `celebrate.png` | recommended | more variety |
| `faces/neutral.png` + `faces/blink.png` | optional | the head with eyes open / closed - turns on blinking |

Put them in `~/.kape-explainer/profile/mascot/` and ask Claude to "prep my mascot". Tips: generate all poses
from one reference image so the character stays consistent, and remove the background with remove.bg or
Photoshop (a white background is not transparent).

## Updating

Get the new zip, unzip it and run `node install.mjs` again.

Your profile is outside the plugin, so updates never touch it.

## Good to know

- **Music:** only use a track you have the rights to (put it at `~/.kape-explainer/profile/music/bed.mp3`), or
  let Claude search the HeyGen catalog (free account, `npx hyperframes auth login` once), or go without.
- **Language:** English by default; set your language in the profile. Taglish works well with ElevenLabs
  Multilingual v2.
- **Vertical video:** ask for a 9:16 version for Reels/TikTok/Shorts.
- Built on [HyperFrames](https://www.npmjs.com/package/hyperframes) (HTML + GSAP rendered to video).

## License

Code: MIT. The KAPE mascot artwork is free to use as the presenter in your own videos, but not as your own
logo or brand character - see [LICENSE](LICENSE).
