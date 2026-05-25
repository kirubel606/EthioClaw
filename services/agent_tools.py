import ast
import html
import math
import operator
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse, unquote

import requests
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


GENERATED_DIR = Path(__file__).resolve().parents[1] / "generated"
USER_AGENT = os.getenv("WEB_SEARCH_USER_AGENT", "Mozilla/5.0 (compatible; EthioClaw/1.0)")
WEB_SEARCH_TIMEOUT = int(os.getenv("WEB_SEARCH_TIMEOUT", "20"))
WEB_SEARCH_LIMIT = int(os.getenv("WEB_SEARCH_LIMIT", "5"))


@dataclass
class ToolBundle:
    context: str = ""
    artifact_kind: str | None = None
    artifact_title: str | None = None


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "artifact"


def _ensure_generated_dir() -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_DIR


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


ALLOWED_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

ALLOWED_UNARY: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

ALLOWED_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "floor": math.floor,
    "ceil": math.ceil,
    "pow": pow,
}

ALLOWED_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}


def safe_math_eval(expression: str) -> float:
    expression = (expression or "").strip().replace("^", "**")
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
            return ALLOWED_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY:
            return ALLOWED_UNARY[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Name) and node.id in ALLOWED_CONSTANTS:
            return ALLOWED_CONSTANTS[node.id]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func = ALLOWED_FUNCTIONS.get(node.func.id)
            if func is None:
                raise ValueError(f"Function '{node.func.id}' is not allowed")
            args = [_eval(arg) for arg in node.args]
            return func(*args)
        raise ValueError("Unsupported math expression")

    return float(_eval(tree))


def _extract_math_expression(message: str) -> str | None:
    text = message.strip()
    lowered = text.lower()

    if not any(
        keyword in lowered
        for keyword in [
            "calculate",
            "compute",
            "what is",
            "solve",
            "how much is",
            "average",
            "mean",
            "sum of",
            "square root",
            "sqrt",
            "percent",
        ]
    ) and not re.search(r"[0-9]\s*[\+\-\*\/\^]\s*[0-9]", text):
        return None

    candidate = text
    for prefix in [
        "calculate",
        "compute",
        "what is",
        "solve",
        "how much is",
    ]:
        if lowered.startswith(prefix):
            candidate = text[len(prefix):].strip(" ?:=.-")
            break

    if "average of" in lowered:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        if numbers:
            expr = f"({'+'.join(numbers)})/{len(numbers)}"
            return expr

    if "sum of" in lowered:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        if numbers:
            return "+".join(numbers)

    match = re.search(r"([-+*/().\d\s^eEpiabsqrtlogncof]+)$", candidate)
    if match:
        expr = match.group(1).strip()
        if expr:
            return expr

    math_chars = re.findall(r"[0-9\.\+\-\*\/\^\(\)\s]+", candidate)
    if math_chars:
        expr = "".join(math_chars).strip()
        if expr:
            return expr

    return None


def run_math_tool(message: str) -> str | None:
    expression = _extract_math_expression(message)
    if not expression:
        return None

    try:
        value = safe_math_eval(expression)
        if float(value).is_integer():
            value_text = str(int(value))
        else:
            value_text = str(round(value, 8))
        return f"Math tool: {expression} = {value_text}"
    except Exception as exc:
        return f"Math tool error for '{expression}': {exc}"


def _extract_search_query(message: str) -> str | None:
    text = message.strip()
    lowered = text.lower()
    search_triggers = [
        "search",
        "look up",
        "look for",
        "find",
        "latest",
        "news",
        "web",
        "browse",
        "research",
    ]
    if not any(trigger in lowered for trigger in search_triggers):
        return None

    query = text
    for prefix in [
        "search for",
        "look up",
        "look for",
        "find",
        "research",
        "browse",
    ]:
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip(" :.-")
            break

    query = re.sub(r"^(latest|news on|web search on|search the web for)\s+", "", query, flags=re.I).strip()
    return query or text


def search_web(query: str, limit: int = WEB_SEARCH_LIMIT) -> list[dict[str, str]]:
    if not query:
        return []

    url = "https://lite.duckduckgo.com/lite/"
    response = requests.get(
        url,
        params={"q": query},
        headers={"User-Agent": USER_AGENT},
        timeout=WEB_SEARCH_TIMEOUT,
    )
    response.raise_for_status()

    html_text = response.text
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', html_text, re.I | re.S):
        raw_url = html.unescape(match.group("url"))
        title = _strip_html(match.group("title"))

        if not title:
            continue

        parsed = urlparse(raw_url)
        final_url = raw_url
        if "duckduckgo.com" in parsed.netloc and parsed.path.endswith("/l/"):
            query_params = parse_qs(parsed.query)
            if "uddg" in query_params:
                final_url = unquote(query_params["uddg"][0])

        if not final_url.startswith("http"):
            continue
        if title.lower() in {"next", "more", "images", "videos", "news", "maps", "shopping"}:
            continue
        if final_url in seen:
            continue
        seen.add(final_url)

        results.append({"title": title, "url": final_url})
        if len(results) >= limit:
            break

    return results


def format_search_results(results: list[dict[str, str]], query: str) -> str:
    if not results:
        return f"Web search: no results found for '{query}'."

    lines = [f"Web search results for '{query}':"]
    for idx, result in enumerate(results, 1):
        lines.append(f"{idx}. {result['title']} - {result['url']}")
    return "\n".join(lines)


def _extract_artifact_request(message: str) -> tuple[str | None, str | None]:
    lowered = message.lower()
    if any(keyword in lowered for keyword in ["powerpoint", "ppt", "pptx", "presentation", "slides"]):
        return "pptx", _extract_topic(message)
    if any(keyword in lowered for keyword in ["word", "docx", "document", "report"]):
        return "docx", _extract_topic(message)
    if "pdf" in lowered:
        return "pdf", _extract_topic(message)
    return None, None


def _extract_topic(message: str) -> str:
    text = message.strip()
    cleaned = re.sub(
        r"(?i)\b(create|make|generate|draft|build|write|export|prepare|turn this into|turn into|a|an|the|to|into|for)\b",
        " ",
        text,
    )
    cleaned = re.sub(r"(?i)\b(powerpoint|pptx|ppt|presentation|slides|word|docx|document|report|pdf)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:-")
    return cleaned or "generated-content"


def _split_paragraphs(content: str) -> list[str]:
    parts = [chunk.strip() for chunk in re.split(r"\n\s*\n", content or "") if chunk.strip()]
    if parts:
        return parts
    lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
    if lines:
        return lines
    return [content.strip() or "No content provided."]


def generate_docx(title: str, content: str) -> Path:
    _ensure_generated_dir()
    file_path = GENERATED_DIR / f"{_slugify(title)}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.docx"

    document = Document()
    document.add_heading(title, level=1)
    for paragraph in _split_paragraphs(content):
        document.add_paragraph(paragraph)
    document.save(file_path)
    return file_path


def generate_pdf(title: str, content: str) -> Path:
    _ensure_generated_dir()
    file_path = GENERATED_DIR / f"{_slugify(title)}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    c = canvas.Canvas(str(file_path), pagesize=letter)
    width, height = letter
    y = height - 72

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, title[:90])
    y -= 28
    c.setFont("Helvetica", 11)

    for paragraph in _split_paragraphs(content):
        for line in _wrap_text(paragraph, max_chars=95):
            if y < 72:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - 72
            c.drawString(72, y, line)
            y -= 14
        y -= 8

    c.save()
    return file_path


def _wrap_text(text: str, max_chars: int = 90) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = []
    current_len = 0

    for word in words:
        addition = len(word) + (1 if current else 0)
        if current_len + addition > max_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += addition

    if current:
        lines.append(" ".join(current))

    return lines or [text]


def generate_pptx(title: str, content: str) -> Path:
    _ensure_generated_dir()
    file_path = GENERATED_DIR / f"{_slugify(title)}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pptx"

    presentation = Presentation()

    title_slide = presentation.slide_layouts[0]
    slide = presentation.slides.add_slide(title_slide)
    slide.shapes.title.text = title
    slide.placeholders[1].text = "Generated by EthioClaw"

    bullet_layout = presentation.slide_layouts[1]
    sections = _split_paragraphs(content)

    for section in sections:
        slide = presentation.slides.add_slide(bullet_layout)
        slide.shapes.title.text = section[:60] or title
        body = slide.shapes.placeholders[1].text_frame
        body.clear()
        for line in _wrap_text(section, max_chars=70)[:8]:
            paragraph = body.add_paragraph()
            paragraph.text = line
            paragraph.level = 0
            paragraph.font.size = Pt(20)

    presentation.save(file_path)
    return file_path


def generate_artifact(kind: str, title: str, content: str) -> Path:
    kind = kind.lower()
    if kind == "docx":
        return generate_docx(title, content)
    if kind == "pdf":
        return generate_pdf(title, content)
    if kind == "pptx":
        return generate_pptx(title, content)
    raise ValueError(f"Unsupported artifact kind: {kind}")


async def build_tool_bundle(message: str) -> ToolBundle:
    context_parts: list[str] = []

    math_result = run_math_tool(message)
    if math_result:
        context_parts.append(math_result)

    search_query = _extract_search_query(message)
    if search_query:
        try:
            results = search_web(search_query)
            context_parts.append(format_search_results(results, search_query))
        except Exception as exc:
            context_parts.append(f"Web search failed for '{search_query}': {exc}")

    artifact_kind, artifact_title = _extract_artifact_request(message)

    return ToolBundle(
        context="\n".join(context_parts).strip(),
        artifact_kind=artifact_kind,
        artifact_title=artifact_title,
    )
