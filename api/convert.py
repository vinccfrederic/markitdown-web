import os
import logging
import tempfile
from flask import Flask, request, Response, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from markitdown import MarkItDown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

MAX_SIZE_MB = 50
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

md = MarkItDown()

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".html", ".htm", ".csv", ".json",
    ".xml", ".txt", ".zip", ".md",
}


@app.errorhandler(429)
def rate_limit_handler(e):
    return Response(
        "Too many requests — please wait a moment before converting again.",
        status=429,
        headers=CORS_HEADERS,
    )


@app.route("/health", methods=["GET"])
def health():
    return Response("ok", status=200)


@app.route("/", methods=["GET"])
def index():
    with open(os.path.join(ROOT, "index.html")) as f:
        return Response(f.read(), mimetype="text/html")


@app.route("/api/convert", methods=["POST", "OPTIONS"])
@app.route("/", methods=["POST", "OPTIONS"])
@limiter.limit("10 per minute", error_message="Too many requests — please wait a moment before converting again.")
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

    # Sanitize: extract only the extension, ignore the rest of the filename
    _, ext = os.path.splitext(file.filename)
    ext = ext.lower()

    if not ext or ext not in ALLOWED_EXTENSIONS:
        return Response(
            f"Unsupported file type '{ext or '(none)'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            status=415,
            headers=CORS_HEADERS,
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            file.save(tmp)

        result = md.convert(tmp_path)
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
        logger.error("Conversion failed for file '%s': %s", file.filename, exc, exc_info=True)
        return Response(
            "Conversion failed. The file may be corrupted or unsupported.",
            status=500,
            headers=CORS_HEADERS,
        )

    finally:
        # Always delete the temp file — nothing persists
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
