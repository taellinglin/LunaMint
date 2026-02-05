"""Minimal EisenScript API server."""
from __future__ import annotations

import argparse
import json
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

from lunamint.scripting.eisen import parse_script, render_svg, render_html


@dataclass
class ProgressState:
    events: List[str] = field(default_factory=list)
    done: bool = False
    error: Optional[str] = None


_PROGRESS: Dict[str, ProgressState] = {}
_PROGRESS_LOCK = threading.Lock()


def _new_progress() -> str:
    pid = uuid.uuid4().hex
    with _PROGRESS_LOCK:
        _PROGRESS[pid] = ProgressState(events=["queued"], done=False)
    return pid


def _append_progress(pid: str, message: str) -> None:
    with _PROGRESS_LOCK:
        state = _PROGRESS.get(pid)
        if state is None:
            return
        state.events.append(message)


def _finish_progress(pid: str, error: Optional[str] = None) -> None:
    with _PROGRESS_LOCK:
        state = _PROGRESS.get(pid)
        if state is None:
            return
        state.done = True
        state.error = error
        if error:
            state.events.append(f"error:{error}")
        else:
            state.events.append("done")


def _get_progress(pid: str) -> Optional[ProgressState]:
    with _PROGRESS_LOCK:
        state = _PROGRESS.get(pid)
        if state is None:
            return None
        return ProgressState(list(state.events), state.done, state.error)


class EisenHandler(BaseHTTPRequestHandler):
    server_version = "EisenAPI/1.0"

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        try:
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionAbortedError, BrokenPipeError):
            return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/progress/"):
            pid = self.path.split("/progress/", 1)[1].strip()
            state = _get_progress(pid)
            if state is None:
                self._send_json({"error": "unknown id"}, status=404)
                return
            self._send_json(
                {"id": pid, "events": state.events, "done": state.done, "error": state.error}
            )
            return
        self._send_json({"status": "ok", "endpoints": ["POST /render", "GET /progress/<id>"]})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/render":
            self._send_json({"error": "not found"}, status=404)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, status=400)
            return

        script = payload.get("script", "")
        want_html = bool(payload.get("html", False))
        if not script or not isinstance(script, str):
            self._send_json({"error": "script is required"}, status=400)
            return

        pid = _new_progress()
        try:
            _append_progress(pid, "parse")
            program = parse_script(script)
            with tempfile.TemporaryDirectory() as tmpdir:
                out_dir = Path(tmpdir)
                svg_path = out_dir / "eisen.svg"
                _append_progress(pid, "render_svg")
                render_svg(program, svg_path)
                svg_text = svg_path.read_text(encoding="utf-8")
                html_text = None
                if want_html:
                    html_path = out_dir / "eisen.html"
                    _append_progress(pid, "render_html")
                    render_html(program, html_path, svg_path=svg_path)
                    html_text = html_path.read_text(encoding="utf-8")
            _finish_progress(pid)
            self._send_json({"id": pid, "svg": svg_text, "html": html_text})
        except Exception as exc:
            _finish_progress(pid, error=str(exc))
            try:
                self._send_json({"id": pid, "error": str(exc)}, status=400)
            except (ConnectionAbortedError, BrokenPipeError):
                return


def main() -> int:
    parser = argparse.ArgumentParser(description="EisenScript API server")
    parser.add_argument("--api", action="store_true", help="Start API server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    args = parser.parse_args()

    if not args.api:
        parser.print_help()
        return 0

    server = ThreadingHTTPServer((args.host, args.port), EisenHandler)
    print(f"[+] EisenScript API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
