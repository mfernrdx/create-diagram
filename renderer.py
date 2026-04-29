"""Generates Excalidraw JSON files from structured diagram specifications."""

import json
import random
import time
from collections import defaultdict, deque

# Pastel color palette
PALETTE = {
    "pink": "#fce4ec",
    "blue": "#e3f2fd",
    "green": "#e8f5e9",
    "purple": "#f3e5f5",
    "yellow": "#fff9c4",
    "orange": "#fff3e0",
    "teal": "#e0f7fa",
    "lavender": "#ede7f6",
    "rose": "#fbe9e7",
    "mint": "#e0f2f1",
}

PALETTE_LIST = list(PALETTE.values())

# Layout constants
NODE_MIN_W = 220
NODE_MIN_H = 80
NODE_PAD_X = 44
NODE_PAD_Y = 32
H_GAP = 100
V_GAP = 120
MARGIN = 80
FONT_SIZE = 18
TITLE_FONT_SIZE = 28
CHAR_WIDTH_RATIO = 0.55
DIAGRAM_GAP = 250  # vertical space between diagrams in combined mode


def _seed():
    return random.randint(1, 2**31 - 1)


def _node_dimensions(label: str, shape: str = "rectangle") -> tuple[float, float]:
    """Calculate node width and height based on label text."""
    lines = label.split("\n")
    line_height = FONT_SIZE * 1.25
    max_chars = max(len(line) for line in lines)

    text_w = max_chars * FONT_SIZE * CHAR_WIDTH_RATIO
    text_h = len(lines) * line_height

    w = max(NODE_MIN_W, text_w + NODE_PAD_X * 2)
    h = max(NODE_MIN_H, text_h + NODE_PAD_Y * 2)

    if shape == "diamond":
        w *= 1.5
        h *= 1.4

    return round(w), round(h)


def _compute_layout(nodes, connections, direction="TB"):
    """Assign x,y positions using a layered graph layout."""
    node_ids = [n["id"] for n in nodes]
    node_map = {n["id"]: n for n in nodes}

    children = defaultdict(list)
    parents = defaultdict(list)
    for conn in connections:
        if conn["from"] in node_map and conn["to"] in node_map:
            children[conn["from"]].append(conn["to"])
            parents[conn["to"]].append(conn["from"])

    roots = [nid for nid in node_ids if not parents[nid]]
    if not roots:
        roots = [node_ids[0]]

    layers = {}
    queue = deque()
    for root in roots:
        layers[root] = 0
        queue.append(root)

    while queue:
        node = queue.popleft()
        for child in children[node]:
            new_layer = layers[node] + 1
            if child not in layers or layers[child] < new_layer:
                layers[child] = new_layer
                queue.append(child)

    max_layer = max(layers.values()) if layers else 0
    for nid in node_ids:
        if nid not in layers:
            max_layer += 1
            layers[nid] = max_layer

    layer_groups = defaultdict(list)
    for nid in node_ids:
        layer_groups[layers[nid]].append(nid)

    dims = {}
    for n in nodes:
        dims[n["id"]] = _node_dimensions(n["label"], n.get("shape", "rectangle"))

    positions = {}
    sorted_layers = sorted(layer_groups.keys())

    if direction == "TB":
        y_offsets = {}
        cumulative_y = 0
        for layer_idx in sorted_layers:
            y_offsets[layer_idx] = cumulative_y
            max_h = max(dims[nid][1] for nid in layer_groups[layer_idx])
            cumulative_y += max_h + V_GAP

        for layer_idx in sorted_layers:
            nodes_in_layer = layer_groups[layer_idx]
            total_w = sum(dims[nid][0] for nid in nodes_in_layer)
            total_w += H_GAP * (len(nodes_in_layer) - 1)
            start_x = -total_w / 2

            x_cursor = start_x
            for nid in nodes_in_layer:
                w, h = dims[nid]
                positions[nid] = (x_cursor, y_offsets[layer_idx])
                x_cursor += w + H_GAP
    else:
        x_offsets = {}
        cumulative_x = 0
        for layer_idx in sorted_layers:
            x_offsets[layer_idx] = cumulative_x
            max_w = max(dims[nid][0] for nid in layer_groups[layer_idx])
            cumulative_x += max_w + V_GAP

        for layer_idx in sorted_layers:
            nodes_in_layer = layer_groups[layer_idx]
            total_h = sum(dims[nid][1] for nid in nodes_in_layer)
            total_h += H_GAP * (len(nodes_in_layer) - 1)
            start_y = -total_h / 2

            y_cursor = start_y
            for nid in nodes_in_layer:
                w, h = dims[nid]
                positions[nid] = (x_offsets[layer_idx], y_cursor)
                y_cursor += h + H_GAP

    # Shift to positive coords with margin (+ room for title)
    min_x = min(p[0] for p in positions.values())
    min_y = min(p[1] for p in positions.values())
    title_space = TITLE_FONT_SIZE * 2

    for nid in positions:
        x, y = positions[nid]
        positions[nid] = (
            round(x - min_x + MARGIN),
            round(y - min_y + MARGIN + title_space),
        )

    return positions, dims


def _base_element(etype, **overrides):
    """Create an Excalidraw element with sensible defaults."""
    el = {
        "type": etype,
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 50,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "index": None,
        "roundness": None,
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "boundElements": None,
        "updated": int(time.time() * 1000),
        "link": None,
        "locked": False,
    }
    el.update(overrides)
    return el


def _build_elements(diagram: dict, prefix: str = "") -> tuple[list[dict], float]:
    """Build Excalidraw elements for a single diagram.

    Returns (elements_list, total_height) so the caller can stack diagrams.
    All element IDs are prefixed with `prefix` to avoid collisions.
    """
    nodes = diagram.get("nodes", [])
    connections = diagram.get("connections", [])
    direction = diagram.get("direction", "TB")
    title = diagram.get("name", "Diagram")
    node_map = {n["id"]: n for n in nodes}

    positions, dims = _compute_layout(nodes, connections, direction)

    elements = []

    # --- Title ---
    elements.append(_base_element(
        "text",
        id=f"{prefix}title_{_seed()}",
        x=MARGIN,
        y=MARGIN // 2,
        width=round(len(title) * TITLE_FONT_SIZE * CHAR_WIDTH_RATIO),
        height=round(TITLE_FONT_SIZE * 1.25),
        text=title,
        fontSize=TITLE_FONT_SIZE,
        fontFamily=1,
        textAlign="left",
        verticalAlign="top",
        containerId=None,
        originalText=title,
        autoResize=True,
        lineHeight=1.25,
        strokeColor="#343a40",
    ))

    # Pre-build bound-element lists for each node
    node_bounds = defaultdict(list)
    for conn in connections:
        fid, tid = conn["from"], conn["to"]
        arrow_id = f"{prefix}arrow_{fid}_{tid}"
        if fid in node_map:
            node_bounds[fid].append({"id": arrow_id, "type": "arrow"})
        if tid in node_map:
            node_bounds[tid].append({"id": arrow_id, "type": "arrow"})

    # --- Nodes (shape + bound text) ---
    for node in nodes:
        nid = node["id"]
        label = node["label"]
        color = node.get("color", PALETTE_LIST[hash(nid) % len(PALETTE_LIST)])
        shape = node.get("shape", "rectangle")
        if shape not in ("rectangle", "diamond", "ellipse"):
            shape = "rectangle"

        x, y = positions[nid]
        w, h = dims[nid]
        rect_id = f"{prefix}node_{nid}"
        text_id = f"{prefix}text_{nid}"

        bound = list(node_bounds[nid])
        bound.append({"id": text_id, "type": "text"})

        roundness = {"type": 3} if shape == "rectangle" else {"type": 2}

        elements.append(_base_element(
            shape,
            id=rect_id,
            x=x, y=y,
            width=w, height=h,
            backgroundColor=color,
            boundElements=bound,
            roundness=roundness,
        ))

        lines = label.split("\n")
        line_h = FONT_SIZE * 1.25
        tw = round(max(len(l) for l in lines) * FONT_SIZE * CHAR_WIDTH_RATIO)
        th = round(len(lines) * line_h)

        elements.append(_base_element(
            "text",
            id=text_id,
            x=round(x + (w - tw) / 2),
            y=round(y + (h - th) / 2),
            width=tw,
            height=th,
            text=label,
            fontSize=FONT_SIZE,
            fontFamily=1,
            textAlign="center",
            verticalAlign="middle",
            containerId=rect_id,
            originalText=label,
            autoResize=True,
            lineHeight=1.25,
        ))

    # --- Arrows ---
    for conn in connections:
        fid, tid = conn["from"], conn["to"]
        if fid not in node_map or tid not in node_map:
            continue

        arrow_id = f"{prefix}arrow_{fid}_{tid}"
        conn_label = conn.get("label", "")

        fx, fy = positions[fid]
        fw, fh = dims[fid]
        tx, ty = positions[tid]
        tw, th = dims[tid]

        if direction == "TB":
            sx = fx + fw / 2
            sy = fy + fh
            ex = tx + tw / 2
            ey = ty
        else:
            sx = fx + fw
            sy = fy + fh / 2
            ex = tx
            ey = ty + th / 2

        dx = round(ex - sx)
        dy = round(ey - sy)

        arrow_bounds = []
        if conn_label:
            lbl_id = f"{prefix}arrowlbl_{fid}_{tid}"
            arrow_bounds.append({"id": lbl_id, "type": "text"})

        elements.append(_base_element(
            "arrow",
            id=arrow_id,
            x=round(sx), y=round(sy),
            width=abs(dx), height=abs(dy),
            points=[[0, 0], [dx, dy]],
            lastCommittedPoint=None,
            startBinding={"elementId": f"{prefix}node_{fid}", "focus": 0, "gap": 4},
            endBinding={"elementId": f"{prefix}node_{tid}", "focus": 0, "gap": 4},
            startArrowhead=None,
            endArrowhead="arrow",
            roundness={"type": 2},
            boundElements=arrow_bounds if arrow_bounds else None,
        ))

        if conn_label:
            lbl_w = round(len(conn_label) * 14 * CHAR_WIDTH_RATIO)
            lbl_h = round(14 * 1.25)
            elements.append(_base_element(
                "text",
                id=lbl_id,
                x=round(sx + dx / 2 - lbl_w / 2),
                y=round(sy + dy / 2 - lbl_h / 2),
                width=lbl_w,
                height=lbl_h,
                text=conn_label,
                fontSize=14,
                fontFamily=1,
                textAlign="center",
                verticalAlign="middle",
                containerId=arrow_id,
                originalText=conn_label,
                autoResize=True,
                lineHeight=1.25,
            ))

    # Compute total height (max y + height across all elements)
    total_height = max(el["y"] + el["height"] for el in elements)

    return elements, total_height


def _offset_elements(elements: list[dict], dy: float):
    """Shift all elements vertically by dy. Mutates in place."""
    for el in elements:
        el["y"] = round(el["y"] + dy)
        # Arrow points are relative to el x,y — don't touch them


def _wrap_document(elements: list[dict]) -> dict:
    """Wrap a list of elements into a full Excalidraw document."""
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "#ffffff",
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
        },
        "files": {},
    }


# --- Public API ---

def render_diagram(diagram: dict) -> dict:
    """Convert a single diagram spec into a full Excalidraw document."""
    elements, _ = _build_elements(diagram)
    return _wrap_document(elements)


def render_combined(diagrams: list[dict]) -> dict:
    """Render multiple diagrams into a single Excalidraw document, stacked vertically."""
    all_elements = []
    y_cursor = 0

    for i, diagram in enumerate(diagrams):
        prefix = f"d{i}_"
        elements, height = _build_elements(diagram, prefix)
        if y_cursor > 0:
            _offset_elements(elements, y_cursor)
        all_elements.extend(elements)
        y_cursor += height + DIAGRAM_GAP

    return _wrap_document(all_elements)


def render_to_file(diagram_or_diagrams, output_path: str) -> str:
    """Render diagram(s) to an .excalidraw file.

    Accepts either a single diagram dict or a list of diagram dicts.
    """
    if isinstance(diagram_or_diagrams, list):
        doc = render_combined(diagram_or_diagrams)
    else:
        doc = render_diagram(diagram_or_diagrams)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return output_path
