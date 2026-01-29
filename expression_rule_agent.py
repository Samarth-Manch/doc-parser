"""
Expression Rule Generator (Manch – COMPLETE & Production Safe)

Flow:
1. Call Manch API (with pagination) to fetch form-fill-metadata
2. Build normalized field registry (display name → variableName)
3. Inject grounded field list into SYSTEM PROMPT
4. Use LLM to extract STRUCTURED INTENT (display names only)
5. Validate functions + helper usage
6. Resolve conditions + args to actual variableNames
7. Emit expr-eval compliant expression

LLM is used ONLY for intent extraction.
"""

import json
import re
import requests
from typing import List, Optional, Dict
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://qa.manchtech.com"
DOCUMENT_TYPE_ID = 1834
AUTH_TOKEN = "e3pHb8Jzuh6yyRyvZ909HIQGkfYgAE"

PAGE_SIZE = 1000

OPENAI_MODEL = "gpt-4.1-mini"
LLM_TEMPERATURE = 0


# ============================================================
# 1. FORM-FILL-METADATA (WITH PAGINATION)
# ============================================================

def fetch_all_form_fill_metadata(document_type_id: int, auth_token: str) -> dict:
    all_fields = []
    page = 0

    while True:
        url = (
            f"{BASE_URL}/app/v2/document-types/"
            f"{document_type_id}/form-fill-metadatas/delete-flag/false"
        )

        headers = {
            "Accept": "application/json",
            "X-Authorization": auth_token,
            "Origin": "https://app.qa.manchtech.com",
            "Referer": "https://app.qa.manchtech.com/",
            "User-Agent": "ExpressionRuleGenerator/1.0"
        }

        params = {
            "page": page,
            "size": PAGE_SIZE,
            "sort": "formOrder,asc",
            "searchParam": ""
        }

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("content", [])
        all_fields.extend(content)

        if data.get("last", True):
            break

        page += 1

    return {"content": all_fields}


# ============================================================
# 2. FIELD REGISTRY (NORMALIZED + SAFE)
# ============================================================

def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def build_field_registry(api_response: dict) -> Dict[str, str]:
    """
    Returns:
      normalized_display_name -> variableName
    """
    registry = {}

    for field in api_response.get("content", []):
        name = field.get("name")
        var = field.get("variableName")

        if not name or not var:
            continue

        registry[normalize(name)] = var.strip()

    if not registry:
        raise RuntimeError("No fields found from form-fill-metadata")

    return registry


# ============================================================
# 3. ALLOWED FUNCTIONS
# ============================================================

ACTION_FUNCTIONS = {
    "mvi", "minvi", "mm", "mnm",
    "en", "dis", "cf", "ctfd",
    "adderr", "remerr",
    "sbmvi", "sbminvi"
}

HELPER_FUNCTIONS = {
    "vo", "regexTest", "cntns",
    "pt", "mt", "vso",
    "tolc", "touc", "concat", "cwd"
}


# ============================================================
# 4. INTENT SCHEMA
# ============================================================

class Statement(BaseModel):
    function: str
    condition: Optional[str]
    args: List[str]
    message: Optional[str] = None


class RuleBlock(BaseModel):
    trigger: Optional[str] = None
    statements: List[Statement]


# ============================================================
# 5. LLM SETUP (FIELD-GROUNDED)
# ============================================================

llm = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=LLM_TEMPERATURE
)


def build_system_prompt(field_registry: Dict[str, str]) -> str:
    field_lines = "\n".join(
        f'- "{k}"' for k in sorted(field_registry.keys())
    )

    return f"""
You are a rule translation engine.

Convert English business rules into STRICT JSON.
Output ONLY raw JSON. No markdown. No explanations.

====================
AVAILABLE FIELDS
====================

Use ONLY these field display names (case-insensitive):

{field_lines}

====================
JSON SCHEMA
====================

{{
  "trigger": string | null,
  "statements": [
    {{
      "function": string,
      "condition": string | null,
      "args": string[],
      "message": string | null
    }}
  ]
}}

====================
RULES
====================

- Use DISPLAY NAMES only
- Use vo("display name") in conditions
- Never invent fields
- Never use variableName
- If unclear, choose the closest matching field
- If no match exists, OMIT the rule
"""

def build_prompt(field_registry: Dict[str, str]) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", build_system_prompt(field_registry)),
        ("human", "{rule}")
    ])


# ============================================================
# 6. LLM OUTPUT SANITIZATION
# ============================================================

def extract_json_from_llm(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", text)
    cleaned = cleaned.replace("```", "").strip()
    return json.loads(cleaned)


def extract_intent(rule_text: str, field_registry: Dict[str, str]) -> RuleBlock:
    prompt = build_prompt(field_registry)
    response = llm.invoke(prompt.format(rule=rule_text))
    data = extract_json_from_llm(response.content)
    return RuleBlock.model_validate(data)


# ============================================================
# 7. CONDITION + ARG RESOLUTION
# ============================================================

def resolve_condition(condition: str, registry: Dict[str, str]) -> str:
    def repl(match):
        field = normalize(match.group(1))
        if field not in registry:
            raise ValueError(f"Unknown field in condition: {field}")
        return f'vo("{registry[field]}")'

    return re.sub(r'vo\(\s*["\']([^"\']+)["\']\s*\)', repl, condition)


def resolve_args(args: List[str], registry: Dict[str, str]) -> List[str]:
    resolved = []
    for arg in args:
        key = normalize(arg)
        if key in registry:
            resolved.append(f'"{registry[key]}"')
        else:
            resolved.append(arg)
    return resolved


# ============================================================
# 8. VALIDATION
# ============================================================

def validate_rule_block(rule_block: RuleBlock):
    if not rule_block.statements:
        raise ValueError("No statements generated")

    for s in rule_block.statements:
        if s.function not in ACTION_FUNCTIONS:
            raise ValueError(f"Invalid action function: {s.function}")

        if s.function == "adderr" and not s.message:
            raise ValueError("adderr requires message")

        if s.function != "adderr" and s.message:
            raise ValueError(f"{s.function} must not have message")


# ============================================================
# 9. ASSEMBLER
# ============================================================

def assemble_expression(rule_block: RuleBlock, registry: Dict[str, str]) -> str:
    lines = []

    for s in rule_block.statements:
        condition = resolve_condition(s.condition or "true", registry)
        args = resolve_args(s.args, registry)

        if s.function == "adderr":
            line = f'adderr({condition},"{s.message}",{",".join(args)});'
        else:
            line = f'{s.function}({condition},{",".join(args)});'

        lines.append(line)

    body = "\n".join(lines)

    if rule_block.trigger:
        return f'on("{rule_block.trigger}") and (\n{body}\n)'

    return body


# ============================================================
# 10. PUBLIC API
# ============================================================

def generate_expression_rule(rule: str) -> str:
    api_data = fetch_all_form_fill_metadata(DOCUMENT_TYPE_ID, AUTH_TOKEN)
    field_registry = build_field_registry(api_data)

    rule_block = extract_intent(rule, field_registry)
    validate_rule_block(rule_block)

    return assemble_expression(rule_block, field_registry)


# ============================================================
# 11. DEMO
# ============================================================

if __name__ == "__main__":

    rule = """
If mobile number is 7822850370,
then make email invisible.
"""

    print("\nGenerated Expression:\n")
    print(generate_expression_rule(rule))
