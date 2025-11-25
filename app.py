"""Flask backend with Anthropic Claude streaming integration."""

import os
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
import anthropic

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint."""
    data = request.get_json() or {}
    message = data.get("message", "")

    # Use Claude for non-streaming response
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": message}]
    )

    return jsonify({
        "response": response.content[0].text,
        "message_received": message
    })


@app.route("/stream", methods=["POST"])
def stream():
    """SSE streaming endpoint using Anthropic Claude."""
    data = request.get_json() or {}
    message = data.get("message", "")

    def generate():
        # Use Claude streaming API
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": message}]
        ) as stream:
            for text in stream.text_stream:
                # SSE format: data: <content>\n\n
                yield f"data: {text}\n\n"

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
