# Kaldr Studio

Kaldr Studio turns pictures into game-ready pixel art and songs into game-ready loops. It runs on your own machine, and you can host it yourself for free.

- **Sprite Builder.** Give it an image or an image URL. A model redraws it, then a deterministic pass reduces it to an exact 48×48 sprite with a clean palette and a 1px outline, and builds a looping idle animation.
- **Sprite Batch.** Do the same for up to 20 images at once.
- **Audio Builder.** Turn a recording into a seamless, vocal-free retro loop.
- **Beep Speech.** Turn a line of text into chiptune babble for character dialogue.

A hosted version, **Kaldr Studio Cloud**, is run by Kaldr Industries LLC. This repository is the self-hosted version.

## License in one minute

Kaldr Studio is **source-available** under the [Functional Source License 1.1, Apache 2.0 Future License](LICENSE.md) (FSL-1.1-ALv2). It is not an OSI "open source" license.

**You can:**

- Host it yourself, for yourself or inside your company, at no cost.
- Read, change and build the code.
- Use it for teaching and non-commercial research.
- Use it to provide professional services to someone who is also using it under this license.
- Use the sprites and audio you make with it however your own rights in the inputs allow (see [Your inputs and outputs](#your-inputs-and-outputs)).

**You can't:**

- Offer it, or a modified version of it, to others as a commercial product or service that competes with Kaldr Studio or Kaldr Studio Cloud. That includes running it as a paid hosted service.
- Use the Kaldr names or logos for your copy. See [TRADEMARKS.md](TRADEMARKS.md).

**Two years after each release,** that release also becomes available under the Apache License 2.0, with no competing-use restriction.

The [license text](LICENSE.md) is what counts. This summary is only a guide. For a commercial license, contact Kaldr Industries LLC.

## Requirements

- macOS on Apple silicon. Some paths and the optional local model are macOS-only for now.
- Python 3.12
- Node.js 20 or newer, to build the web interface
- `ffmpeg`, for the Audio Builder
- An [OpenRouter](https://openrouter.ai) API key, for sprite redraws. You bring your own key and pay OpenRouter directly for each redraw.

## Self-hosting

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install rembg onnxruntime pillow certifi jsonschema

cd web
npm ci
npm run build
cd ..

.venv/bin/python app/server.py            # http://127.0.0.1:8765
```

Open `http://127.0.0.1:8765`, then add your OpenRouter key in the studio. The key is saved on this machine only, in `~/Library/Application Support/sprite-studio/`, readable only by your user.

The server listens on `127.0.0.1` only, so nothing outside this machine can reach it. Change that only if you add your own authentication in front of it.

To work on the interface, run `npm run dev` in `web/` alongside the server. Vite serves the UI on port 5173 and forwards API calls to port 8765.

## Where your data goes

| What | Where it goes |
|---|---|
| Images you redraw | To OpenRouter and the model you pick, using your key |
| Audio and text | Nowhere. Loops and beep speech are made on this machine |
| Jobs and outputs | `studio_jobs/` in this folder |
| Your OpenRouter key | `~/Library/Application Support/sprite-studio/openrouter.key` |

Kaldr Industries LLC receives nothing from a self-hosted copy.

## Your inputs and outputs

You need the right to use whatever you put into the studio. Redrawing, pixelating or animating someone else's art does not make it yours, and it doesn't make it safe to sell. Kaldr Studio does not check whether an image, song or video is cleared for your use.

The background-removal model, [BRIA RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0), is licensed for non-commercial use only. If you make sprites for commercial use, get a commercial license from BRIA or switch `scripts/pixelate.py` to a model whose license allows it.

The Audio Builder can download audio from a URL with `yt-dlp`. Only use it on recordings you have the right to download and adapt.

## Repository layout

| Path | What it holds |
|---|---|
| `app/` | The local API server, sprite pipeline and audio jobs |
| `web/` | The studio interface (React, Vite) |
| `scripts/` | Command-line sprite pipeline: redraw, pixelate, recolor, animate |
| `prompts/` | Prompts for the redraw models |
| `retroloop.py` | Song to vocal-free retro loop |
| `beep_speech/` | Text to beep speech ([README](beep_speech/README.md)) |
| `private/` | Your own art and game data. Gitignored, never published |

Some scripts in `scripts/` were written for a game's own data and expect files under `private/` that aren't in this repository.

## Contributing

Contributions are welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md), which includes a contributor license agreement. To report a security problem, see [SECURITY.md](SECURITY.md).

## Legal

- [LICENSE.md](LICENSE.md): the license for this code
- [NOTICE](NOTICE): copyright and third-party software
- [TRADEMARKS.md](TRADEMARKS.md): use of the Kaldr names and logos
- The in-app [Terms of Service](web/src/legal.tsx) and Privacy Policy cover Kaldr Studio Cloud. Whoever runs a self-hosted copy is responsible for it.

Copyright 2026 Kaldr Industries LLC.
