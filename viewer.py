"""Local Excalidraw viewer — serves .excalidraw files in the browser with the full editor."""

import http.server
import json
import os
import webbrowser

DEFAULT_PORT = 8765

EXCALIDRAW_VERSION = "0.18.0"

# Uses .replace() for templating to avoid brace-escaping hell
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>

  <!-- Excalidraw stylesheet -->
  <link rel="stylesheet" href="https://unpkg.com/@excalidraw/excalidraw@__VER__/dist/prod/index.css" />

  <!-- Font + asset path (Virgil, Cascadia, etc.) -->
  <script>
    window.EXCALIDRAW_ASSET_PATH = "https://unpkg.com/@excalidraw/excalidraw@__VER__/dist/prod/";
  </script>

  <!-- Import map — single React instance shared between our code and Excalidraw -->
  <script type="importmap">
    {
      "imports": {
        "react": "https://esm.sh/react@18.3.1",
        "react/": "https://esm.sh/react@18.3.1/",
        "react-dom": "https://esm.sh/react-dom@18.3.1",
        "react-dom/": "https://esm.sh/react-dom@18.3.1/"
      }
    }
  </script>

  <style>
    html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }
    #root { width: 100%; height: 100%; }
    .loading {
      display: flex; justify-content: center; align-items: center;
      height: 100vh; font-family: system-ui, sans-serif; color: #888; font-size: 18px;
    }
  </style>
</head>
<body>
  <div id="root"><div class="loading">Loading Excalidraw…</div></div>

  <script type="module">
    import React, { createElement as h } from "react";
    import { createRoot } from "react-dom/client";
    import { Excalidraw } from "https://esm.sh/@excalidraw/excalidraw@__VER__?external=react,react-dom";

    const initialData = __DATA__;

    function App() {
      return h("div", { style: { width: "100vw", height: "100vh" } },
        h(Excalidraw, { initialData })
      );
    }

    createRoot(document.getElementById("root")).render(h(App));
  </script>
</body>
</html>""".replace("__VER__", EXCALIDRAW_VERSION)


def _render_page(data_json: str, title: str) -> str:
    return HTML_TEMPLATE.replace("__TITLE__", title).replace("__DATA__", data_json)


def _index_page(names: list[str]) -> str:
    links = "\n".join(
        f'<li><a href="/{n}">{n.replace("_", " ")}</a></li>' for n in names
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Diagrams</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 60px auto; color: #333; }}
  h1 {{ font-weight: 400; }}
  a {{ color: #5b21b6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  li {{ margin: 12px 0; font-size: 1.1em; }}
</style>
</head><body>
<h1>Generated Diagrams</h1>
<ul>{links}</ul>
</body></html>"""


def serve(file_paths: list[str], port: int = DEFAULT_PORT):
    """Start a local server and open .excalidraw files in the browser."""
    diagrams = {}
    for path in file_paths:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            diagrams[name] = json.load(f)

    index = _index_page(list(diagrams.keys()))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            key = self.path.strip("/")
            if not key:
                body = index.encode()
            elif key in diagrams:
                body = _render_page(json.dumps(diagrams[key]), key.replace("_", " ")).encode()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)

    url = f"http://127.0.0.1:{port}"
    if len(diagrams) == 1:
        url += f"/{list(diagrams.keys())[0]}"
    webbrowser.open(url)

    print(f"Viewer at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\nStopped.")


if __name__ == "__main__":
    import glob
    import sys

    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(glob.glob("output/*.excalidraw"))
    if not files:
        print("No .excalidraw files found.")
        raise SystemExit(1)

    serve(files)
