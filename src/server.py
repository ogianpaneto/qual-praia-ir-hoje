from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from generate_index import generate_index


ROOT_DIR = Path(__file__).resolve().parent.parent


class PraiaRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def do_POST(self):
        if urlparse(self.path).path != "/api/regenerate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            result = generate_index()
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"ok": False, "message": str(exc)}).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        payload = json.dumps(
            {
                "ok": True,
                "message": f"Índice atualizado em {result['generated_at']}",
                "generated_at": result["generated_at"],
                "beaches": len(result.get("beaches", [])),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("localhost", 8000), PraiaRequestHandler)
    print("Servidor em http://localhost:8000/web/")
    print("POST /api/regenerate para recalcular o índice.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()