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

cd web
npm ci
npm run build
cd ..

.venv/bin/python -m app.server            # http://127.0.0.1:8765
```

Run it from the repository folder. `requirements.txt` pins every Python dependency to an exact version.

Open `http://127.0.0.1:8765`, then add your OpenRouter key in the studio. The key is saved on this machine only, in `~/Library/Application Support/kaldr-studio/`, readable only by your user. A key saved by an earlier version under `sprite-studio/` moves there on its own.

The server listens on `127.0.0.1` only, so nothing outside this machine can reach it. Change that only if you add your own authentication in front of it.

To work on the interface, run `npm run dev` in `web/` alongside the server. Vite serves the UI on port 5173 and forwards API calls to port 8765.

## API

Each generator has one route that takes everything the studio sends. Post `multipart/form-data`, or `application/json` when there is no file. Leave a setting out to use the studio's default. A field the route does not know is an error, so a typo does not go unnoticed. Errors come back as `{"error": "..."}` with status 400.

The server only answers requests addressed to `127.0.0.1` or `localhost`.

### `POST /api/v1/sprite`

Send `file` (an image, up to 20 MB) or `url`. Returns `202` with the job. Poll `GET /jobs/<id>` until `status` is `done` or `error`, then fetch the files it lists or `GET /jobs/<id>/sprite.zip`. Each sprite is a redraw charged to your OpenRouter key.

| Field | Values | Default |
|---|---|---|
| `model` | an `id` from `GET /models` | FLUX.2 Klein 4B |
| `canvas` | `32`, `48` or `64` | `48` |
| `palette_colors` | 4 to 24 | `14` |
| `saturation` | 0.5 to 2 | `1.25` |
| `contrast` | 0.5 to 2 | `1.1` |
| `coverage` | 0.05 to 0.8 | `0.35` |
| `dark_bias` | 0 to 6 | `3` |
| `outline` | `true` or `false` | `true` |
| `sticker` | `true` or `false` | `false` |

```bash
curl -F file=@cat.png -F canvas=64 -F outline=false http://127.0.0.1:8765/api/v1/sprite
```

### `POST /api/v1/loop`

Send `file` (audio or video, up to 80 MB) or `url`, and `rights=true` to confirm you own the recording or have permission to use it. Returns `202` with the job. Poll `GET /audio/score/<id>` until `status` is `done` or `error`, then fetch the files it lists.

| Field | Values | Default |
|---|---|---|
| `style` | `soft` or `gb` | `soft` |
| `classic` | `true` or `false` | `false` |
| `lead` | `vocal-melody`, `instrument` or `none` | `vocal-melody` |
| `min_seconds` | 8 to 180, no more than `max_seconds` | `40` |
| `max_seconds` | 8 to 240 | `90` |
| `start_after` | 0 to 600 | `0` |
| `space` | 0 to 2.5 | `1` |
| `brightness` | 0.35 to 2 | `1` |
| `lead_level`, `chords_level`, `bass_level`, `drums_level` | 0 to 2.5 | `1` |

```bash
curl -F file=@song.mp3 -F rights=true -F style=gb http://127.0.0.1:8765/api/v1/loop
```

### `POST /api/v1/speech`

Send `text`, up to 600 characters. Returns `200` with a WAV file.

| Field | Values | Default |
|---|---|---|
| `pitch` | 80 to 800 | `300` |
| `speed` | 4 to 40 | `16` |
| `variation` | 0 to 12 | `3` |
| `length` | 0.2 to 3 | `1` |
| `drop` | 0 to 6 | `1` |
| `pauses` | 0 to 4 | `1` |
| `brightness` | 400 to 16000 | `6000` |
| `lift` | 0 to 6 | `1` |
| `tone` | 0.05 to 0.9 | `0.5` |
| `seed` | a whole number from 0 to 2000000000, for the same audio every time | random |

```bash
curl -F text="Want to buy something?" -F pitch=440 -F seed=7 -o line.wav http://127.0.0.1:8765/api/v1/speech
```

## Where your data goes

| What | Where it goes |
|---|---|
| Images you redraw | To OpenRouter and the model you pick, using your key |
| Audio and text | Nowhere. Loops and beep speech are made on this machine |
| Jobs and outputs | `studio_jobs/` in this folder |
| Your OpenRouter key | `~/Library/Application Support/kaldr-studio/openrouter.key` |

Kaldr Industries LLC receives nothing from a self-hosted copy.

## Models

| Step | Model | Runs | License |
|---|---|---|---|
| Redraw | FLUX.2 Klein 4B by default, or another model you pick | On OpenRouter | Apache-2.0 for Klein 4B; others under their provider's terms |
| Background removal | [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | On this machine | MIT |
| Stem separation | [Demucs](https://github.com/facebookresearch/demucs) `htdemucs` | On this machine | MIT |

BiRefNet and Demucs download on first use. BiRefNet takes about 16 seconds per image on Apple silicon. All three defaults allow commercial use of what they produce.

## Your inputs and outputs

You need the right to use whatever you put into the studio. Redrawing, pixelating or animating someone else's art does not make it yours, and it doesn't make it safe to sell. Kaldr Studio does not check whether an image, song or video is cleared for your use.

The Audio Builder can download audio from a URL with `yt-dlp`. Only use it on recordings you have the right to download and adapt.

## Repository layout

| Path | What it holds |
|---|---|
| `app/` | The local server (`server.py`, with routes in `routes_*.py`), sprite pipeline and jobs, and audio jobs |
| `web/` | The studio interface (React, Vite) |
| `scripts/` | Command-line sprite pipeline: redraw, pixelate, recolor, animate |
| `prompts/` | Prompts for the redraw models |
| `retroloop/` | Song to vocal-free retro loop |
| `beep_speech/` | Text to beep speech ([README](beep_speech/README.md)) |
| `tests/` | Tests for the server, the API and the settings each generator accepts |
| `private/` | Your own art and game data. Gitignored, never published |

Run a script as a module from the repository folder, for example `.venv/bin/python -m scripts.animate`. Some scripts in `scripts/` were written for a game's own data and expect files under `private/` that aren't in this repository.

## Contributing

Contributions are welcome under the terms in [CONTRIBUTING.md](CONTRIBUTING.md), which includes a contributor license agreement. To report a security problem, see [SECURITY.md](SECURITY.md).

## Legal

- [LICENSE.md](LICENSE.md): the license for this code
- [NOTICE](NOTICE): copyright and third-party software
- [TRADEMARKS.md](TRADEMARKS.md): use of the Kaldr names and logos
- The in-app [Terms of Service](web/src/legal.tsx) and Privacy Policy cover Kaldr Studio Cloud. Whoever runs a self-hosted copy is responsible for it.

Copyright 2026 Kaldr Industries LLC.
