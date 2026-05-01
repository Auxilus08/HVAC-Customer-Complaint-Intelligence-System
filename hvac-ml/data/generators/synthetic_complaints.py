"""Offline template-based synthetic HVAC complaint generator.

Produces a deterministic DataFrame of N complaints across 8 categories,
with realistic source / region / product variation and language mixing
(English / Hinglish / angry-CAPS). Includes a deliberate spike of
compressor_noise complaints in Delhi over the most recent 7 days so
downstream trend detection has a real signal to fire on.

Run: python -m data.generators.synthetic_complaints
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


CATEGORY_DISTRIBUTION: dict[str, float] = {
    "cooling_inefficiency": 0.18,
    "compressor_noise": 0.14,
    "water_leakage": 0.12,
    "service_delay": 0.12,
    "electrical_tripping": 0.10,
    "installation_defect": 0.10,
    "noise_misc": 0.10,
    "billing_dispute": 0.09,
    "gas_leak": 0.05,
}

SOURCES: list[str] = ["crm", "whatsapp", "email", "app", "field_tech", "call_center"]

REGIONS: list[str] = [
    "Delhi",
    "Mumbai",
    "Bangalore",
    "Chennai",
    "Hyderabad",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Noida",
    "Gurgaon",
]

PRODUCT_SKUS: list[str] = [
    "1.0T-SPLIT",
    "1.5T-SPLIT",
    "2.0T-SPLIT",
    "1.5T-WINDOW",
    "2.0T-CASSETTE",
    "3.0T-DUCT",
]

# ── Templates: (category, language) → list of phrase fragments ───────────────
# Each template list provides multiple natural phrasings; sentences are
# composed by combining 1-3 fragments for length variation (10-40 words).

ENGLISH_TEMPLATES: dict[str, list[str]] = {
    "cooling_inefficiency": [
        "AC is not cooling the room properly even after running for three hours",
        "The temperature stays at 30 degrees no matter what we set on the remote",
        "Room still feels hot and humid, the AC is barely making any difference",
        "Cooling has been very poor since last week, almost no cold air comes out",
        "We set it to 18 but the room is still 28 degrees after a long time",
    ],
    "compressor_noise": [
        "There is a loud grinding noise coming from the outdoor compressor unit",
        "Compressor makes a very loud humming sound that wakes us up at night",
        "Outdoor unit has started making rattling and banging noises since yesterday",
        "Heavy vibration and noise from the outdoor unit, neighbours have complained",
        "Loud knocking sound from compressor every time the AC starts up",
    ],
    "water_leakage": [
        "Water is dripping continuously from the indoor unit onto the floor",
        "There is heavy water leakage from the AC and it has damaged the wall",
        "Indoor unit is leaking water, we had to place a bucket below it",
        "Water keeps coming out of the front grill of the indoor unit",
        "AC has been leaking water all morning and the carpet is now soaked",
    ],
    "electrical_tripping": [
        "The AC trips the MCB after running for around five minutes every time",
        "Main circuit breaker keeps tripping whenever we switch on the AC",
        "There is some electrical issue, MCB trips the moment compressor starts",
        "AC repeatedly trips the breaker, we cannot use it for more than ten minutes",
        "Whenever the AC is turned on, the entire room loses power within a minute",
    ],
    "installation_defect": [
        "Installation was done very poorly, the copper pipe is not insulated at all",
        "The outdoor unit bracket is loose and shaking, looks like installation defect",
        "Indoor unit is not levelled properly and water drips because of the slope",
        "Pipe insulation is missing in several places, condensation forms on the wall",
        "Installation team did a sloppy job, drainage pipe is not connected correctly",
    ],
    "service_delay": [
        "The technician never showed up despite three confirmed appointments this week",
        "It has been three weeks since I raised the complaint and still no one came",
        "Service request was logged ten days ago and there is still no response",
        "Booking keeps getting cancelled at the last minute, very unprofessional",
        "Customer care promised next-day service but no one has come for four days",
    ],
    "billing_dispute": [
        "I was charged twice for the same service visit on the credit card statement",
        "The invoice amount is different from the quote that was given on phone",
        "Extra hidden charges were added to my bill that were never explained",
        "Wrong amount has been charged, the bill is almost double the original quote",
        "Invoice shows charges for parts that were never actually replaced or installed",
    ],
    "gas_leak": [
        "There is a strong hissing sound near the outdoor unit and a chemical smell",
        "I can smell refrigerant gas around the AC unit, this seems unsafe",
        "Faint hissing noise from the indoor unit and a strange smell in the room",
        "Suspect gas leak from outdoor unit, hissing sound has been there for days",
        "Strong gas smell near the AC, family is feeling uncomfortable in the room",
    ],
    "noise_misc": [
        "There is a strange clicking sound from the indoor unit every few minutes",
        "Indoor blower is making a whistling noise that we never heard before",
        "Squeaking and creaking sound from the indoor fan whenever AC is running",
        "A constant buzzing sound from the indoor unit is very disturbing at night",
        "Some unusual ticking and snapping sounds from the indoor swing motor",
    ],
}

HINGLISH_TEMPLATES: dict[str, list[str]] = {
    "cooling_inefficiency": [
        "AC bilkul thanda nahi kar raha hai, room ekdum garam hai abhi bhi",
        "Cooling theek se nahi ho rahi, kamre ka temperature kam hi nahi ho raha",
        "Itni heat hai room mein, AC chala kar bhi koi farak nahi pad raha",
        "Yaar AC barabar cooling nahi de raha, raat bhar pasine se bura haal hai",
        "Remote pe 18 set kiya hai par room garam hi rehta hai pura time",
    ],
    "compressor_noise": [
        "Outdoor unit se bahut zyada noise aa rahi hai, neighbours bhi complain kar rahe",
        "Compressor se grinding wali awaaz aati hai jab bhi AC chalu karte hain",
        "Bahar wali unit bahut khatarnak awaaz kar rahi hai, kuch toot raha lagta hai",
        "Outdoor unit pe bohot loud humming sound hai, raat ko neend nahi aati",
        "Compressor start hote hi bahut tez khat-khat ki awaaz aane lagti hai",
    ],
    "water_leakage": [
        "Indoor unit se paani tapak raha hai continuously, neeche balti rakhni padi",
        "AC ke andar wali unit se paani lagatar gir raha hai, deewar kharab ho gayi",
        "Pani tapak raha hai AC se aur fursh poora geela ho gaya hai",
        "Indoor unit ke grill se pani aa raha hai, carpet bhi geela ho gaya",
        "AC se paani lagatar tapak raha hai subah se, bahut pareshani ho rahi hai",
    ],
    "electrical_tripping": [
        "AC chalate hi MCB trip ho jaata hai paanch minute mein har baar",
        "Main breaker bar bar gir jaata hai jab bhi AC ko on karte hain",
        "Electric ka problem hai, compressor start hote hi MCB trip ho jata hai",
        "AC chalu karte hi pure ghar ki light chali jaati hai, kuch garbar hai",
        "Har baar AC on karne pe MCB neeche gir jaata hai, dus minute bhi nahi chal pata",
    ],
    "installation_defect": [
        "Installation bahut ghatiya ki hai, pipe ko proper insulate nahi kiya",
        "Outdoor unit ka bracket dheela hai aur unit hil rahi hai, installation issue",
        "Indoor unit seedha nahi laga, isi liye paani tapak raha hai pura time",
        "Pipe ki insulation kayi jagah pe missing hai, deewar kharab ho rahi hai",
        "Installation wale bande ne sahi se kaam nahi kiya, drainage bhi galat lagi hai",
    ],
    "service_delay": [
        "Technician aaya hi nahi, teen baar appointment confirm kiya tha phir bhi nahi aaya",
        "Tin hafte ho gaye complaint kiye hue, abhi tak koi nahi aaya repair karne",
        "Service request dala tha das din pehle, abhi tak koi response nahi aaya",
        "Booking baar baar last minute pe cancel ho jati hai, bahut unprofessional hai",
        "Customer care bola tha kal aayega, char din ho gaye koi nahi aaya",
    ],
    "billing_dispute": [
        "Ek hi service ke liye do baar paisa kaat liya credit card se, ye galat hai",
        "Invoice mein amount alag hai aur phone pe quote alag bataya tha",
        "Bill mein extra charges add kar diye jo kabhi bataye hi nahi the",
        "Galat amount charge kar diya, bill quote se almost double hai",
        "Invoice mein un parts ka bhi paisa lag gaya jo kabhi replace hi nahi hue",
    ],
    "gas_leak": [
        "Outdoor unit se hissing ki awaaz aa rahi hai aur chemical jaisi smell bhi",
        "AC ke paas refrigerant gas ki smell aa rahi hai, safety ka concern hai",
        "Indoor unit se halki si hissing aa rahi hai aur kamre mein ajeeb smell",
        "Lagta hai gas leak ho rahi hai outdoor se, hissing kafi din se aa rahi hai",
        "AC ke paas gas ki strong smell aa rahi hai, family ko uncomfortable lag raha",
    ],
    "noise_misc": [
        "Indoor unit se ajeeb si click click ki awaaz aati hai har kuch minute pe",
        "Indoor blower se seeti jaisi awaaz aa rahi hai, aisi pehle kabhi nahi suni",
        "Indoor fan se chu chu aur kar kar ki awaaz aati hai jab bhi chalta hai",
        "Indoor unit se lagatar buzzing ki awaaz hai, raat ko bahut disturb hota hai",
        "Indoor unit ke swing motor se ajeeb si tick tick aur snap ki awaaz aati hai",
    ],
}


# ── Closing tail fragments — appended to ~85% of complaints to break duplicates.
_ENGLISH_TAILS: list[str] = [
    "Please send a technician at the earliest convenience",
    "Looking forward to a quick resolution from your team",
    "This issue has been going on for several days now",
    "Kindly escalate this to the service supervisor",
    "Need someone to inspect and resolve this urgently",
    "Customer is extremely frustrated with the delay",
    "Have already raised this multiple times before",
    "Expecting a callback within 24 hours regarding this",
    "Will consider switching brands if this is not fixed",
    "Please share an estimated time of arrival for the visit",
    "This is the third time we are reporting the same problem",
    "Hoping for a permanent fix and not just a temporary patch",
    "Unit was purchased less than a year ago, still under warranty",
    "Send the senior engineer this time, junior could not fix it",
    "Cannot use the AC at all, family is suffering in this heat",
]
_HINGLISH_TAILS: list[str] = [
    "Jaldi se technician bhejo bhai, problem solve karwao",
    "Resolution chahiye urgent basis pe, please",
    "Pehle bhi complaint kiye the par koi action nahi hua",
    "Senior engineer bhejna is baar, junior se kaam nahi banta",
    "Warranty period mein hai abhi bhi product, free repair karwao",
    "Customer care ko bata diya hai, ab aap log respond karo",
    "Bahut din se ye problem chal rahi hai, please dekho",
    "Iss baar permanent solution chahiye, temporary fix se kaam nahi chalega",
    "Garmi mein bahut takleef ho rahi hai, jaldi karo please",
    "Agar nahi sudhra to dusra brand le lenge, decision le liya hai",
]
_OPENERS: list[str] = [
    "Hello team,",
    "Hi,",
    "Dear customer service,",
    "To whom it may concern:",
    "Hi support,",
    "",  # empty allows pure body
    "",
    "",
]
_HINGLISH_OPENERS: list[str] = [
    "Bhai,",
    "Sir ji,",
    "Hello team,",
    "Suniye,",
    "",
    "",
    "",
]


def _build_text(rng: np.random.Generator, category: str, language: str) -> str:
    """Compose a complaint of 10-40 words from opener + body + tail fragments.

    Three-component composition (opener × body × tail) explodes the unique
    surface forms from O(templates) to O(templates × tails × openers), driving
    the duplicate rate from ~46% to <5%.
    """
    is_hinglish = language == "hinglish"
    pool = (HINGLISH_TEMPLATES if is_hinglish else ENGLISH_TEMPLATES)[category]
    tails_pool = _HINGLISH_TAILS if is_hinglish else _ENGLISH_TAILS
    openers_pool = _HINGLISH_OPENERS if is_hinglish else _OPENERS

    # Body: 1 fragment 30%, 2 fragments 70% — biases toward composed sentences.
    n_fragments = int(rng.choice([1, 2], p=[0.30, 0.70]))
    body = rng.choice(pool, size=min(n_fragments, len(pool)), replace=False)
    body_text = ". ".join(body).rstrip(".") + "."

    # Tail: ~85% of complaints get a closing line.
    parts: list[str] = []
    opener = str(rng.choice(openers_pool))
    if opener:
        parts.append(opener)
    parts.append(body_text)
    if rng.random() < 0.85:
        parts.append(str(rng.choice(tails_pool)) + ".")

    text = " ".join(parts).strip()
    words = text.split()
    if len(words) > 40:
        text = " ".join(words[:40]).rstrip(",.") + "."
    return text


_ANGRY_INTENSIFIERS: list[str] = [
    "WORST",
    "PATHETIC",
    "USELESS",
    "TERRIBLE",
    "DISGUSTED",
    "FRAUD",
]


def _angrify(rng: np.random.Generator, text: str) -> str:
    """Convert a polite complaint into shouty angry-customer style."""
    intensifier = rng.choice(_ANGRY_INTENSIFIERS)
    bangs = "!" * int(rng.integers(2, 5))
    shouted = text.upper().rstrip(".")
    shouted = shouted.replace(", ", " ").replace("...", "")
    return f"{intensifier} SERVICE{bangs} {shouted}{bangs}"


def _pick_language(rng: np.random.Generator) -> str:
    return rng.choice(
        ["english", "hinglish", "angry"],
        p=[0.70, 0.20, 0.10],
    )


def _allocate_counts(n: int) -> dict[str, int]:
    """Allocate exactly *n* complaints across categories per the distribution."""
    counts = {cat: int(round(pct * n)) for cat, pct in CATEGORY_DISTRIBUTION.items()}
    diff = n - sum(counts.values())
    keys = list(counts.keys())
    i = 0
    while diff != 0:
        if diff > 0:
            counts[keys[i % len(keys)]] += 1
            diff -= 1
        else:
            if counts[keys[i % len(keys)]] > 0:
                counts[keys[i % len(keys)]] -= 1
                diff += 1
        i += 1
    return counts


def _build_region_plan(
    rng: np.random.Generator, counts: dict[str, int]
) -> dict[str, list[str]]:
    """Pre-allocate a region for every complaint with stratified balance.

    For non-spike categories: round-robin across regions so each region gets
    the same count ± 1 — eliminates the small-N sampling noise that otherwise
    leaves billing_dispute / service_delay with 1-2% Delhi share.

    For compressor_noise: ~40% goes to Delhi (engineered spike), the remaining
    60% is round-robined across the other 9 regions.
    """
    plan: dict[str, list[str]] = {}
    for cat, count in counts.items():
        if cat == "compressor_noise":
            delhi_count = int(round(count * 0.40))
            others = [r for r in REGIONS if r != "Delhi"]
            seq = ["Delhi"] * delhi_count
            remaining = count - delhi_count
            for i in range(remaining):
                seq.append(others[i % len(others)])
        else:
            seq = [REGIONS[i % len(REGIONS)] for i in range(count)]
        # Deterministic shuffle so regions aren't blocky in CSV order.
        rng.shuffle(seq)
        plan[cat] = seq
    return plan


def _generate_timestamp(
    rng: np.random.Generator,
    category: str,
    region: str,
    now: datetime,
) -> datetime:
    """Spread over last 90 days. For compressor_noise + Delhi the date
    distribution is heavily skewed so current-week count ≈ 3.8× previous-week
    count, yielding the +280% WoW signal trend detection needs to fire.
    """
    if category == "compressor_noise" and region == "Delhi":
        bucket = rng.choice(
            ["current_week", "previous_week", "older"],
            p=[0.62, 0.16, 0.22],
        )
        if bucket == "current_week":
            offset_days = float(rng.uniform(0, 7))
        elif bucket == "previous_week":
            offset_days = float(rng.uniform(7, 14))
        else:
            offset_days = float(rng.uniform(14, 90))
    else:
        offset_days = float(rng.uniform(0, 90))
    seconds = float(rng.uniform(0, 86400))
    return now - timedelta(days=offset_days, seconds=seconds)


def generate_complaints(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate *n* synthetic complaints deterministically.

    Returns a pandas DataFrame with the columns specified in the sprint spec:
    complaint_id, complaint_text, source, region, product_sku, created_at, category.
    """
    rng = np.random.default_rng(seed)
    now = datetime.now(tz=timezone.utc)
    counts = _allocate_counts(n)
    region_plan = _build_region_plan(rng, counts)

    rows: list[dict[str, object]] = []
    for category, count in counts.items():
        for i in range(count):
            language = _pick_language(rng)
            base_lang = "hinglish" if language == "hinglish" else "english"
            text = _build_text(rng, category, base_lang)
            if language == "angry":
                text = _angrify(rng, text)

            region = region_plan[category][i]
            uuid_bytes = bytearray(rng.bytes(16))
            uuid_bytes[6] = (uuid_bytes[6] & 0x0F) | 0x40  # version 4
            uuid_bytes[8] = (uuid_bytes[8] & 0x3F) | 0x80  # variant RFC 4122
            row: dict[str, object] = {
                "complaint_id": str(uuid.UUID(bytes=bytes(uuid_bytes))),
                "complaint_text": text,
                "source": str(rng.choice(SOURCES)),
                "region": region,
                "product_sku": str(rng.choice(PRODUCT_SKUS)),
                "created_at": _generate_timestamp(rng, category, region, now),
                "category": category,
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    # Deterministic shuffle so categories are interleaved
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df


def _save(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic HVAC complaints.")
    parser.add_argument("--n", type=int, default=500, help="Number of complaints to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "generated" / "complaints_500.csv",
    )
    args = parser.parse_args()

    df = generate_complaints(n=args.n, seed=args.seed)
    _save(df, args.output)

    distribution = df["category"].value_counts().sort_index().to_dict()
    delhi_compressor = df[
        (df["category"] == "compressor_noise") & (df["region"] == "Delhi")
    ]
    last_7d = delhi_compressor[
        delhi_compressor["created_at"]
        >= datetime.now(tz=timezone.utc) - timedelta(days=7)
    ]
    delhi_recent = (
        f"{len(last_7d)}/{len(delhi_compressor)}"
        if len(delhi_compressor)
        else "0/0"
    )

    logger.info(
        "synthetic_complaints_generated",
        count=len(df),
        output=str(args.output),
        distribution={str(k): int(v) for k, v in distribution.items()},
        delhi_compressor_last_7d=delhi_recent,
    )


if __name__ == "__main__":
    main()
