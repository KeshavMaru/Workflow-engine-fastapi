from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Callable, Dict, Optional, Tuple

from app.schemas import StateModel

logger = logging.getLogger("nodes_tools")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

ToolType = Callable[..., Any]
registered_tools: Dict[str, ToolType] = {}


def register_tool(name: str, tool: ToolType) -> None:
    registered_tools[name] = tool


def get_tool(name: str) -> ToolType:
    return registered_tools[name]


def estimate_complexity(function_source: str) -> int:
    if not function_source:
        return 0
    keywords = ["if ", "for ", "while ", "elif ", "case ", "except ", "and ", "or ", "return "]
    score = 1
    lower_source = function_source.lower()
    for keyword in keywords:
        score += lower_source.count(keyword)
    return max(1, min(score, 100))


def run_lint(function_source: str) -> Dict[str, Any]:
    issues = []
    lines = function_source.splitlines()

    for line_number, line_text in enumerate(lines, start=1):
        if len(line_text) > 120:
            issues.append(
                {
                    "type": "long_line",
                    "line": line_number,
                    "detail": "Line longer than 120 characters",
                }
            )
        if line_text.rstrip() != line_text:
            issues.append(
                {
                    "type": "trailing_whitespace",
                    "line": line_number,
                    "detail": "Line contains trailing whitespace",
                }
            )

    for index, content in enumerate(lines):
        stripped = content.strip()
        if stripped.startswith("def "):
            next_lines = lines[index + 1 : index + 4]
            has_docstring = any(item.strip().startswith(('"""', "'''")) for item in next_lines)
            if not has_docstring:
                issues.append(
                    {
                        "type": "missing_docstring",
                        "line": index + 1,
                        "detail": "Function may be missing a docstring",
                    }
                )
            break

    return {"issue_count": len(issues), "issues": issues}


def generate_suggestions(function_source: str) -> Dict[str, Any]:
    suggestions = []
    complexity = estimate_complexity(function_source)
    if complexity > 10:
        suggestions.append(
            {
                "type": "split_function",
                "detail": "Function appears complex and could be split into smaller parts",
            }
        )
    lint_result = run_lint(function_source)
    for issue in lint_result["issues"]:
        if issue["type"] == "long_line":
            suggestions.append(
                {
                    "type": "wrap_long_line",
                    "detail": f"Consider wrapping line {issue['line']}",
                }
            )
        if issue["type"] == "missing_docstring":
            suggestions.append(
                {
                    "type": "add_docstring",
                    "detail": "Add a descriptive docstring",
                }
            )
    return {"suggestions": suggestions}


register_tool("estimate_complexity", estimate_complexity)
register_tool("run_lint", run_lint)
register_tool("generate_suggestions", generate_suggestions)


async def extract_functions_node(
    state: StateModel,
    tools: Dict[str, ToolType],
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], StateModel, str]:
    source = state.source_code
    extracted = []

    if isinstance(source, str):
        file_map = {"main.py": source}
    else:
        file_map = source or {}

    for filename, content in file_map.items():
        lines = content.splitlines()
        current_source = []
        current_name = None
        start_line = 0

        for line_number, line_text in enumerate(lines, start=1):
            stripped = line_text.lstrip()

            if stripped.startswith("def "):
                if current_name is not None:
                    extracted.append(
                        {
                            "filename": filename,
                            "function_name": current_name,
                            "start_line": start_line,
                            "end_line": line_number - 1,
                            "source": "\n".join(current_source),
                        }
                    )
                current_name = stripped.split("(")[0].replace("def ", "").strip()
                start_line = line_number
                current_source = [line_text]
            else:
                if current_name is not None:
                    current_source.append(line_text)

        if current_name is not None:
            extracted.append(
                {
                    "filename": filename,
                    "function_name": current_name,
                    "start_line": start_line,
                    "end_line": len(lines),
                    "source": "\n".join(current_source),
                }
            )

    state.functions = extracted
    return "check_complexity", state, f"extracted {len(extracted)} functions"


async def check_complexity_node(
    state: StateModel,
    tools: Dict[str, ToolType],
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], StateModel, str]:
    tool = tools["estimate_complexity"]
    results = []

    for function_entry in state.functions:
        source = function_entry.get("source", "")
        complexity = await asyncio.to_thread(tool, source)
        results.append(
            {
                "function_name": function_entry["function_name"],
                "complexity": complexity,
            }
        )

    if results:
        average = sum(item["complexity"] for item in results) / len(results)
        quality = max(0.0, 100.0 - average)
    else:
        quality = 100.0

    state.metadata["complexity"] = results
    state.quality_score = quality

    return "detect_issues", state, f"computed complexity for {len(results)} functions"


async def detect_issues_node(
    state: StateModel,
    tools: Dict[str, ToolType],
    config: Optional[Dict[str,Any]] = None,
) -> Tuple[Optional[str], StateModel, str]:
    tool = tools["run_lint"]
    collected = []

    for item in state.functions:
        source = item.get("source", "")
        result = await asyncio.to_thread(tool, source)
        if result["issue_count"] > 0:
            collected.append(
                {
                    "function_name": item["function_name"],
                    "issues": result["issues"],
                }
            )

    state.issues = collected
    return "suggest_improvements", state, f"detected issues in {len(collected)} functions"


async def suggest_improvements_node(
    state: StateModel,
    tools: Dict[str, ToolType],
    config: Optional[Dict[str,Any]] = None,
) -> Tuple[Optional[str], StateModel, str]:
    tool = tools["generate_suggestions"]
    suggestions = []

    for item in state.functions:
        source = item.get("source", "")
        result = await asyncio.to_thread(tool, source)
        suggestions.append(
            {
                "function_name": item["function_name"],
                "suggestions": result["suggestions"],
            }
        )

    state.suggestions = suggestions

    count = sum(len(s["suggestions"]) for s in suggestions)
    if count > 0:
        state.quality_score = min(100.0, (state.quality_score or 0.0) + math.log1p(count) * 2.0)
    else:
        state.quality_score = min(100.0, (state.quality_score or 0.0) + 1.0)

    return "compute_quality", state, f"generated suggestions for {len(suggestions)} functions"


async def compute_quality_node(
    state: StateModel,
    tools: Dict[str, ToolType],
    config: Optional[Dict[str,Any]] = None,
) -> Tuple[Optional[str], StateModel, str]:
    threshold = 90.0
    if config:
        threshold = float(config.get("threshold", threshold))

    current = state.quality_score or 0.0
    if current >= threshold:
        return None, state, f"quality target reached: {current}"
    return "check_complexity", state, f"quality below threshold: {current}"


NODE_FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "extract_functions": extract_functions_node,
    "check_complexity": check_complexity_node,
    "detect_issues": detect_issues_node,
    "suggest_improvements": suggest_improvements_node,
    "compute_quality": compute_quality_node,
}
