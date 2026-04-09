# skimap

CLI that prints **detailed live lift and run (trail) status** using **[ski-resort-status](https://www.npmjs.com/package/ski-resort-status)** from the **[ski-lift-status](https://github.com/marcushyett/ski-lift-status)** project. Data is matched to **[OpenSkiMap](https://openskimap.org/)** IDs.

Coverage is **whatever that library supports** (today mostly **Lumiplan**-based areas in France; the list grows over time). This replaces the earlier RapidAPI-only flow.

## Requirements

- **Python 3.10+**
- **Node.js 18+** (`node` on your PATH)

## Setup

```bash
git clone https://github.com/philipnisevich/skimap.git
cd skimap
npm install
```

No Python `pip` packages are required.

## Usage

```bash
python ski_trails.py --list-resorts
python ski_trails.py les-trois-vallees
python ski_trails.py --raw-json espace-diamant
```

- **`--list-resorts`** — IDs and names from `getSupportedResorts()`.
- **`--raw-json`** — Full JSON from `fetchResortStatus()` after the human-readable sections.

Equivalent:

```bash
npm run resorts
```

## How it works

Python runs a small Node bridge: [`node/ski_resort_bridge.cjs`](node/ski_resort_bridge.cjs), which calls `ski-resort-status` and prints JSON on stdout for Python to format.

## License

Your use of resort data is subject to **ski-resort-status** and upstream providers. See the [ski-lift-status license](https://github.com/marcushyett/ski-lift-status/blob/main/LICENSE).
