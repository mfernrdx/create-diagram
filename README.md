# create-diagram

Turns text descriptions (e.g. Upwork job posts) into interactive Excalidraw diagrams automatically.

## How it works

1. **Analyzer** — Sends the description to Claude CLI, which breaks it down into structured diagram specs (nodes, connections, colors)
2. **Renderer** — Converts the specs into valid `.excalidraw` JSON with auto-layout (layered graph positioning, pastel colors, hand-drawn style)
3. **Viewer** — Serves the diagrams locally with the full Excalidraw editor embedded in the browser

Multiple diagrams are combined into a single `.excalidraw` file, stacked vertically.

## Setup

Requires [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) (authenticated with a Max plan or API key).

```bash
pip install anthropic   # only needed if using the SDK directly
```

## Usage

```bash
# Generate diagrams and open in browser (default)
python pipeline.py job_description.txt

# Open in VS Code instead (requires Excalidraw extension)
python pipeline.py job_description.txt --vscode

# Paste description via stdin
python pipeline.py

# View existing .excalidraw files in browser
python viewer.py output/*.excalidraw
```

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | Main entry point — orchestrates analyze + render + view |
| `renderer.py` | Excalidraw JSON generator with auto-layout engine |
| `viewer.py` | Local HTTP server that embeds the full Excalidraw editor |

## Output

Generates `.excalidraw` files in `output/` with:
- Pastel color palette (pink, blue, green, purple, yellow, orange, teal, lavender)
- Auto-layout (left-to-right default, supports top-to-bottom)
- Hand-drawn Excalidraw style (roughness, Virgil font)
- Rectangles, diamonds, ellipses, arrows with labels
