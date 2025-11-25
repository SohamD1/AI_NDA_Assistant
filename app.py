"""Flask backend with Anthropic Claude streaming, tool use, and conversation memory."""

import os
import json
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
import anthropic

from tools import TOOLS, execute_tool
from system_prompt import SYSTEM_PROMPT

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model configuration
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
MAX_HISTORY_LENGTH = 20  # Keep last 20 messages

# In-memory conversation storage (per session)
# In production, use Redis, database, or session storage
conversations = {}


def get_conversation(session_id: str) -> list:
    """Get conversation history for a session."""
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]


def add_to_conversation(session_id: str, role: str, content) -> list:
    """
    Add a message to conversation history and trim to MAX_HISTORY_LENGTH.

    Args:
        session_id: Unique session identifier
        role: 'user' or 'assistant'
        content: Message content (string or list of content blocks)

    Returns:
        Updated conversation history
    """
    history = get_conversation(session_id)

    # Add new message
    history.append({"role": role, "content": content})

    # Trim to keep only last MAX_HISTORY_LENGTH messages
    # But ensure we don't cut in the middle of a tool use exchange
    if len(history) > MAX_HISTORY_LENGTH:
        # Find a safe trim point (not in middle of tool use)
        trim_start = len(history) - MAX_HISTORY_LENGTH

        # Make sure we start with a user message for valid conversation
        while trim_start < len(history):
            if history[trim_start]["role"] == "user":
                # Check if it's a tool_result (which needs the preceding assistant message)
                content = history[trim_start]["content"]
                if isinstance(content, list) and content and isinstance(content[0], dict):
                    if content[0].get("type") == "tool_result":
                        trim_start += 1
                        continue
                break
            trim_start += 1

        conversations[session_id] = history[trim_start:]

    return conversations[session_id]


def clear_conversation(session_id: str):
    """Clear conversation history for a session."""
    if session_id in conversations:
        del conversations[session_id]


def serialize_content_for_history(content) -> list:
    """
    Convert Anthropic content blocks to serializable format for history.

    Args:
        content: Content from Anthropic response (list of content blocks)

    Returns:
        Serializable list of content dictionaries
    """
    if isinstance(content, str):
        return content

    serialized = []
    for block in content:
        if hasattr(block, "type"):
            if block.type == "text":
                serialized.append({
                    "type": "text",
                    "text": block.text
                })
            elif block.type == "tool_use":
                serialized.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        elif isinstance(block, dict):
            serialized.append(block)

    return serialized


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint with tool support and memory."""
    data = request.get_json() or {}
    message = data.get("message", "")
    session_id = data.get("session_id", "default")

    # Get existing conversation history
    history = get_conversation(session_id)

    # Build messages with history
    messages = history + [{"role": "user", "content": message}]

    # Initial response
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages
    )

    # Track messages added during this turn for history
    turn_messages = [{"role": "user", "content": message}]

    # Handle tool use loop
    while response.stop_reason == "tool_use":
        # Find tool use blocks
        tool_uses = [block for block in response.content if block.type == "tool_use"]

        # Execute each tool and collect results
        tool_results = []
        for tool_use in tool_uses:
            result = execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })

        # Add assistant response and tool results to messages
        assistant_content = serialize_content_for_history(response.content)
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        # Track for history
        turn_messages.append({"role": "assistant", "content": assistant_content})
        turn_messages.append({"role": "user", "content": tool_results})

        # Continue conversation
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

    # Extract final text response
    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    # Add final assistant response to turn messages
    final_content = serialize_content_for_history(response.content)
    turn_messages.append({"role": "assistant", "content": final_content})

    # Save all turn messages to history
    for msg in turn_messages:
        add_to_conversation(session_id, msg["role"], msg["content"])

    return jsonify({
        "response": text_content,
        "message_received": message,
        "session_id": session_id,
        "history_length": len(get_conversation(session_id))
    })


@app.route("/stream", methods=["POST"])
def stream():
    """SSE streaming endpoint with tool use support and memory."""
    data = request.get_json() or {}
    message = data.get("message", "")
    session_id = data.get("session_id", "default")

    def generate():
        # Get existing conversation history
        history = get_conversation(session_id)

        # Build messages from history
        messages = history + [{"role": "user", "content": message}]

        # Track messages for this turn
        turn_messages = [{"role": "user", "content": message}]

        # Loop to handle multiple tool calls
        while True:
            current_tool_use = None
            current_tool_input = ""

            # Stream the response
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            ) as stream_response:

                for event in stream_response:
                    # Handle different event types
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            pass
                        elif event.content_block.type == "tool_use":
                            current_tool_use = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {}
                            }
                            current_tool_input = ""
                            yield f"data: [TOOL_START:{event.content_block.name}]\n\n"

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield f"data: {event.delta.text}\n\n"
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_input += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_use is not None:
                            try:
                                current_tool_use["input"] = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            current_tool_use = None
                            current_tool_input = ""

                final_message = stream_response.get_final_message()

            # Check if we need to handle tool use
            if final_message.stop_reason == "tool_use":
                tool_use_blocks = [
                    block for block in final_message.content
                    if block.type == "tool_use"
                ]

                tool_results = []
                for tool_block in tool_use_blocks:
                    yield f"data: [TOOL_EXECUTING:{tool_block.name}]\n\n"
                    result = execute_tool(tool_block.name, tool_block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result
                    })
                    yield f"data: [TOOL_RESULT:{tool_block.name}]\n\n"

                # Serialize and add to messages
                assistant_content = serialize_content_for_history(final_message.content)
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

                # Track for history
                turn_messages.append({"role": "assistant", "content": assistant_content})
                turn_messages.append({"role": "user", "content": tool_results})

            else:
                # Final response - save to history
                final_content = serialize_content_for_history(final_message.content)
                turn_messages.append({"role": "assistant", "content": final_content})

                # Save all turn messages to conversation history
                for msg in turn_messages:
                    add_to_conversation(session_id, msg["role"], msg["content"])

                break

        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/history", methods=["GET"])
def get_history():
    """Get conversation history for a session."""
    session_id = request.args.get("session_id", "default")
    history = get_conversation(session_id)

    return jsonify({
        "session_id": session_id,
        "history": history,
        "message_count": len(history)
    })


@app.route("/history", methods=["DELETE"])
def delete_history():
    """Clear conversation history for a session."""
    session_id = request.args.get("session_id", "default")
    clear_conversation(session_id)

    return jsonify({
        "session_id": session_id,
        "status": "cleared"
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
