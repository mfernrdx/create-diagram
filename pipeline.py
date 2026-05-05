"""Pipeline: Upwork job description → diagram specs → Excalidraw files.

Usage:
    python pipeline.py job_description.txt          # read from file
    python pipeline.py                              # paste into stdin
    python -c "from pipeline import generate_diagrams; generate_diagrams('...')"
"""

import json
import os
import re
import subprocess
import sys

from renderer import render_combined, render_to_file

# Default API model. Matches what upwork_automation uses for scoring (Sonnet 4).
DEFAULT_API_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a technical diagram architect. Given an Upwork job description, \
break it down into clear, simple visual diagrams that show what the project \
involves at a glance.

## Rules
- Create 1-3 diagrams depending on complexity (most jobs need 1-2)
- Each diagram: 4-10 nodes (keep it digestible)
- Each node label has TWO parts separated by a newline:
  - Line 1: Short title (2-4 words)
  - Line 2: Brief example or detail in parentheses, e.g. "(OCR, email parsing)"
- Use plain language a non-technical person can follow
- Show logical flow — what leads to what
- Same color = related category
- Space nodes well — don't cram too many into one diagram

## Diagram types (pick what fits the job)
- **Workflow** — step-by-step process (most common)
- **Architecture** — system components and connections
- **Deliverables** — what gets built

## Pastel color palette (use these exact hex values)
- #fce4ec  Pink — user-facing / frontend
- #e3f2fd  Blue — backend / API / logic
- #e8f5e9  Green — data / database / storage
- #f3e5f5  Purple — integrations / third-party
- #fff9c4  Yellow — planning / setup / config
- #fff3e0  Orange — testing / QA / review
- #e0f7fa  Teal — deployment / infrastructure
- #ede7f6  Lavender — docs / communication

## Shape types
- "rectangle" — default for steps and components
- "diamond" — decision points or conditions
- "ellipse" — start / end points

## Direction
- "LR" — left to right (DEFAULT — prefer this for most diagrams)
- "TB" — top to bottom (only use if the diagram has many branching paths)

## Output
Return ONLY valid JSON — no markdown fences, no explanation.

{
  "title": "Short Project Title",
  "diagrams": [
    {
      "name": "Diagram Title",
      "direction": "LR",
      "nodes": [
        {"id": "1", "label": "Data Ingestion\\n(fax, email, API)", "color": "#fce4ec", "shape": "rectangle"},
        {"id": "2", "label": "AI Processing\\n(NLP, classification)", "color": "#e3f2fd", "shape": "rectangle"}
      ],
      "connections": [
        {"from": "1", "to": "2", "label": ""}
      ]
    }
  ]
}
"""


def _strip_fences(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*\n", "", raw.strip())
    raw = re.sub(r"\n```\s*$", "", raw)
    return raw


def _analyze_via_api(description: str, model: str) -> dict:
    """Call the Anthropic API directly. Used by upwork_automation's trigger_agent
    where Claude CLI subprocess on Windows wedges silently. Requires
    ANTHROPIC_API_KEY in env."""
    import anthropic  # imported lazily so CLI mode doesn't require the SDK

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot call Anthropic API")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": description}],
    )
    # response.content is a list of content blocks; the first is the text
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    raw = "".join(parts).strip()
    return json.loads(_strip_fences(raw))


def _analyze_via_cli(description: str, model: str) -> dict:
    """Original Claude CLI path. Kept for standalone CLI usage of this repo —
    upwork_automation's daemonized trigger_agent uses _analyze_via_api instead
    because the CLI subprocess wedges under that supervisor on Windows."""
    result = subprocess.run(
        [
            "claude", "-p", description,
            "--system-prompt", SYSTEM_PROMPT,
            "--model", model,
            "--output-format", "text",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed:\n{result.stderr}")
    return json.loads(_strip_fences(result.stdout))


_API_ALIAS = {"sonnet": DEFAULT_API_MODEL, "haiku": "claude-haiku-4-5-20251001"}


def analyze_job(description: str, model: str | None = None) -> dict:
    """Send the job description to Claude and get back a diagram spec.

    Routing:
    - If ANTHROPIC_API_KEY is set → use Anthropic SDK (HTTP). This is what the
      upwork_automation trigger_agent runs into; the CLI subprocess path
      reliably wedges under that supervisor on Windows.
    - Otherwise → fall back to the `claude` CLI for standalone use of this repo.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        api_model = _API_ALIAS.get(model, model) if model else DEFAULT_API_MODEL
        return _analyze_via_api(description, api_model)
    return _analyze_via_cli(description, model or "sonnet")


def generate_diagram_json(description: str, model: str | None = None) -> dict:
    """In-process variant: analyze + render, return rendered Excalidraw doc.

    Returns {"title": <project title>, "excalidraw": <full excalidraw doc dict>}.
    No file IO. Used by upwork_automation/trigger_agent.py. When model is None,
    analyze_job picks the default for whichever path it routes to (API vs CLI).
    """
    spec = analyze_job(description, model=model)
    diagrams = spec.get("diagrams", [])
    if not diagrams:
        raise ValueError("Analyzer returned no diagrams")
    return {
        "title": spec.get("title", "diagram"),
        "excalidraw": render_combined(diagrams),
    }


def generate_diagrams(description: str, output_dir: str = "output") -> str:
    """Full pipeline: analyze → render → save single combined .excalidraw file."""
    print("Analyzing job description with Claude...")
    spec = analyze_job(description)

    os.makedirs(output_dir, exist_ok=True)

    title = spec.get("title", "diagram")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")

    diagrams = spec["diagrams"]
    filename = f"{safe_title}.excalidraw"
    path = os.path.join(output_dir, filename)

    render_to_file(diagrams, path)

    diagram_names = [d.get("name", f"diagram_{i+1}") for i, d in enumerate(diagrams)]
    print(f"  Created: {path}")
    print(f"  Contains {len(diagrams)} diagram(s): {', '.join(diagram_names)}")
    return path


if __name__ == "__main__":
    use_vscode = "--vscode" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--vscode"]

    if args:
        with open(args[0], "r", encoding="utf-8") as f:
            desc = f.read()
    else:
        print("Paste the Upwork job description (Ctrl+Z then Enter when done):\n")
        desc = sys.stdin.read()

    path = generate_diagrams(desc)

    if use_vscode:
        subprocess.Popen(["code", path])
    else:
        from viewer import serve
        serve([path])
