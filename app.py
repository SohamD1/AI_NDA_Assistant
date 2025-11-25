"""Flask backend with Anthropic Claude streaming and tool use integration."""

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


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming chat endpoint with tool support."""
    data = request.get_json() or {}
    message = data.get("message", "")
    conversation_history = data.get("history", [])

    # Build messages
    messages = conversation_history + [{"role": "user", "content": message}]

    # Initial response
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages
    )

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
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

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

    return jsonify({
        "response": text_content,
        "message_received": message
    })


@app.route("/stream", methods=["POST"])
def stream():
    """SSE streaming endpoint with tool use support."""
    data = request.get_json() or {}
    message = data.get("message", "")
    conversation_history = data.get("history", [])

    def generate():
        # Build messages from history
        messages = conversation_history + [{"role": "user", "content": message}]

        # Loop to handle multiple tool calls
        while True:
            # Collect the full response to check for tool use
            collected_content = []
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
                            # Text block starting
                            pass
                        elif event.content_block.type == "tool_use":
                            # Tool use block starting
                            current_tool_use = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {}
                            }
                            current_tool_input = ""
                            # Notify frontend that a tool is being called
                            yield f"data: [TOOL_START:{event.content_block.name}]\n\n"

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            # Stream text to client
                            yield f"data: {event.delta.text}\n\n"
                        elif hasattr(event.delta, "partial_json"):
                            # Accumulate tool input JSON
                            current_tool_input += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_use is not None:
                            # Parse the accumulated tool input
                            try:
                                current_tool_use["input"] = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            collected_content.append(current_tool_use)
                            current_tool_use = None
                            current_tool_input = ""

                # Get the final message for stop reason
                final_message = stream_response.get_final_message()

            # Check if we need to handle tool use
            if final_message.stop_reason == "tool_use":
                # Find all tool use blocks from the response
                tool_use_blocks = [
                    block for block in final_message.content
                    if block.type == "tool_use"
                ]

                # Execute tools and collect results
                tool_results = []
                for tool_block in tool_use_blocks:
                    yield f"data: [TOOL_EXECUTING:{tool_block.name}]\n\n"

                    # Execute the tool
                    result = execute_tool(tool_block.name, tool_block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result
                    })

                    yield f"data: [TOOL_RESULT:{tool_block.name}]\n\n"

                # Add assistant response and tool results to message history
                messages.append({"role": "assistant", "content": final_message.content})
                messages.append({"role": "user", "content": tool_results})

                # Continue the loop to get Claude's response after tool execution

            else:
                # No more tool calls, we're done
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
