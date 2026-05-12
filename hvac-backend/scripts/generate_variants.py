"""Generate varied tenant-voice complaint text per cluster using DeepSeek.

Idempotent + resumable: progress saved to /tmp/generated_variants.json after every
cluster. Re-run skips clusters already populated. Tolerant of malformed JSON
responses (one retry with stricter wording, then skip).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI
from sqlalchemy import create_engine, text

OUT = Path("/tmp/generated_variants.json")

PROMPT = (
    "You generate REALISTIC tenant complaints for an HVAC complaint analysis demo.\n\n"
    "CLUSTER THEME: {label}\n"
    "EXAMPLES OF BOILERPLATE TEXT (do not copy):\n{samples}\n\n"
    "Output ONLY a JSON OBJECT with one key 'complaints' whose value is an array "
    "of 30 strings. Each string is one varied, natural tenant-voice complaint "
    "about this theme. Mix tones (frustrated, urgent, resigned, polite), mix "
    "lengths (1-3 sentences), mention NYC boroughs naturally, NO inspector / "
    "HPD / 311 references, NO names or addresses, NO numbered prefixes. Each "
    "complaint is plain text with NO embedded quotes inside the string. Be terse.\n\n"
    "Schema: {{\"complaints\": [\"...\", \"...\", ...]}}"
)


def load_state() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text())
    return {}


def save_state(state: dict) -> None:
    OUT.write_text(json.dumps(state))


def extract_array(content: str) -> list[str] | None:
    # Strict JSON first
    try:
        d = json.loads(content)
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, list):
                    return [str(s).strip() for s in v if isinstance(s, str)]
        if isinstance(d, list):
            return [str(s).strip() for s in d if isinstance(s, str)]
    except Exception:
        pass
    # Lenient: pluck quoted strings between [ ... ]
    m = re.search(r"\[(.*)\]", content, re.S)
    if not m:
        return None
    items = re.findall(r'"((?:\\.|[^"\\])*)"', m.group(1))
    cleaned = [
        s.encode("utf-8", "ignore").decode("unicode_escape", "ignore").strip()
        for s in items
        if len(s) > 10
    ]
    return cleaned or None


def main() -> int:
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )
    engine = create_engine(os.environ["DATABASE_SYNC_URL"])

    SQL = """
    SELECT c.id AS cluster_id, c.label,
           (array_agg(comp.clean_text ORDER BY comp.id))[1:2] AS samples
    FROM clusters c
    JOIN complaints comp ON comp.cluster_id = c.id
    WHERE c.label IS NOT NULL AND comp.source = 'nyc_311'
    GROUP BY c.id, c.label
    ORDER BY c.id;
    """
    with engine.connect() as conn:
        rows = conn.execute(text(SQL)).fetchall()

    state = load_state()
    print(f"clusters: {len(rows)}, already_have: {len(state)}", flush=True)

    for i, (ci, label, samples) in enumerate(rows):
        key = str(ci)
        if key in state and len(state[key]) >= 20:
            print(f"  [{i+1}/{len(rows)}] cluster {ci} cached — skip", flush=True)
            continue

        samples_str = "\n".join(f"- {s[:160]}" for s in (samples or [])[:2])
        prompt = PROMPT.format(label=label, samples=samples_str)

        variants: list[str] = []
        for attempt in (0, 1):
            try:
                resp = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.9 if attempt == 0 else 0.5,
                    max_tokens=2500,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or ""
                arr = extract_array(content)
                if arr and len(arr) >= 10:
                    variants = arr
                    break
            except Exception as e:  # noqa: BLE001
                print(
                    f"  [{i+1}/{len(rows)}] cluster {ci} attempt {attempt} error: "
                    f"{type(e).__name__}: {str(e)[:100]}",
                    flush=True,
                )

        state[key] = variants
        save_state(state)
        status = f"{len(variants)} variants" if variants else "FAILED"
        print(
            f"  [{i+1}/{len(rows)}] cluster {ci} ({(label or '')[:40]}): {status}",
            flush=True,
        )

    total = sum(len(v) for v in state.values())
    filled = sum(1 for v in state.values() if v)
    print(
        f"\nDONE. clusters_filled={filled}/{len(rows)}  total_variants={total}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
