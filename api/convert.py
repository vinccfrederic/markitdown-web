import os
import tempfile
from flask import Flask, request, Response
from markitdown import MarkItDown

app = Flask(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

MAX_SIZE_MB = 50
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


@app.route("/api/convert", methods=["POST", "OPTIONS"])
@app.route("/", methods=["POST", "OPTIONS"])
def convert():
    # CORS preflight
    if request.method == "OPTIONS":
        return Response("", status=204, headers=CORS_HEADERS)

    file = request.files.get("file")
    if not file or not file.filename:
        return Response("No file provided.", status=400, headers=CORS_HEADERS)

    # Check size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE_BYTES:
        return Response(
            f"File too large (max {MAX_SIZE_MB} MB).", status=413, headers=CORS_HEADERS
        )

    # Preserve original extension so markitdown can detect the type
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower() or ".bin"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            file.save(tmp)

        mid = MarkItDown()
        result = mid.convert(tmp_path)
        md_text = result.text_content or ""

        if not md_text.strip():
            return Response(
                "Conversion produced no output. File type may not be supported.",
                status=422,
                headers=CORS_HEADERS,
            )

        return Response(
            md_text,
            status=200,
            mimetype="text/plain; charset=utf-8",
            headers=CORS_HEADERS,
        )

    except Exception as exc:
        return Response(f"Conversion error: {exc}", status=500, headers=CORS_HEADERS)

    finally:
        # Always delete the temp file — nothing persists
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
