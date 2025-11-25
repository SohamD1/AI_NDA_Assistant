#tools.py

import json

# ---------------------------------------------------------
# 1. TOOL DEFINITIONS
# These are sent to Claude so it knows how to format its requests.
# ---------------------------------------------------------

TOOLS = [
    {
        "name": "extract_information",
        "description": "Extracts and saves structured data from the conversation to the session memory. Use this immediately when the user provides specific details like names, dates, or jurisdiction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "party_a": {
                    "type": "string",
                    "description": "Full legal name of the Disclosing Party (or first party)."
                },
                "party_b": {
                    "type": "string",
                    "description": "Full legal name of the Receiving Party (or second party)."
                },
                "effective_date": {
                    "type": "string",
                    "description": "The effective date of the agreement (e.g., '2024-01-01' or 'Immediate')."
                },
                "purpose": {
                    "type": "string",
                    "description": "The specific reason for the NDA (e.g., 'Potential Partnership', 'Employment')."
                },
                "is_mutual": {
                    "type": "boolean",
                    "description": "True if both parties are disclosing information; False if one-way."
                }
            },
            "required": ["party_a"]
        }
    },
    {
        "name": "generate_document",
        "description": "Generates the initial NDA document based on gathered information. The input must be the FULL, valid LaTeX code. Calling this triggers the split-screen renderer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latex_content": {
                    "type": "string",
                    "description": "The complete, compilable LaTeX code for the NDA. Must include \\documentclass{article}, preamble, and document body."
                }
            },
            "required": ["latex_content"]
        }
    },
    {
        "name": "apply_edits",
        "description": "Applies specific edits to the existing NDA document. The input must be the FULL, updated LaTeX code (not just the diff).",
        "input_schema": {
            "type": "object",
            "properties": {
                "latex_content": {
                    "type": "string",
                    "description": "The complete, updated LaTeX code including the requested changes."
                }
            },
            "required": ["latex_content"]
        }
    }
]


# ---------------------------------------------------------
# 2. TOOL EXECUTION LOGIC
# This function is called by app.py when Claude uses a tool.
# ---------------------------------------------------------

def execute_tool(tool_name, tool_input):
    """
    Executes the tool requested by the LLM.
    
    Args:
        tool_name (str): The name of the tool (e.g., 'extract_information').
        tool_input (dict): The arguments provided by the LLM.

    Returns:
        str: The result of the tool execution to be returned to the LLM.
    """
    
    try:
        if tool_name == "extract_information":
            # In a real app, you would save this to a database here.
            # For this demo, we just acknowledge the data was "saved".
            
            saved_fields = ", ".join(tool_input.keys())
            print(f"✅ [TOOL] Information extracted: {json.dumps(tool_input, indent=2)}")
            return f"Success. The following details have been saved to the session memory: {saved_fields}. You may proceed to generate the document if sufficient info is present."

        elif tool_name == "generate_document":
            # The actual streaming of the LaTeX to the frontend happens in app.py
            # via the [LATEX_DELTA] events. 
            # This function just confirms to the LLM that the rendering happened.
            
            # Note: We do NOT return the full latex content back to the LLM context 
            # to save context window space, unless specifically needed.
            print("✅ [TOOL] Document generated and sent to frontend renderer.")
            return "Document successfully rendered on the right-side interface."

        elif tool_name == "apply_edits":
            # Similar to generate_document, the frontend handles the update.
            print("✅ [TOOL] Document edits applied and sent to frontend renderer.")
            return "Document edits successfully applied and rendered on the right-side interface."

        else:
            return f"Error: Unknown tool '{tool_name}'."

    except Exception as e:
        return f"Error executing tool {tool_name}: {str(e)}"
