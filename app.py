#./app.py

"""Minimal Flask backend with chat and streaming endpoints."""

import time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint for testing."""
    data = request.get_json() or {}
    message = data.get("message", "")

    # Mock response
    return jsonify({
        "response": "Hello world!",
        "message_received": message
    })


@app.route("/stream", methods=["POST"])
def stream():
    """SSE streaming endpoint returning mock tokens."""

    def generate():
        tokens = ["Hello", " world", "!"]
        for token in tokens:
            # SSE format: data: <content>\n\n
            yield f"data: {token}\n\n"
            time.sleep(0.2)  # 200ms delay between tokens
        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
