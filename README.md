# skimap

Small CLI for live ski resort lift status via the [Ski API](https://skiapi.com/) on [RapidAPI](https://rapidapi.com/random-shapes-random-shapes-default/api/ski-resorts-and-conditions) (Ski Resorts and Conditions). It prints each lift in a table with open/closed (and related) states.

## Setup

1. Create a [RapidAPI](https://rapidapi.com/) account and subscribe to **Ski Resorts and Conditions**.

2. Copy the environment template and add your key:

   ```bash
   cp .env.example .env
   ```

   Set `RAPIDAPI_KEY` in `.env` to your RapidAPI application key.

3. Install dependencies (Python 3.10+ recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

```bash
python ski_trails.py palisades
python ski_trails.py                    # prompts for resort slug
python ski_trails.py --list-resorts     # slugs (GitHub Liftie index if RapidAPI has no list endpoint)
python ski_trails.py brighton --raw-json
```

**Slugs:** Many resorts match folder names from [Liftie](https://github.com/pirxpilot/liftie) under `lib/resorts/`. Palisades Tahoe uses `palisades` (not `alpine`); the script maps common legacy names to `palisades`.

**Note:** This API exposes **lift** status for most resorts, not per-trail geometry. The script still prefers trail/run fields when the payload includes them.

## License

Use follows RapidAPI and upstream data providers’ terms.
