"""Claude tool definitions and execution functions for the legal document assistant."""

import json
import re
from datetime import datetime
from typing import Optional

# =============================================================================
# Tool Definitions (JSON schemas for Claude)
# =============================================================================

EXTRACT_INFORMATION = {
    "name": "extract_information",
    "description": "Extract structured information from text. Use this to pull out specific data points, entities, facts, or key details from unstructured content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_text": {
                "type": "string",
                "description": "The text to extract information from"
            },
            "extraction_type": {
                "type": "string",
                "enum": ["entities", "facts", "key_points", "metadata", "custom"],
                "description": "The type of information to extract"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific fields or data points to extract (e.g., ['name', 'date', 'location'])"
            },
            "output_format": {
                "type": "string",
                "enum": ["json", "markdown", "plain_text"],
                "default": "json",
                "description": "Format for the extracted information"
            }
        },
        "required": ["source_text", "extraction_type"]
    }
}

GENERATE_DOCUMENT = {
    "name": "generate_document",
    "description": "Generate a structured document based on specifications. Use this to create reports, summaries, articles, or other formatted content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": ["report", "summary", "article", "email", "memo", "proposal", "custom"],
                "description": "The type of document to generate"
            },
            "title": {
                "type": "string",
                "description": "Title or subject of the document"
            },
            "content_requirements": {
                "type": "string",
                "description": "Description of what the document should contain"
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of sections to include (e.g., ['Introduction', 'Analysis', 'Conclusion'])"
            },
            "tone": {
                "type": "string",
                "enum": ["formal", "informal", "technical", "casual", "professional"],
                "default": "professional",
                "description": "Writing tone for the document"
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum length in words (optional)"
            }
        },
        "required": ["document_type", "title", "content_requirements"]
    }
}

APPLY_EDITS = {
    "name": "apply_edits",
    "description": "Apply edits or modifications to existing text. Use this to revise, reformat, correct, or transform content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "original_text": {
                "type": "string",
                "description": "The original text to be edited"
            },
            "edit_type": {
                "type": "string",
                "enum": ["grammar", "style", "tone", "format", "simplify", "expand", "translate", "custom"],
                "description": "The type of edit to apply"
            },
            "instructions": {
                "type": "string",
                "description": "Specific instructions for how to edit the text"
            },
            "preserve_meaning": {
                "type": "boolean",
                "default": True,
                "description": "Whether to preserve the original meaning while editing"
            },
            "target_language": {
                "type": "string",
                "description": "Target language for translation (only used when edit_type is 'translate')"
            }
        },
        "required": ["original_text", "edit_type"]
    }
}

# List of all tools for easy import
TOOLS = [EXTRACT_INFORMATION, GENERATE_DOCUMENT, APPLY_EDITS]


# =============================================================================
# Tool Execution Functions
# =============================================================================

def extract_information(source_text: str, extraction_type: str,
                        fields: Optional[list] = None,
                        output_format: str = "json") -> dict:
    """
    Extract structured information from text.

    Args:
        source_text: The text to analyze
        extraction_type: Type of extraction (entities, facts, key_points, metadata, custom)
        fields: Specific fields to extract for custom extraction
        output_format: Output format (json, markdown, plain_text)

    Returns:
        Dictionary with extracted information
    """
    result = {
        "success": True,
        "extraction_type": extraction_type,
        "source_stats": {
            "character_count": len(source_text),
            "word_count": len(source_text.split()),
            "line_count": len(source_text.splitlines())
        },
        "extracted_data": {}
    }

    if extraction_type == "entities":
        result["extracted_data"] = _extract_entities(source_text)
    elif extraction_type == "facts":
        result["extracted_data"] = _extract_facts(source_text)
    elif extraction_type == "key_points":
        result["extracted_data"] = _extract_key_points(source_text)
    elif extraction_type == "metadata":
        result["extracted_data"] = _extract_metadata(source_text)
    elif extraction_type == "custom" and fields:
        result["extracted_data"] = _extract_custom_fields(source_text, fields)
    else:
        result["extracted_data"] = {"raw_text_preview": source_text[:500]}

    # Format output
    if output_format == "markdown":
        return _format_as_markdown(result)
    elif output_format == "plain_text":
        return _format_as_plain_text(result)

    return result


def _extract_entities(text: str) -> dict:
    """Extract named entities from text using pattern matching."""
    entities = {
        "parties": [],
        "dates": [],
        "monetary_values": [],
        "percentages": [],
        "durations": [],
        "emails": [],
        "addresses": []
    }

    # Extract dates (various formats)
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
    ]
    for pattern in date_patterns:
        entities["dates"].extend(re.findall(pattern, text, re.IGNORECASE))

    # Extract monetary values
    money_pattern = r'\$[\d,]+(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars|USD|EUR|GBP)\b'
    entities["monetary_values"] = re.findall(money_pattern, text, re.IGNORECASE)

    # Extract percentages
    percent_pattern = r'\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*percent\b'
    entities["percentages"] = re.findall(percent_pattern, text, re.IGNORECASE)

    # Extract durations
    duration_pattern = r'\b\d+\s*(?:days?|weeks?|months?|years?|hours?|minutes?)\b'
    entities["durations"] = re.findall(duration_pattern, text, re.IGNORECASE)

    # Extract emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    entities["emails"] = re.findall(email_pattern, text)

    # Extract potential party names (capitalized phrases after common indicators)
    party_indicators = r'(?:between|by and between|party|parties|company|corporation|llc|inc|ltd)\s*[:\s]*([A-Z][A-Za-z\s,\.]+?)(?=\s*(?:and|,|\(|$))'
    entities["parties"] = re.findall(party_indicators, text, re.IGNORECASE)

    # Clean up empty lists
    return {k: list(set(v)) for k, v in entities.items() if v}


def _extract_facts(text: str) -> dict:
    """Extract factual statements and obligations from text."""
    facts = {
        "obligations": [],
        "conditions": [],
        "prohibitions": [],
        "definitions": []
    }

    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        lower_sentence = sentence.lower()

        # Obligations (shall, must, will, agrees to)
        if any(word in lower_sentence for word in ['shall', 'must', 'agrees to', 'is required to', 'will provide', 'will deliver']):
            facts["obligations"].append(sentence[:200])

        # Conditions (if, unless, provided that, subject to)
        if any(phrase in lower_sentence for phrase in ['if ', 'unless ', 'provided that', 'subject to', 'in the event']):
            facts["conditions"].append(sentence[:200])

        # Prohibitions (shall not, may not, prohibited, forbidden)
        if any(phrase in lower_sentence for phrase in ['shall not', 'may not', 'prohibited', 'forbidden', 'not permitted']):
            facts["prohibitions"].append(sentence[:200])

        # Definitions (means, refers to, defined as)
        if any(phrase in lower_sentence for phrase in ['" means', "' means", 'refers to', 'defined as', 'shall mean']):
            facts["definitions"].append(sentence[:200])

    # Limit to most relevant items
    return {k: v[:10] for k, v in facts.items() if v}


def _extract_key_points(text: str) -> dict:
    """Extract key points and summary information."""
    key_points = {
        "summary_sentences": [],
        "important_terms": [],
        "action_items": [],
        "deadlines": []
    }

    sentences = re.split(r'[.!?]+', text)

    # Get first few sentences as summary
    key_points["summary_sentences"] = [s.strip()[:200] for s in sentences[:3] if s.strip()]

    # Find action items
    action_keywords = ['must', 'shall', 'will', 'need to', 'required to', 'responsible for']
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in action_keywords):
            key_points["action_items"].append(sentence.strip()[:200])
            if len(key_points["action_items"]) >= 5:
                break

    # Find deadlines
    deadline_pattern = r'(?:by|before|within|no later than|deadline)[:\s]+([^.]+)'
    key_points["deadlines"] = re.findall(deadline_pattern, text, re.IGNORECASE)[:5]

    # Extract important capitalized terms (potential definitions)
    term_pattern = r'"([A-Z][^"]+)"'
    key_points["important_terms"] = list(set(re.findall(term_pattern, text)))[:10]

    return {k: v for k, v in key_points.items() if v}


def _extract_metadata(text: str) -> dict:
    """Extract document metadata."""
    metadata = {
        "document_type": "Unknown",
        "word_count": len(text.split()),
        "character_count": len(text),
        "paragraph_count": len([p for p in text.split('\n\n') if p.strip()]),
        "estimated_reading_time_minutes": max(1, len(text.split()) // 200),
        "sections_detected": [],
        "has_signature_block": False,
        "language": "English"
    }

    # Detect document type
    lower_text = text.lower()
    if 'non-disclosure' in lower_text or 'confidentiality agreement' in lower_text:
        metadata["document_type"] = "Non-Disclosure Agreement (NDA)"
    elif 'employment' in lower_text and 'agreement' in lower_text:
        metadata["document_type"] = "Employment Agreement"
    elif 'service agreement' in lower_text or 'services agreement' in lower_text:
        metadata["document_type"] = "Service Agreement"
    elif 'lease' in lower_text:
        metadata["document_type"] = "Lease Agreement"
    elif 'purchase' in lower_text and 'agreement' in lower_text:
        metadata["document_type"] = "Purchase Agreement"
    elif 'terms of service' in lower_text or 'terms and conditions' in lower_text:
        metadata["document_type"] = "Terms of Service"
    elif 'privacy policy' in lower_text:
        metadata["document_type"] = "Privacy Policy"

    # Detect sections
    section_pattern = r'^(?:ARTICLE|SECTION|CLAUSE|\d+\.|\([a-z]\)|\([0-9]+\))\s*[A-Z]+'
    metadata["sections_detected"] = re.findall(section_pattern, text, re.MULTILINE)[:20]

    # Check for signature block
    metadata["has_signature_block"] = any(phrase in lower_text for phrase in
        ['signature:', 'signed:', 'in witness whereof', 'executed as of', 'authorized signature'])

    return metadata


def _extract_custom_fields(text: str, fields: list) -> dict:
    """Extract custom specified fields from text."""
    extracted = {}
    lower_text = text.lower()

    for field in fields:
        field_lower = field.lower().replace('_', ' ')

        # Try to find content after field name
        patterns = [
            rf'{field_lower}[:\s]+([^.\n]+)',
            rf'{field_lower}\s*[:=]\s*([^.\n]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, lower_text, re.IGNORECASE)
            if matches:
                extracted[field] = matches[0].strip()[:200]
                break

        if field not in extracted:
            extracted[field] = f"[Not found in document - searched for '{field}']"

    return extracted


def _format_as_markdown(result: dict) -> str:
    """Format extraction result as markdown."""
    md = f"# Extraction Results\n\n"
    md += f"**Type:** {result['extraction_type']}\n\n"
    md += f"## Source Statistics\n"
    for key, value in result['source_stats'].items():
        md += f"- {key.replace('_', ' ').title()}: {value}\n"
    md += f"\n## Extracted Data\n\n"

    for key, value in result['extracted_data'].items():
        md += f"### {key.replace('_', ' ').title()}\n"
        if isinstance(value, list):
            for item in value:
                md += f"- {item}\n"
        else:
            md += f"{value}\n"
        md += "\n"

    return md


def _format_as_plain_text(result: dict) -> str:
    """Format extraction result as plain text."""
    lines = [f"Extraction Type: {result['extraction_type']}", ""]

    for key, value in result['extracted_data'].items():
        lines.append(f"{key.upper()}:")
        if isinstance(value, list):
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"  {value}")
        lines.append("")

    return "\n".join(lines)


def generate_document(document_type: str, title: str, content_requirements: str,
                      sections: Optional[list] = None, tone: str = "professional",
                      max_length: Optional[int] = None) -> dict:
    """
    Generate a structured document based on specifications.

    Args:
        document_type: Type of document (report, summary, article, etc.)
        title: Title of the document
        content_requirements: Description of required content
        sections: List of section names to include
        tone: Writing tone (formal, informal, etc.)
        max_length: Maximum word count

    Returns:
        Dictionary with generated document
    """
    result = {
        "success": True,
        "document_type": document_type,
        "title": title,
        "tone": tone,
        "generated_at": datetime.now().isoformat(),
        "content": "",
        "metadata": {
            "sections_count": 0,
            "estimated_word_count": 0
        }
    }

    # Default sections based on document type
    if sections is None:
        sections = _get_default_sections(document_type)

    # Generate document structure
    doc_content = _build_document(document_type, title, content_requirements, sections, tone)

    # Apply max length if specified
    if max_length:
        words = doc_content.split()
        if len(words) > max_length:
            doc_content = ' '.join(words[:max_length]) + "\n\n[Document truncated to meet length requirement]"

    result["content"] = doc_content
    result["metadata"]["sections_count"] = len(sections)
    result["metadata"]["estimated_word_count"] = len(doc_content.split())

    return result


def _get_default_sections(document_type: str) -> list:
    """Get default sections for a document type."""
    defaults = {
        "report": ["Executive Summary", "Introduction", "Findings", "Analysis", "Recommendations", "Conclusion"],
        "summary": ["Overview", "Key Points", "Details", "Conclusion"],
        "article": ["Introduction", "Background", "Main Content", "Conclusion"],
        "email": ["Greeting", "Purpose", "Details", "Call to Action", "Closing"],
        "memo": ["To/From/Date/Subject", "Purpose", "Background", "Discussion", "Action Required"],
        "proposal": ["Executive Summary", "Problem Statement", "Proposed Solution", "Implementation", "Timeline", "Budget", "Conclusion"],
        "custom": ["Introduction", "Body", "Conclusion"]
    }
    return defaults.get(document_type, defaults["custom"])


def _build_document(document_type: str, title: str, requirements: str, sections: list, tone: str) -> str:
    """Build the document content."""
    tone_style = {
        "formal": {"greeting": "Dear Sir/Madam,", "closing": "Respectfully,"},
        "informal": {"greeting": "Hi,", "closing": "Best,"},
        "technical": {"greeting": "", "closing": ""},
        "casual": {"greeting": "Hey,", "closing": "Cheers,"},
        "professional": {"greeting": "Dear [Recipient],", "closing": "Best regards,"}
    }

    style = tone_style.get(tone, tone_style["professional"])

    doc = f"""{'=' * 60}
{title.upper()}
{'=' * 60}

Document Type: {document_type.title()}
Date: {datetime.now().strftime('%B %d, %Y')}
Tone: {tone.title()}

---

CONTENT REQUIREMENTS:
{requirements}

---

"""

    for i, section in enumerate(sections, 1):
        doc += f"""
{i}. {section.upper()}
{'-' * 40}

[Content for "{section}" section]

This section should address the following based on requirements:
- Relevant points from: {requirements[:100]}...
- Appropriate {tone} tone throughout
- Clear and concise language

"""

    doc += f"""
---

NOTES:
- This is a generated document structure
- Please review and fill in the bracketed sections
- Customize content to match specific needs
- Have legal counsel review before finalizing (if applicable)

{'=' * 60}
Generated by LexiDoc Assistant
{'=' * 60}
"""

    return doc


def apply_edits(original_text: str, edit_type: str, instructions: Optional[str] = None,
                preserve_meaning: bool = True, target_language: Optional[str] = None) -> dict:
    """
    Apply edits or modifications to existing text.

    Args:
        original_text: The text to edit
        edit_type: Type of edit to apply
        instructions: Specific editing instructions
        preserve_meaning: Whether to preserve original meaning
        target_language: Target language for translation

    Returns:
        Dictionary with edited text and change summary
    """
    result = {
        "success": True,
        "edit_type": edit_type,
        "preserve_meaning": preserve_meaning,
        "original": {
            "text": original_text,
            "word_count": len(original_text.split()),
            "character_count": len(original_text)
        },
        "edited": {
            "text": "",
            "word_count": 0,
            "character_count": 0
        },
        "changes": []
    }

    edited_text = original_text
    changes = []

    if edit_type == "grammar":
        edited_text, changes = _apply_grammar_fixes(original_text)
    elif edit_type == "simplify":
        edited_text, changes = _apply_simplification(original_text)
    elif edit_type == "format":
        edited_text, changes = _apply_formatting(original_text)
    elif edit_type == "expand":
        edited_text, changes = _apply_expansion(original_text, instructions)
    elif edit_type == "tone":
        edited_text, changes = _apply_tone_change(original_text, instructions)
    elif edit_type == "style":
        edited_text, changes = _apply_style_change(original_text, instructions)
    elif edit_type == "translate":
        edited_text, changes = _apply_translation(original_text, target_language)
    elif edit_type == "custom":
        edited_text, changes = _apply_custom_edits(original_text, instructions)

    result["edited"]["text"] = edited_text
    result["edited"]["word_count"] = len(edited_text.split())
    result["edited"]["character_count"] = len(edited_text)
    result["changes"] = changes

    return result


def _apply_grammar_fixes(text: str) -> tuple:
    """Apply basic grammar fixes."""
    changes = []
    edited = text

    # Fix double spaces
    if '  ' in edited:
        edited = re.sub(r' +', ' ', edited)
        changes.append("Removed extra spaces")

    # Fix spacing around punctuation
    edited = re.sub(r'\s+([.,!?;:])', r'\1', edited)
    if edited != text:
        changes.append("Fixed spacing around punctuation")

    # Capitalize first letter of sentences
    edited = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), edited)

    # Ensure first character is capitalized
    if edited and edited[0].islower():
        edited = edited[0].upper() + edited[1:]
        changes.append("Capitalized sentence beginnings")

    if not changes:
        changes.append("No grammar issues detected")

    return edited, changes


def _apply_simplification(text: str) -> tuple:
    """Simplify complex language."""
    changes = []
    edited = text

    # Replace complex words with simpler alternatives
    replacements = {
        r'\butilize\b': 'use',
        r'\bcommence\b': 'start',
        r'\bterminate\b': 'end',
        r'\bsubsequent\b': 'next',
        r'\bprior to\b': 'before',
        r'\bin the event that\b': 'if',
        r'\bnotwithstanding\b': 'despite',
        r'\bpursuant to\b': 'under',
        r'\bwhereas\b': 'while',
        r'\bhereinafter\b': 'from now on',
        r'\baforementioned\b': 'mentioned above',
    }

    for pattern, replacement in replacements.items():
        if re.search(pattern, edited, re.IGNORECASE):
            edited = re.sub(pattern, replacement, edited, flags=re.IGNORECASE)
            changes.append(f"Simplified: '{pattern[2:-2]}' → '{replacement}'")

    if not changes:
        changes.append("Text is already relatively simple")

    return edited, changes


def _apply_formatting(text: str) -> tuple:
    """Apply formatting improvements."""
    changes = []
    edited = text

    # Add paragraph breaks after periods followed by capital letters
    edited = re.sub(r'\.(\s*)([A-Z])', r'.\n\n\2', edited)
    changes.append("Added paragraph breaks")

    # Normalize whitespace
    edited = re.sub(r'\n{3,}', '\n\n', edited)
    changes.append("Normalized whitespace")

    return edited, changes


def _apply_expansion(text: str, instructions: Optional[str]) -> tuple:
    """Expand text with additional detail."""
    changes = []

    expanded = text + "\n\n[EXPANDED CONTENT]\n"
    expanded += f"Additional context and detail would be added here based on: {instructions or 'general expansion'}\n"
    expanded += "[/EXPANDED CONTENT]"

    changes.append("Added expansion placeholder")
    changes.append(f"Expansion guidance: {instructions or 'Add more detail and context'}")

    return expanded, changes


def _apply_tone_change(text: str, instructions: Optional[str]) -> tuple:
    """Change the tone of the text."""
    changes = []
    edited = text

    target_tone = (instructions or "professional").lower()

    if "formal" in target_tone:
        # Make more formal
        edited = edited.replace("can't", "cannot")
        edited = edited.replace("won't", "will not")
        edited = edited.replace("don't", "do not")
        changes.append("Made contractions formal")
    elif "casual" in target_tone or "informal" in target_tone:
        # Make more casual
        edited = edited.replace("cannot", "can't")
        edited = edited.replace("will not", "won't")
        edited = edited.replace("do not", "don't")
        changes.append("Added contractions for casual tone")

    changes.append(f"Adjusted tone toward: {target_tone}")

    return edited, changes


def _apply_style_change(text: str, instructions: Optional[str]) -> tuple:
    """Apply style changes."""
    changes = []
    edited = text

    if instructions:
        changes.append(f"Style adjustment requested: {instructions}")
        changes.append("Manual review recommended for style changes")
    else:
        changes.append("No specific style instructions provided")

    return edited, changes


def _apply_translation(text: str, target_language: Optional[str]) -> tuple:
    """Mark text for translation."""
    changes = []
    lang = target_language or "target language"

    translated = f"[TRANSLATION TO {lang.upper()}]\n\n"
    translated += f"Original text ({len(text.split())} words):\n{text}\n\n"
    translated += f"[Translation to {lang} would be inserted here]\n"
    translated += "[/TRANSLATION]"

    changes.append(f"Marked for translation to: {lang}")
    changes.append("Note: Actual translation requires language processing service")

    return translated, changes


def _apply_custom_edits(text: str, instructions: Optional[str]) -> tuple:
    """Apply custom edits based on instructions."""
    changes = []

    edited = f"[CUSTOM EDIT]\n\n"
    edited += f"Original:\n{text}\n\n"
    edited += f"Instructions: {instructions or 'No specific instructions provided'}\n\n"
    edited += "[Edited version would be inserted here based on instructions]\n"
    edited += "[/CUSTOM EDIT]"

    changes.append(f"Custom edit requested: {instructions or 'See marked sections'}")

    return edited, changes


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Route tool execution to the appropriate function.
    Returns the tool result as a JSON string.
    """
    try:
        if tool_name == "extract_information":
            result = extract_information(**tool_input)
        elif tool_name == "generate_document":
            result = generate_document(**tool_input)
        elif tool_name == "apply_edits":
            result = apply_edits(**tool_input)
        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        # Convert to JSON string if result is dict
        if isinstance(result, dict):
            return json.dumps(result, indent=2, default=str)
        return str(result)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "tool_name": tool_name
        }, indent=2)
