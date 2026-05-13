"""Telegram support bot orchestration.

End-to-end flow for an inbound customer message:
    1. Strip PII + encrypt raw; persist to support_messages.
    2. Match the customer's described product against the seeded `products`
       catalog (LLM-driven, with keyword pre-filter to keep prompt size sane).
    3. Classify the issue as AI-resolvable or human-needed.
    4a. If AI-resolvable above confidence threshold: generate a troubleshooting
        tip from the matched product's `common_issues` plus model knowledge,
        send via Telegram, store outbound message.
    4b. If human-needed: create a `Complaint` row through the existing
        ingestion pipeline (embedding + sentiment + clustering kick in
        automatically) and tell the customer an agent will follow up.

The agent-reply path is invoked from the REST endpoint when a human types
into the dashboard inbox; it stores the message and sends it via the same
Telegram outbound helper.

All LLM calls go through `get_llm_client()` from `app.services.llm_client`.
All raw customer text is PII-stripped before any LLM call and stored as
both `body_redacted` (Text, safe to display) and `body_encrypted`
(AES-256-GCM, retained per policy) — never as plaintext.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import encrypt_raw_text, strip_pii
from app.models.product import Product
from app.models.support_conversation import SupportConversation
from app.models.support_message import SupportMessage
from app.services.complaint_service import ingest_complaints
from app.services.llm_client import get_llm_client, get_vision_client

logger = get_logger(__name__)


# ── LLM prompts ───────────────────────────────────────────────────────────────

_PRODUCT_MATCH_SYSTEM_PROMPT = """You are an HVAC product identifier for Carrier customer support.
Given a snippet of customer conversation and a JSON list of candidate Carrier products,
pick the product that best matches the customer's description.

Reply with a JSON object only — no surrounding prose, no markdown fences:
{
  "sku": "<exact sku from the catalog OR null if no clear match>",
  "confidence": <float 0-1>,
  "reasoning": "<short, 1 sentence>"
}

Only return a sku if the customer mentions clear signals (model name, family, capacity,
features). If they have only described a generic problem with no product context, return
sku=null with confidence below 0.5."""


_CLASSIFY_SYSTEM_PROMPT = """You are a triage agent for Carrier HVAC customer support.
Decide whether the customer's issue can be resolved with self-service troubleshooting
tips, needs a human technician / agent, OR the conversation is already resolved.

Consider AI-resolvable: filter replacement, thermostat config, breaker reset, drain
cleaning, common error codes with documented fixes, scheduling questions, general
product questions, billing questions you can refer back to docs for.

Consider human-needed: refrigerant leaks, electrical faults, compressor failure,
warranty disputes, anything involving safety (gas smell, sparks, smoke), repeated
failures, or any issue where the customer explicitly asks for an agent.

Consider resolved: the customer says thanks, the issue is fixed, it's working now,
"resolved", "sorted", "never mind", or any similar closing acknowledgment — especially
after the bot already gave a troubleshooting tip. Do NOT escalate to a human just
because the customer said thanks.

Reply with a JSON object only — no surrounding prose:
{
  "verdict": "ai" | "human" | "resolved",
  "confidence": <float 0-1>,
  "reasoning": "<short, 1 sentence>",
  "suggested_tip": "<helpful 2-4 sentence customer-facing reply IF verdict='ai', else null>"
}"""


_FACT_EXTRACTOR_SYSTEM_PROMPT = """You are extracting structured facts from a
Carrier HVAC customer support conversation so a human agent can see them at a
glance. Read the conversation history, then update the running "gathered_info"
JSON object with any NEW or UPDATED facts you can infer.

Rules:
- Only add a field if the customer explicitly stated it OR an image OCR result
  clearly shows it. Never guess.
- Keep prior facts unless the customer correctly contradicts them.
- If a value is unknown, leave it null (don't fabricate).
- Keep values short and human-readable (e.g. "1.5 ton" not "1.5"; "2022-03" or
  "March 2022" not "twenty-twenty-two").

Reply with a JSON object only — no surrounding prose, no markdown fences:
{
  "brand": "<string or null>",
  "family": "<Infinity / Performance / Comfort / etc., or null>",
  "model_name": "<string or null>",
  "model_number": "<string or null>",
  "serial_number": "<string or null>",
  "capacity": "<e.g. '1.5 ton', '18000 BTU', or null>",
  "refrigerant": "<e.g. 'R-32', 'R-410A', or null>",
  "install_type": "<e.g. 'split AC', 'window unit', 'ductless mini-split', or null>",
  "install_location": "<e.g. 'living room wall mount', 'rooftop', or null>",
  "purchase_date": "<e.g. '2022-03' or 'March 2022' or null>",
  "manufacture_date": "<e.g. '2022-03' or null>",
  "warranty_status": "<'in warranty' / 'out of warranty' / null>",
  "issue_summary": "<one short sentence describing the customer's reported problem, or null>",
  "symptoms": ["<short bullet>", "..."],
  "tried_already": ["<short bullet of things the customer already attempted>", "..."]
}"""


_FOLLOWUP_QUESTION_PROMPT = """You are helping a Carrier HVAC customer. Look at the full
conversation so far. We still don't know exactly which Carrier product they have.

Rules:
- Ask ONE short, friendly follow-up question (max 2 sentences).
- Do NOT repeat anything you've already asked. The customer already told you what they
  know — read what they said carefully.
- Skip questions the customer already answered, even partially.
- If the customer said "I don't know", "no idea", "not sure", "idk", or similar for a
  topic, NEVER ask about that topic again — try a different angle (symptom, age of unit,
  where it's installed, what they see/hear).
- Don't keep asking about Infinity/Performance/Comfort series if they couldn't tell you.

Reply with ONLY the question text, no preamble, no quotes."""


# Bigger-picture safety net: how many follow-ups we'll ask before giving up and
# proceeding to classify the issue with whatever info we have. Without this, the
# bot loops asking for product details forever when the customer's actual model
# (e.g. "CAI20PE5R35W0") isn't in our seeded catalog.
_MAX_FOLLOWUPS_BEFORE_CLASSIFY = 2

# Substrings (lowercased) that mean "the customer doesn't have more info" —
# when seen in inbound text we stop asking and try to help with what we have.
_IDK_PHRASES = (
    "i don’t know",
    "i dont know",
    "i don’t know",  # curly apostrophe
    "don’t know",
    "dont know",
    "don’t know",
    "no idea",
    "not sure",
    "idk",
    "no clue",
    "can’t tell",
    "cant tell",
    "i can’t say",
    "i cant say",
)


def _user_said_idk(text: str) -> bool:
    """Return True if the customer’s message is mostly a ‘don’t know’ answer."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # Short messages whose only content is an IDK phrase
    if len(t) <= 40 and any(p in t for p in _IDK_PHRASES):
        return True
    # Longer messages still count if they open with an IDK phrase
    return any(t.startswith(p) for p in _IDK_PHRASES)


# Phrases that indicate the customer’s issue is resolved / conversation closing.
# Checked against the LAST BOT MESSAGE being an AI tip — so we don’t close prematurely.
_RESOLVED_PHRASES = (
    "thank",       # covers thanks, thank you, thanks a lot
    "resolved",
    "it works",
    "it’s working",
    "its working",
    "working now",
    "fixed",
    "that worked",
    "that helped",
    "problem solved",
    "issue solved",
    "issue resolved",
    "all good",
    "sorted",
    "got it working",
    "it worked",
    "never mind",
    "nevermind",
    "no worries",
)


def _user_said_resolved(text: str) -> bool:
    """Return True if the customer is signaling their issue is now resolved.

    Deliberately conservative: only match short/clearly-closing messages.
    A long message with ‘resolved’ in the middle is not a closer.
    """
    t = (text or "").strip().lower()
    if not t:
        return False
    # Only apply to short closing-style messages (≤ 80 chars)
    if len(t) > 80:
        return False
    return any(p in t for p in _RESOLVED_PHRASES)


_VISION_OCR_SYSTEM_PROMPT = """You are an expert OCR assistant for HVAC product labels.
The image is a photo of an HVAC unit nameplate, control panel sticker, packaging label,
remote control, or service tag. Extract every product-identifying detail you can read.

Reply with a JSON object only — no surrounding prose, no markdown fences:
{
  "brand": "<brand name visible on the label, or null>",
  "model_name": "<full model name as printed, or null>",
  "model_number": "<full model number / SKU as printed, or null>",
  "serial_number": "<serial if visible, or null>",
  "capacity": "<e.g. '1.5 ton', '18000 BTU', or null>",
  "refrigerant": "<e.g. 'R-32', 'R-410A', or null>",
  "manufacture_date": "<e.g. '2022-03', or null>",
  "other_text": "<any other meaningful text on the label, single string>",
  "confidence": <float 0-1 — how confident you are the OCR is correct>,
  "is_carrier": <true if the label shows the Carrier brand, false otherwise>,
  "summary": "<one-sentence customer-facing description of what you saw>"
}

If the image isn't a product label (e.g. a selfie, a meme, a random photo),
return all fields as null with confidence=0 and summary='This does not appear to be
a product label — could you take a photo of the nameplate sticker on the unit?'"""


_GREETING_TEXT = (
    "Hi! I'm the Carrier support assistant. Tell me which Carrier product you have "
    "and what's going on — I'll either help directly or hand you off to a human agent. "
    "You can also send me a photo of the unit's nameplate sticker and I'll read it."
)

_ESCALATION_TEXT = (
    "Thanks for the details. I've flagged this for a human agent and they will "
    "reply right here in this chat shortly. You can keep adding context in the "
    "meantime."
)

_RESOLUTION_CLOSING_TEXT = (
    "Glad I could help. Marking this resolved — message me again anytime if "
    "something else comes up."
)


# ── Product catalog pre-filter ────────────────────────────────────────────────

# Keep the prompt small by pre-filtering the catalog with cheap keyword overlap
# against the most recent conversation snippet before handing it to the LLM.
def _keyword_prefilter(
    snippet: str, products: list[Product], max_candidates: int = 12
) -> list[Product]:
    if not products:
        return []
    if len(products) <= max_candidates:
        return products

    snippet_lower = snippet.lower()
    scored: list[tuple[int, Product]] = []
    for p in products:
        score = 0
        for needle in filter(None, [p.family, p.model_name, p.category, p.tonnage]):
            for token in str(needle).lower().split():
                if len(token) >= 3 and token in snippet_lower:
                    score += 1
        scored.append((score, p))

    # Sort by score desc; keep at least max_candidates to give the LLM options.
    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:max_candidates]]


# ── Telegram I/O ──────────────────────────────────────────────────────────────


async def download_telegram_file(
    file_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[bytes, str] | None:
    """Resolve a Telegram file_id to (bytes, mime-hint) or None on failure.

    Telegram's two-step download: first call getFile to learn the file_path,
    then GET https://api.telegram.org/file/bot<token>/<file_path>.
    """
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        return None

    base = settings.TELEGRAM_API_BASE_URL
    token = settings.TELEGRAM_BOT_TOKEN
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        info = await client.get(
            f"{base}/bot{token}/getFile", params={"file_id": file_id}
        )
        info.raise_for_status()
        data = info.json()
        if not data.get("ok"):
            logger.error("telegram_getfile_failed", response=data)
            return None
        file_path = data["result"]["file_path"]

        blob = await client.get(f"{base}/file/bot{token}/{file_path}")
        blob.raise_for_status()
        # Telegram returns the original file; we just guess mime from extension
        # to populate the data URL — the vision API doesn't strictly need a
        # correct mime, but Qwen handles jpeg/png/webp.
        mime = "image/jpeg"
        lower = file_path.lower()
        if lower.endswith(".png"):
            mime = "image/png"
        elif lower.endswith(".webp"):
            mime = "image/webp"
        elif lower.endswith(".gif"):
            mime = "image/gif"
        return blob.content, mime
    except httpx.HTTPError as exc:
        logger.error("telegram_file_download_error", error=str(exc))
        return None
    finally:
        if owns_client:
            await client.aclose()


async def analyze_image(image_bytes: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    """Run the configured vision model over an image; return a structured dict.

    Falls back to ``{"summary": "<error msg>", ...}`` if the provider doesn't
    support vision or the call fails — callers should always check ``confidence``.
    """
    try:
        client, model = get_vision_client()
    except RuntimeError as exc:
        logger.error("telegram_vision_unavailable", error=str(exc))
        return {
            "summary": (
                "Image analysis is currently unavailable — could you type "
                "the model number from the label instead?"
            ),
            "confidence": 0.0,
            "error": str(exc),
        }

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": _VISION_OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Read this HVAC product label. Extract everything."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            max_tokens=500,
            temperature=0.1,
        )
    except Exception as exc:  # pragma: no cover — log + return error
        logger.error("telegram_vision_api_error", error=str(exc), model=model)
        return {
            "summary": (
                "I couldn't read the image — could you take a clearer photo "
                "of the label or type the model number?"
            ),
            "confidence": 0.0,
            "error": str(exc),
        }

    raw = response.choices[0].message.content or ""
    parsed = _safe_json_loads(raw)
    if not parsed:
        logger.warning("telegram_vision_unparseable", raw=raw[:300])
        return {
            "summary": (
                "I saw the image but couldn't extract product details — "
                "could you type the model number from the label?"
            ),
            "confidence": 0.0,
            "raw": raw[:500],
        }
    return parsed


def _image_facts_as_text(facts: dict[str, Any]) -> str:
    """Convert the vision OCR dict into a plain-text 'customer said' line.

    Used as the synthetic inbound text so the rest of the pipeline (product
    match + classify) treats the image content like the customer typed it.
    """
    bits: list[str] = []
    for key in ("brand", "model_name", "model_number", "serial_number",
                "capacity", "refrigerant", "manufacture_date"):
        v = facts.get(key)
        if v:
            bits.append(f"{key}: {v}")
    other = facts.get("other_text")
    if other:
        bits.append(f"label text: {other}")
    if not bits:
        return "[Customer sent a photo but no readable product info was extracted.]"
    return "[From product label photo] " + " | ".join(bits)


async def send_to_telegram(
    chat_id: int,
    text: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> int | None:
    """Send a text message to a Telegram chat; return the Telegram message_id."""
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_send_skipped_no_token", chat_id=chat_id)
        return None

    url = (
        f"{settings.TELEGRAM_API_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    )
    payload = {"chat_id": chat_id, "text": text}

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)

    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            logger.error(
                "telegram_send_failed", chat_id=chat_id, response=data
            )
            return None
        return int(data["result"]["message_id"])
    except httpx.HTTPError as exc:
        logger.error("telegram_send_error", chat_id=chat_id, error=str(exc))
        return None
    finally:
        if owns_client:
            await client.aclose()


# ── LLM steps ─────────────────────────────────────────────────────────────────


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    """Best-effort JSON parse — some providers wrap JSON in ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Strip leading fence + optional language tag, then trailing fence.
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("telegram_llm_json_parse_failed", text=text[:200])
        return None


async def match_product(
    conversation_snippet: str, candidates: list[Product]
) -> tuple[Product | None, float, str]:
    """Return (matched product or None, confidence 0-1, reasoning)."""
    if not candidates:
        return None, 0.0, "no products in catalog"

    catalog_payload = [
        {
            "sku": p.sku,
            "family": p.family,
            "model_name": p.model_name,
            "category": p.category,
            "tonnage": p.tonnage,
        }
        for p in candidates
    ]

    try:
        client, model = get_llm_client()
    except RuntimeError as exc:
        logger.error("telegram_llm_unavailable", error=str(exc))
        return None, 0.0, "llm unavailable"

    # OpenAI SDK is sync; run in thread so we don't block the event loop.
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": _PRODUCT_MATCH_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Catalog candidates:\n{json.dumps(catalog_payload, indent=2)}\n\n"
                    f"Customer conversation:\n{conversation_snippet}"
                ),
            },
        ],
        max_tokens=200,
        temperature=0.1,
    )
    parsed = _safe_json_loads(response.choices[0].message.content or "")
    if not parsed:
        return None, 0.0, "llm returned non-json"

    sku = parsed.get("sku")
    confidence = float(parsed.get("confidence") or 0.0)
    reasoning = str(parsed.get("reasoning") or "")
    if not sku or confidence < 0.5:
        return None, confidence, reasoning

    match = next((p for p in candidates if p.sku == sku), None)
    if match is None:
        # LLM hallucinated a SKU not in our list.
        logger.warning("telegram_product_match_hallucination", sku=sku)
        return None, confidence, reasoning
    return match, confidence, reasoning


async def classify_resolution(
    conversation_history: str, matched_product: Product | None
) -> dict[str, Any]:
    """Return classification dict {verdict, confidence, reasoning, suggested_tip}."""
    try:
        client, model = get_llm_client()
    except RuntimeError as exc:
        logger.error("telegram_llm_unavailable", error=str(exc))
        # Fail open to human path so customer is never stuck with the bot.
        return {
            "verdict": "human",
            "confidence": 0.0,
            "reasoning": f"llm unavailable: {exc}",
            "suggested_tip": None,
        }

    product_block = "No product matched yet."
    if matched_product is not None:
        common_issues = matched_product.common_issues or []
        product_block = (
            f"Matched product: {matched_product.family} "
            f"{matched_product.model_name} (sku {matched_product.sku}).\n"
            f"Known common issues:\n{json.dumps(common_issues, indent=2)}"
        )

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{product_block}\n\nCustomer conversation:\n{conversation_history}"
                ),
            },
        ],
        max_tokens=400,
        temperature=0.2,
    )
    parsed = _safe_json_loads(response.choices[0].message.content or "")
    if not parsed:
        return {
            "verdict": "human",
            "confidence": 0.0,
            "reasoning": "llm returned non-json",
            "suggested_tip": None,
        }

    verdict = parsed.get("verdict")
    if verdict not in ("ai", "human", "resolved"):
        verdict = "human"
    return {
        "verdict": verdict,
        "confidence": float(parsed.get("confidence") or 0.0),
        "reasoning": str(parsed.get("reasoning") or ""),
        "suggested_tip": parsed.get("suggested_tip"),
    }


_FACT_FIELDS = (
    "brand",
    "family",
    "model_name",
    "model_number",
    "serial_number",
    "capacity",
    "refrigerant",
    "install_type",
    "install_location",
    "purchase_date",
    "manufacture_date",
    "warranty_status",
    "issue_summary",
)
_FACT_LIST_FIELDS = ("symptoms", "tried_already")


async def extract_facts(
    history_text: str, prior_info: dict[str, Any] | None
) -> dict[str, Any]:
    """Update the conversation's structured facts dict using the LLM.

    Merges the LLM's reply with the prior info — LLM-provided non-null values
    overwrite, lists are unioned. Falls back to prior_info on LLM failure so
    we never lose what we already gathered.
    """
    prior = dict(prior_info or {})
    try:
        client, model = get_llm_client()
    except RuntimeError:
        return prior

    user_content = (
        f"Prior gathered_info:\n{json.dumps(prior, indent=2)}\n\n"
        f"Conversation so far:\n{history_text}"
    )

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": _FACT_EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=400,
            temperature=0.1,
        )
    except Exception as exc:  # pragma: no cover — best-effort
        logger.error("telegram_fact_extractor_error", error=str(exc))
        return prior

    parsed = _safe_json_loads(response.choices[0].message.content or "")
    if not parsed:
        return prior

    merged = dict(prior)
    for field in _FACT_FIELDS:
        new_val = parsed.get(field)
        if new_val is not None and new_val != "":
            merged[field] = new_val
    for field in _FACT_LIST_FIELDS:
        new_list = parsed.get(field) or []
        if isinstance(new_list, list) and new_list:
            existing = merged.get(field) or []
            seen = set(existing)
            for item in new_list:
                if item and item not in seen:
                    existing.append(item)
                    seen.add(item)
            merged[field] = existing
    return merged


async def ask_followup_question(conversation_snippet: str) -> str:
    """Ask a short clarifying question when we can't yet match a product."""
    try:
        client, model = get_llm_client()
    except RuntimeError:
        return (
            "Could you tell me the Carrier model name or family "
            "(Infinity / Performance / Comfort) of your unit?"
        )

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": _FOLLOWUP_QUESTION_PROMPT},
            {"role": "user", "content": conversation_snippet},
        ],
        max_tokens=120,
        temperature=0.4,
    )
    text = (response.choices[0].message.content or "").strip()
    return text or (
        "Could you tell me the Carrier model name or family "
        "(Infinity / Performance / Comfort) of your unit?"
    )


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _get_active_conversation(
    session: AsyncSession, chat_id: int
) -> SupportConversation | None:
    """Return the most recent non-closed conversation for a chat, if any."""
    result = await session.execute(
        select(SupportConversation)
        .where(
            SupportConversation.telegram_chat_id == chat_id,
            SupportConversation.status != "closed",
        )
        .order_by(desc(SupportConversation.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _create_new_conversation(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int | None,
    customer_name: str | None,
) -> SupportConversation:
    conversation = SupportConversation(
        telegram_chat_id=chat_id,
        telegram_user_id=user_id,
        customer_display_name_encrypted=(
            encrypt_raw_text(customer_name) if customer_name else None
        ),
        status="bot_collecting",
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def _get_or_create_conversation(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int | None,
    customer_name: str | None,
) -> tuple[SupportConversation, bool]:
    existing = await _get_active_conversation(session, chat_id)
    if existing is not None:
        return existing, False
    conversation = await _create_new_conversation(
        session, chat_id=chat_id, user_id=user_id, customer_name=customer_name
    )
    return conversation, True


async def _start_new_session(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int | None,
    customer_name: str | None,
) -> SupportConversation:
    """Close any active conversation for this chat and open a fresh one.

    Invoked when the customer sends /start so the dashboard shows a brand
    new ticket and the bot's product matching / gathered_info starts clean.
    """
    existing = await _get_active_conversation(session, chat_id)
    if existing is not None:
        existing.status = "closed"
        existing.escalation_reason = (
            (existing.escalation_reason or "") + " [closed by customer /start]"
        ).strip()
        await session.flush()
        logger.info(
            "telegram_session_reset",
            prior_conversation_id=existing.id,
            chat_id=chat_id,
        )
    return await _create_new_conversation(
        session, chat_id=chat_id, user_id=user_id, customer_name=customer_name
    )


async def _persist_inbound_message(
    session: AsyncSession,
    *,
    conversation: SupportConversation,
    raw_text: str,
    telegram_message_id: int | None,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> SupportMessage:
    redacted = strip_pii(raw_text)
    encrypted = encrypt_raw_text(raw_text)
    # Encrypt the image bytes with the same AES key used for raw text so the
    # at-rest threat model is consistent: anyone with DB access alone can't
    # see the photo the customer sent.
    image_blob: bytes | None = None
    if image_bytes:
        nonce_plus_ct = encrypt_raw_text(base64.b64encode(image_bytes).decode("ascii"))
        image_blob = nonce_plus_ct
    msg = SupportMessage(
        conversation_id=conversation.id,
        direction="inbound",
        body_redacted=redacted,
        body_encrypted=encrypted,
        telegram_message_id=telegram_message_id,
        image_encrypted=image_blob,
        image_mime=image_mime,
    )
    session.add(msg)
    conversation.last_message_at = datetime.now(tz=UTC)
    await session.flush()
    return msg


def decrypt_inbound_image(msg: SupportMessage) -> tuple[bytes, str] | None:
    """Decrypt the inbound message's image blob, returning (bytes, mime).

    Returns None if the message has no image attached.
    """
    if not msg.image_encrypted:
        return None
    from app.core.security import decrypt_raw_text

    b64 = decrypt_raw_text(msg.image_encrypted)
    return base64.b64decode(b64), msg.image_mime or "image/jpeg"


async def _persist_outbound_bot_message(
    session: AsyncSession,
    *,
    conversation: SupportConversation,
    body: str,
    llm_metadata: dict[str, Any] | None,
    telegram_message_id: int | None,
) -> SupportMessage:
    # Bot-generated text never contains customer PII — running strip_pii on it
    # only causes false-positive redactions of brand names (spaCy NER labels
    # "Carrier" / "Comfort" as ORG and strips them from messages we send out).
    # Store the body as-is; raw is still encrypted for retention parity.
    msg = SupportMessage(
        conversation_id=conversation.id,
        direction="outbound_bot",
        body_redacted=body,
        body_encrypted=encrypt_raw_text(body),
        llm_metadata=llm_metadata,
        telegram_message_id=telegram_message_id,
    )
    session.add(msg)
    conversation.last_message_at = datetime.now(tz=UTC)
    await session.flush()
    return msg


async def _persist_outbound_agent_message(
    session: AsyncSession,
    *,
    conversation: SupportConversation,
    body: str,
    telegram_message_id: int | None,
) -> SupportMessage:
    # Agent text is authored by an authenticated support agent. Don't redact.
    # Raw is still encrypted to keep storage parity with inbound messages.
    msg = SupportMessage(
        conversation_id=conversation.id,
        direction="outbound_agent",
        body_redacted=body,
        body_encrypted=encrypt_raw_text(body),
        telegram_message_id=telegram_message_id,
    )
    session.add(msg)
    conversation.last_message_at = datetime.now(tz=UTC)
    await session.flush()
    return msg


async def _recent_history(
    session: AsyncSession, conversation_id: int, limit: int = 12
) -> list[SupportMessage]:
    result = await session.execute(
        select(SupportMessage)
        .where(SupportMessage.conversation_id == conversation_id)
        .order_by(desc(SupportMessage.created_at))
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


def _format_history_for_llm(messages: list[SupportMessage]) -> str:
    lines = []
    for m in messages:
        speaker = {
            "inbound": "Customer",
            "outbound_bot": "Bot",
            "outbound_agent": "Agent",
        }.get(m.direction, m.direction)
        lines.append(f"{speaker}: {m.body_redacted}")
    return "\n".join(lines)


def _customer_only_text(messages: list[SupportMessage]) -> str:
    """Concatenate only the customer's inbound text — no bot greeting/questions.

    Used to build the Complaint row text when escalating, so embeddings and
    clustering see only what the customer said, not the bot's scaffolding.
    """
    return "\n".join(m.body_redacted for m in messages if m.direction == "inbound")


# ── Public entrypoints ────────────────────────────────────────────────────────


async def handle_inbound_message(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int | None,
    telegram_message_id: int | None,
    raw_text: str | None,
    customer_name: str | None,
    photo_file_id: str | None = None,
    photo_caption: str | None = None,
    celery_app=None,
    redis_client=None,
) -> dict[str, Any]:
    """Process a single inbound Telegram message end-to-end.

    If ``photo_file_id`` is set, the bot downloads the image via Telegram's
    file API, runs vision OCR over it, and treats the extracted product info
    as the customer's message (combined with ``photo_caption`` if present).
    Returns a dict with `conversation_id`, `verdict`, `escalated`, and the
    bot-reply text (or None if nothing was sent). Commits the session.
    """
    # ── /start: always open a brand new conversation (close any active one).
    # This is the standard Telegram bot convention and keeps each support
    # session as its own ticket on the dashboard.
    is_start_command = (raw_text or "").strip().lower() == "/start"
    if is_start_command:
        conversation = await _start_new_session(
            session,
            chat_id=chat_id,
            user_id=user_id,
            customer_name=customer_name,
        )
        is_new = True
    else:
        conversation, is_new = await _get_or_create_conversation(
            session, chat_id=chat_id, user_id=user_id, customer_name=customer_name
        )

    # ── Image branch: turn the photo into structured product facts, then
    # synthesize an inbound text line and proceed through the normal flow.
    image_facts: dict[str, Any] | None = None
    image_bytes: bytes | None = None
    image_mime: str | None = None
    if photo_file_id and not raw_text:
        # Acknowledge so the customer knows we got it (vision OCR takes a sec)
        await send_to_telegram(chat_id, "Got the photo — reading it now…")
        download = await download_telegram_file(photo_file_id)
        if download is None:
            raw_text = (
                "[Photo received but couldn't be downloaded.] "
                + (photo_caption or "")
            ).strip()
        else:
            image_bytes, image_mime = download
            image_facts = await analyze_image(image_bytes, mime=image_mime)
            raw_text = _image_facts_as_text(image_facts)
            if photo_caption:
                raw_text = f"{photo_caption.strip()}\n{raw_text}"
            logger.info(
                "telegram_image_analyzed",
                conversation_id=conversation.id,
                confidence=image_facts.get("confidence"),
                model_name=image_facts.get("model_name"),
                model_number=image_facts.get("model_number"),
            )

    # Guard: bot received only a non-text, non-photo update (sticker, voice, etc).
    if not raw_text:
        raw_text = "[Customer sent a non-text message we cannot process.]"

    await _persist_inbound_message(
        session,
        conversation=conversation,
        raw_text=raw_text,
        telegram_message_id=telegram_message_id,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )

    # If we have image facts, attach them to the inbound message's metadata
    # so the dashboard can surface "extracted from photo" details to the agent.
    if image_facts is not None:
        last_inbound = (
            (
                await session.execute(
                    select(SupportMessage)
                    .where(SupportMessage.conversation_id == conversation.id)
                    .order_by(desc(SupportMessage.id))
                    .limit(1)
                )
            )
            .scalar_one_or_none()
        )
        if last_inbound is not None:
            last_inbound.llm_metadata = {
                "kind": "image_ocr",
                **{k: v for k, v in image_facts.items() if k != "raw"},
            }
            await session.flush()

    # If a human agent has taken over, do not auto-reply — just persist and exit.
    if conversation.status == "agent_active":
        await session.commit()
        logger.info(
            "telegram_inbound_during_agent_active",
            conversation_id=conversation.id,
        )
        return {
            "conversation_id": conversation.id,
            "verdict": "agent_active",
            "escalated": False,
            "reply": None,
        }

    history = await _recent_history(session, conversation.id)
    history_text = _format_history_for_llm(history)

    # ── Fact extraction: keep the dashboard's "Product Information" panel
    # up to date. Best-effort; doesn't block bot reply on failure.
    try:
        new_info = await extract_facts(history_text, conversation.gathered_info)
        if new_info != conversation.gathered_info:
            conversation.gathered_info = new_info
            await session.flush()
    except Exception:  # pragma: no cover — logged inside extract_facts
        logger.exception("telegram_fact_extraction_failed")

    # ── Greet on first message before deciding anything ──────────────────────
    if is_new:
        await send_to_telegram(chat_id, _GREETING_TEXT)
        await _persist_outbound_bot_message(
            session,
            conversation=conversation,
            body=_GREETING_TEXT,
            llm_metadata={"kind": "greeting"},
            telegram_message_id=None,
        )

    # ── Product matching ─────────────────────────────────────────────────────
    matched_product = None
    if conversation.matched_product_id is not None:
        result = await session.execute(
            select(Product).where(Product.id == conversation.matched_product_id)
        )
        matched_product = result.scalar_one_or_none()

    # Count how many follow-up questions we've already sent in this conversation
    # and whether the customer just told us they don't know. Either signal
    # short-circuits the product-match loop so we don't badger them.
    prior_followups = sum(
        1
        for m in history
        if m.direction == "outbound_bot"
        and (m.llm_metadata or {}).get("kind") == "followup"
    )
    customer_gave_up = _user_said_idk(raw_text)
    skip_product_match = (
        prior_followups >= _MAX_FOLLOWUPS_BEFORE_CLASSIFY or customer_gave_up
    )

    if matched_product is None and not skip_product_match:
        all_products = list(
            (await session.execute(select(Product))).scalars().all()
        )
        candidates = _keyword_prefilter(history_text, all_products)
        matched_product, match_conf, match_reason = await match_product(
            history_text, candidates
        )
        if matched_product is not None:
            conversation.matched_product_id = matched_product.id
            logger.info(
                "telegram_product_matched",
                conversation_id=conversation.id,
                sku=matched_product.sku,
                confidence=match_conf,
            )
        else:
            # Still no match — ask one more follow-up, but only if we haven't
            # already hit the cap. The follow-up prompt now sees full history
            # so it doesn't repeat itself.
            followup = await ask_followup_question(history_text)
            tg_msg_id = await send_to_telegram(chat_id, followup)
            await _persist_outbound_bot_message(
                session,
                conversation=conversation,
                body=followup,
                llm_metadata={
                    "kind": "followup",
                    "match_confidence": match_conf,
                    "match_reasoning": match_reason,
                    "followup_index": prior_followups + 1,
                },
                telegram_message_id=tg_msg_id,
            )
            await session.commit()
            return {
                "conversation_id": conversation.id,
                "verdict": "awaiting_info",
                "escalated": False,
                "reply": followup,
            }

    # If we got here without a matched product, log why and continue to classify.
    if matched_product is None:
        logger.info(
            "telegram_proceeding_without_product_match",
            conversation_id=conversation.id,
            prior_followups=prior_followups,
            customer_gave_up=customer_gave_up,
        )

    # ── Resolved-conversation short-circuit ─────────────────────────────────
    # If the customer says "thanks / resolved / it works" and the last bot
    # message was an AI troubleshooting tip, treat the conversation as
    # successfully closed — no LLM classify call, no human escalation.
    if _user_said_resolved(raw_text):
        last_bot_msg = next(
            (m for m in reversed(history) if m.direction == "outbound_bot"),
            None,
        )
        last_was_ai_tip = (
            last_bot_msg is not None
            and (last_bot_msg.llm_metadata or {}).get("kind") == "ai_resolution"
        )
        if last_was_ai_tip:
            conversation.status = "bot_resolved"
            tg_msg_id = await send_to_telegram(chat_id, _RESOLUTION_CLOSING_TEXT)
            await _persist_outbound_bot_message(
                session,
                conversation=conversation,
                body=_RESOLUTION_CLOSING_TEXT,
                llm_metadata={"kind": "closing"},
                telegram_message_id=tg_msg_id,
            )
            await session.commit()
            logger.info(
                "telegram_conversation_self_resolved",
                conversation_id=conversation.id,
            )
            return {
                "conversation_id": conversation.id,
                "verdict": "resolved",
                "escalated": False,
                "reply": _RESOLUTION_CLOSING_TEXT,
            }

    # ── Classify resolution path ─────────────────────────────────────────────
    classification = await classify_resolution(history_text, matched_product)
    settings = get_settings()
    confidence = classification["confidence"]

    # Handle "resolved" verdict from the LLM as a graceful close too.
    if classification["verdict"] == "resolved":
        conversation.status = "bot_resolved"
        tg_msg_id = await send_to_telegram(chat_id, _RESOLUTION_CLOSING_TEXT)
        await _persist_outbound_bot_message(
            session,
            conversation=conversation,
            body=_RESOLUTION_CLOSING_TEXT,
            llm_metadata={
                "kind": "closing",
                "confidence": confidence,
                "reasoning": classification["reasoning"],
            },
            telegram_message_id=tg_msg_id,
        )
        await session.commit()
        logger.info(
            "telegram_conversation_llm_resolved",
            conversation_id=conversation.id,
            confidence=confidence,
        )
        return {
            "conversation_id": conversation.id,
            "verdict": "resolved",
            "escalated": False,
            "reply": _RESOLUTION_CLOSING_TEXT,
        }

    is_ai_resolvable = (
        classification["verdict"] == "ai"
        and confidence >= settings.TELEGRAM_AI_CONFIDENCE_THRESHOLD
        and classification.get("suggested_tip")
    )

    if is_ai_resolvable:
        tip = classification["suggested_tip"]
        tg_msg_id = await send_to_telegram(chat_id, tip)
        await _persist_outbound_bot_message(
            session,
            conversation=conversation,
            body=tip,
            llm_metadata={
                "kind": "ai_resolution",
                "verdict": "ai",
                "confidence": confidence,
                "reasoning": classification["reasoning"],
                "matched_product_sku": (
                    matched_product.sku if matched_product else None
                ),
            },
            telegram_message_id=tg_msg_id,
        )
        # Stay in bot_collecting so a follow-up "didn't work" can re-classify.
        await session.commit()
        return {
            "conversation_id": conversation.id,
            "verdict": "ai",
            "escalated": False,
            "reply": tip,
        }

    # ── Human path: escalate, link to complaint pipeline ─────────────────────
    await _escalate_to_human(
        session,
        conversation=conversation,
        matched_product=matched_product,
        history_text=history_text,
        classification=classification,
        celery_app=celery_app,
        redis_client=redis_client,
    )
    tg_msg_id = await send_to_telegram(chat_id, _ESCALATION_TEXT)
    await _persist_outbound_bot_message(
        session,
        conversation=conversation,
        body=_ESCALATION_TEXT,
        llm_metadata={
            "kind": "escalation_notice",
            "verdict": classification["verdict"],
            "confidence": confidence,
            "reasoning": classification["reasoning"],
        },
        telegram_message_id=tg_msg_id,
    )
    await session.commit()
    return {
        "conversation_id": conversation.id,
        "verdict": "human",
        "escalated": True,
        "reply": _ESCALATION_TEXT,
    }


async def _escalate_to_human(
    session: AsyncSession,
    *,
    conversation: SupportConversation,
    matched_product: Product | None,
    history_text: str,
    classification: dict[str, Any],
    celery_app,
    redis_client,
) -> None:
    """Mark conversation as escalated and create a Complaint row.

    The Complaint row flows into the existing embedding → sentiment →
    clustering pipeline automatically because `ingest_complaints` queues
    those tasks. When celery_app/redis_client are not provided (e.g.
    test mode), the DB row is still created but background tasks are
    skipped.
    """
    from app.schemas.complaint import ComplaintIngest

    conversation.status = "escalated"
    conversation.escalation_reason = classification.get("reasoning") or "human_needed"

    if celery_app is None or redis_client is None:
        logger.info(
            "telegram_escalate_no_celery_skip_pipeline",
            conversation_id=conversation.id,
        )
        return

    # Build complaint text from customer-only messages so the embedding /
    # clustering pipeline doesn't see the bot's greeting or questions —
    # only what the customer actually said (or what we OCR'd from photos).
    all_msgs = (
        (
            await session.execute(
                select(SupportMessage)
                .where(SupportMessage.conversation_id == conversation.id)
                .order_by(SupportMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    customer_text = _customer_only_text(list(all_msgs)).strip()
    if not customer_text:
        # Fallback to the LLM-history view if no inbound text yet (shouldn't
        # really happen, but keeps the row creatable).
        customer_text = history_text[:5000]

    payload = ComplaintIngest(
        text=customer_text[:5000],
        source="telegram",
        region=None,
        product_sku=matched_product.sku if matched_product else None,
    )
    accepted, queued = await ingest_complaints(
        [payload], session, redis_client, celery_app
    )

    # Re-fetch the complaint id we just created — it's the most recent row
    # for this conversation's source within the same transaction.
    from app.models.complaint import Complaint

    result = await session.execute(
        select(Complaint.id)
        .where(Complaint.source == "telegram")
        .order_by(desc(Complaint.id))
        .limit(1)
    )
    complaint_id = result.scalar_one_or_none()
    if complaint_id is not None:
        conversation.complaint_id = complaint_id

    logger.info(
        "telegram_escalation_complaint_created",
        conversation_id=conversation.id,
        complaint_id=complaint_id,
        accepted=accepted,
        queued=queued,
    )


async def send_agent_reply(
    session: AsyncSession, *, conversation_id: int, body: str
) -> SupportMessage:
    """Send a human-agent reply via Telegram and persist it.

    Raises ValueError if the conversation can't be found.
    """
    result = await session.execute(
        select(SupportConversation).where(SupportConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise ValueError(f"conversation {conversation_id} not found")

    tg_msg_id = await send_to_telegram(conversation.telegram_chat_id, body)
    message = await _persist_outbound_agent_message(
        session,
        conversation=conversation,
        body=body,
        telegram_message_id=tg_msg_id,
    )
    conversation.status = "agent_active"
    await session.commit()
    return message


async def resolve_conversation(
    session: AsyncSession, *, conversation_id: int
) -> SupportConversation:
    result = await session.execute(
        select(SupportConversation).where(SupportConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise ValueError(f"conversation {conversation_id} not found")

    await send_to_telegram(conversation.telegram_chat_id, _RESOLUTION_CLOSING_TEXT)
    await _persist_outbound_bot_message(
        session,
        conversation=conversation,
        body=_RESOLUTION_CLOSING_TEXT,
        llm_metadata={"kind": "closing"},
        telegram_message_id=None,
    )
    conversation.status = "closed"
    await session.commit()
    return conversation


async def list_tickets(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return inbox rows ordered by last_message_at desc."""
    stmt = select(SupportConversation)
    if status_filter:
        stmt = stmt.where(SupportConversation.status == status_filter)
    stmt = stmt.order_by(desc(SupportConversation.last_message_at)).limit(limit)

    conversations = list((await session.execute(stmt)).scalars().all())
    if not conversations:
        return []

    # Batch-fetch the last message + count per conversation in one query each.
    convo_ids = [c.id for c in conversations]
    counts_stmt = (
        select(SupportMessage.conversation_id, func.count(SupportMessage.id))
        .where(SupportMessage.conversation_id.in_(convo_ids))
        .group_by(SupportMessage.conversation_id)
    )
    counts = {row[0]: row[1] for row in (await session.execute(counts_stmt)).all()}

    last_msg_stmt = (
        select(SupportMessage)
        .where(SupportMessage.conversation_id.in_(convo_ids))
        .order_by(SupportMessage.conversation_id, desc(SupportMessage.created_at))
    )
    last_messages: dict[int, SupportMessage] = {}
    for msg in (await session.execute(last_msg_stmt)).scalars().all():
        if msg.conversation_id not in last_messages:
            last_messages[msg.conversation_id] = msg

    product_ids = {c.matched_product_id for c in conversations if c.matched_product_id}
    products: dict[int, Product] = {}
    if product_ids:
        prod_rows = (
            await session.execute(select(Product).where(Product.id.in_(product_ids)))
        ).scalars().all()
        products = {p.id: p for p in prod_rows}

    out: list[dict[str, Any]] = []
    for c in conversations:
        last = last_messages.get(c.id)
        out.append(
            {
                "id": c.id,
                "status": c.status,
                "matched_product": products.get(c.matched_product_id)
                if c.matched_product_id
                else None,
                "last_message_preview": (last.body_redacted[:140] if last else None),
                "last_message_direction": last.direction if last else None,
                "message_count": counts.get(c.id, 0),
                "created_at": c.created_at,
                "last_message_at": c.last_message_at,
            }
        )
    return out


async def get_ticket_detail(
    session: AsyncSession, conversation_id: int
) -> dict[str, Any] | None:
    result = await session.execute(
        select(SupportConversation).where(SupportConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        return None

    msgs = (
        (
            await session.execute(
                select(SupportMessage)
                .where(SupportMessage.conversation_id == conversation_id)
                .order_by(SupportMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    matched_product = None
    if conversation.matched_product_id:
        matched_product = (
            await session.execute(
                select(Product).where(Product.id == conversation.matched_product_id)
            )
        ).scalar_one_or_none()

    # Customer display name: do NOT decrypt for dashboard — return a redacted
    # placeholder. This keeps PII out of agent screens unless explicitly opted in.
    customer_display_name = (
        "[encrypted]" if conversation.customer_display_name_encrypted else None
    )

    return {
        "conversation": conversation,
        "messages": list(msgs),
        "matched_product": matched_product,
        "customer_display_name": customer_display_name,
    }


# ── Telegram getUpdates polling (called from celery worker) ───────────────────


async def fetch_updates(
    *,
    offset: int | None,
    timeout_seconds: int,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Long-poll Telegram's getUpdates endpoint; return list of updates."""
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        return []

    url = (
        f"{settings.TELEGRAM_API_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates"
    )
    params: dict[str, Any] = {"timeout": timeout_seconds}
    if offset is not None:
        params["offset"] = offset

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_seconds + 10)

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            logger.error("telegram_getupdates_failed", response=data)
            return []
        return list(data.get("result") or [])
    except httpx.HTTPError as exc:
        logger.error("telegram_getupdates_error", error=str(exc))
        return []
    finally:
        if owns_client:
            await client.aclose()


def extract_inbound(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract chat_id / user_id / text / photo / captions from a Telegram update.

    Returns None for non-message updates (callbacks, edits, etc.).
    For photo messages, returns the largest photo's ``file_id`` plus any
    caption. For audio/voice/sticker, returns ``raw_text=None`` and no photo
    — caller will ask the customer for text.
    """
    message = update.get("message") or update.get("channel_post")
    if not message:
        return None

    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    text = message.get("text")
    caption = message.get("caption")

    # Photos arrive as a list of PhotoSize objects in ascending resolution;
    # the last one is the highest resolution available.
    photo_file_id = None
    photos = message.get("photo") or []
    if isinstance(photos, list) and photos:
        photo_file_id = photos[-1].get("file_id")

    return {
        "chat_id": chat.get("id"),
        "user_id": from_user.get("id"),
        "telegram_message_id": message.get("message_id"),
        "raw_text": text,
        "photo_file_id": photo_file_id,
        "photo_caption": caption,
        "customer_name": _display_name(from_user),
    }


def _display_name(user: dict[str, Any]) -> str | None:
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    username = (user.get("username") or "").strip()
    full = " ".join(p for p in (first, last) if p).strip()
    return full or (f"@{username}" if username else None)


# ── Convenience for tests / scripts ──────────────────────────────────────────


async def mark_conversation_updated_at(
    session: AsyncSession, conversation_id: int
) -> None:
    """Bump updated_at — used by tests; production paths handle this implicitly."""
    await session.execute(
        update(SupportConversation)
        .where(SupportConversation.id == conversation_id)
        .values(updated_at=datetime.now(tz=UTC))
    )
