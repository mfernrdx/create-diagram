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

from renderer import render_to_file

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


def analyze_job(description: str, model: str = "sonnet") -> dict:
    """Send the job description to Claude CLI and get back a diagram spec."""
    result = subprocess.run(
        [
            "claude", "-p",
            "--system-prompt", SYSTEM_PROMPT,
            "--model", model,
            "--output-format", "text",
        ],
        input=description,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed:\n{result.stderr}")

    raw = result.stdout.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*\n", "", raw)
    raw = re.sub(r"\n```\s*$", "", raw)

    return json.loads(raw)


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
