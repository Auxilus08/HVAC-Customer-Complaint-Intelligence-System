"""Seed the products table with a curated set of real Carrier HVAC products.

Covers Carrier's mainstream residential families (Infinity / Performance /
Comfort), heat pumps, ductless mini-splits, packaged rooftops, and a small
slice of light-commercial offerings. Each row includes common_issues that
feed both the LLM product-match prompt and the AI-resolvable suggestion
path on the support bot.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-12
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PRODUCTS: list[dict] = [
    # ── Infinity series (premium residential) ─────────────────────────────────
    {
        "sku": "24ANB1",
        "family": "Infinity",
        "model_name": "Infinity 19VS Variable-Speed Central AC",
        "category": "Central Split AC",
        "tonnage": "2.0-5.0",
        "seer_rating": 19.0,
        "description": (
            "Two-stage Puron refrigerant compressor with variable-speed fan; "
            "pairs with Infinity touch control."
        ),
        "common_issues": [
            {
                "symptom": "Outdoor unit running but no cool air indoors",
                "resolution_tip": (
                    "Check the indoor air handler breaker, replace the air filter, "
                    "and verify the thermostat is set to COOL with fan AUTO."
                ),
            },
            {
                "symptom": "Infinity touch control shows 'communication fault'",
                "resolution_tip": (
                    "Power-cycle the unit at the breaker for 60 seconds. If the "
                    "fault persists after restart, the ABCD wiring between the "
                    "indoor and outdoor unit needs to be inspected by a technician."
                ),
            },
            {
                "symptom": "Outdoor unit iced over",
                "resolution_tip": (
                    "Turn the system off and let it thaw for 1-2 hours. Replace a "
                    "dirty filter and clear any blocked return vents. Persistent "
                    "icing indicates low refrigerant — that needs a tech."
                ),
            },
        ],
    },
    {
        "sku": "24VNA0",
        "family": "Infinity",
        "model_name": "Infinity 26 Variable-Speed Central AC",
        "category": "Central Split AC",
        "tonnage": "2.0-5.0",
        "seer_rating": 26.0,
        "description": "Top-tier residential AC with Greenspeed Intelligence.",
        "common_issues": [
            {
                "symptom": "Compressor cycling on and off rapidly",
                "resolution_tip": (
                    "Short-cycling usually means a clogged filter or blocked "
                    "outdoor coil. Replace the filter and rinse the outdoor coil "
                    "with a garden hose (power off first)."
                ),
            },
            {
                "symptom": "High humidity indoors even when running",
                "resolution_tip": (
                    "Lower the indoor fan speed in the Infinity control's comfort "
                    "menu; this lets the coil run colder and pull more moisture."
                ),
            },
        ],
    },
    {
        "sku": "25VNA8",
        "family": "Infinity",
        "model_name": "Infinity 24 Heat Pump",
        "category": "Heat Pump",
        "tonnage": "2.0-5.0",
        "seer_rating": 24.0,
        "description": (
            "Variable-speed heat pump for year-round comfort, 24 SEER2 / 10 HSPF2."
        ),
        "common_issues": [
            {
                "symptom": "Heat pump blowing cold air in heating mode",
                "resolution_tip": (
                    "The unit may be in defrost cycle — wait 10-15 minutes. If it "
                    "persists, check that the reversing valve solenoid is wired and "
                    "the auxiliary electric heat strip is enabled at the thermostat."
                ),
            },
            {
                "symptom": "Unit runs continuously below 30°F",
                "resolution_tip": (
                    "This is expected behavior — heat pumps run longer at low "
                    "temperatures. Make sure auxiliary heat lockout is set "
                    "correctly (typically 25-35°F) in the thermostat config."
                ),
            },
        ],
    },
    {
        "sku": "25VNA4",
        "family": "Infinity",
        "model_name": "Infinity 20 Heat Pump",
        "category": "Heat Pump",
        "tonnage": "2.0-5.0",
        "seer_rating": 20.0,
        "description": "Two-stage scroll compressor heat pump with Puron refrigerant.",
        "common_issues": [
            {
                "symptom": "Ice on outdoor coil during winter",
                "resolution_tip": (
                    "Light frost is normal; thick ice means the defrost board needs "
                    "service. Confirm the defrost thermostat clip is firmly attached "
                    "to the suction line near the reversing valve."
                ),
            },
        ],
    },
    {
        "sku": "59TN6",
        "family": "Infinity",
        "model_name": "Infinity 98 Gas Furnace",
        "category": "Gas Furnace",
        "tonnage": "60k-120k BTU",
        "seer_rating": None,
        "description": "98.5% AFUE modulating gas furnace with variable-speed blower.",
        "common_issues": [
            {
                "symptom": "Furnace LED flashes 3 times",
                "resolution_tip": (
                    "Three flashes = pressure switch fault. Check that the vent and "
                    "intake PVC pipes are clear of debris, and the condensate drain "
                    "is not clogged."
                ),
            },
            {
                "symptom": "Furnace short-cycles on cold mornings",
                "resolution_tip": (
                    "Replace the filter and check the flame sensor — a dirty sensor "
                    "is the most common cause of short cycling in 90+ AFUE furnaces. "
                    "Clean gently with fine sandpaper if you're comfortable doing so."
                ),
            },
        ],
    },
    # ── Performance series (mid-tier) ─────────────────────────────────────────
    {
        "sku": "24ACC6",
        "family": "Performance",
        "model_name": "Performance 17 Central AC",
        "category": "Central Split AC",
        "tonnage": "1.5-5.0",
        "seer_rating": 17.0,
        "description": "Two-stage Puron compressor, ENERGY STAR qualified.",
        "common_issues": [
            {
                "symptom": "Outdoor fan not spinning",
                "resolution_tip": (
                    "Power off at the breaker. If the fan blade spins freely by "
                    "hand, the capacitor is likely failed — that's a $15 part but "
                    "should be replaced by a licensed tech."
                ),
            },
            {
                "symptom": "Hissing or bubbling sound near indoor coil",
                "resolution_tip": (
                    "Indicates refrigerant leak. Shut down the system immediately "
                    "and schedule service — running with low refrigerant damages "
                    "the compressor."
                ),
            },
        ],
    },
    {
        "sku": "24ACB7",
        "family": "Performance",
        "model_name": "Performance 16 Compact Central AC",
        "category": "Central Split AC",
        "tonnage": "1.5-5.0",
        "seer_rating": 16.0,
        "description": "Single-stage scroll compressor, compact cabinet for tight installations.",
        "common_issues": [
            {
                "symptom": "Water leaking from indoor air handler",
                "resolution_tip": (
                    "The condensate drain line is clogged. Pour 1 cup of distilled "
                    "white vinegar into the drain access tee, wait 30 minutes, then "
                    "flush with warm water."
                ),
            },
        ],
    },
    {
        "sku": "25HCC5",
        "family": "Performance",
        "model_name": "Performance 17 Heat Pump",
        "category": "Heat Pump",
        "tonnage": "1.5-5.0",
        "seer_rating": 17.0,
        "description": "Two-stage Puron heat pump for moderate climates.",
        "common_issues": [
            {
                "symptom": "Emergency heat keeps turning on",
                "resolution_tip": (
                    "Check the outdoor sensor wiring and confirm the balance point "
                    "in the thermostat is set above your current outdoor temp. "
                    "Compressor lockout below balance point is normal."
                ),
            },
        ],
    },
    {
        "sku": "59TP6",
        "family": "Performance",
        "model_name": "Performance 96 Gas Furnace",
        "category": "Gas Furnace",
        "tonnage": "40k-120k BTU",
        "seer_rating": None,
        "description": "96.7% AFUE two-stage gas furnace.",
        "common_issues": [
            {
                "symptom": "Furnace won't ignite",
                "resolution_tip": (
                    "Confirm the gas valve is open and the thermostat is calling for "
                    "heat. If you hear the inducer motor run but no ignition, the "
                    "hot-surface igniter is likely cracked — visible inspection."
                ),
            },
        ],
    },
    # ── Comfort series (entry-level residential) ──────────────────────────────
    {
        "sku": "24ABC6",
        "family": "Comfort",
        "model_name": "Comfort 16 Central AC",
        "category": "Central Split AC",
        "tonnage": "1.5-5.0",
        "seer_rating": 16.0,
        "description": "Entry-level single-stage AC, Puron refrigerant.",
        "common_issues": [
            {
                "symptom": "AC running but house not cooling below 78°F",
                "resolution_tip": (
                    "On a 95°F+ day, a 20°F differential is the limit for most "
                    "single-stage units. Replace filter, clean outdoor coil, and "
                    "close blinds on sun-facing windows."
                ),
            },
            {
                "symptom": "Loud humming from outdoor unit at startup",
                "resolution_tip": (
                    "Likely a weak start capacitor. The unit will continue working "
                    "but should be serviced soon — replacement is $20-40 in parts."
                ),
            },
        ],
    },
    {
        "sku": "24ACA4",
        "family": "Comfort",
        "model_name": "Comfort 13 Central AC",
        "category": "Central Split AC",
        "tonnage": "1.5-5.0",
        "seer_rating": 13.0,
        "description": "Budget single-stage AC, legacy R-22 / Puron variants.",
        "common_issues": [
            {
                "symptom": "Old unit (10+ years), losing cooling efficiency",
                "resolution_tip": (
                    "R-22 units past 10-12 years often have refrigerant degradation. "
                    "Replacement is usually more cost-effective than recharge given "
                    "R-22 phase-out pricing."
                ),
            },
        ],
    },
    {
        "sku": "25HCB5",
        "family": "Comfort",
        "model_name": "Comfort 15 Heat Pump",
        "category": "Heat Pump",
        "tonnage": "1.5-5.0",
        "seer_rating": 15.0,
        "description": "Entry-level single-stage heat pump.",
        "common_issues": [
            {
                "symptom": "Outdoor unit makes loud banging in defrost",
                "resolution_tip": (
                    "Some thump from the reversing valve is normal at the start of "
                    "defrost cycles. Persistent loud banging means a worn compressor "
                    "mount — schedule service."
                ),
            },
        ],
    },
    {
        "sku": "59SC2",
        "family": "Comfort",
        "model_name": "Comfort 80 Gas Furnace",
        "category": "Gas Furnace",
        "tonnage": "45k-155k BTU",
        "seer_rating": None,
        "description": "80% AFUE single-stage gas furnace.",
        "common_issues": [
            {
                "symptom": "Pilot light won't stay lit",
                "resolution_tip": (
                    "Modern Comfort 80 models use hot-surface ignition, not a pilot. "
                    "If you're seeing a pilot-like flame go out, you may have an "
                    "older model — confirm the thermocouple is seated in the flame."
                ),
            },
        ],
    },
    # ── Ductless mini-splits ──────────────────────────────────────────────────
    {
        "sku": "38MAQB",
        "family": "Comfort",
        "model_name": "Performance Ductless High-Wall Inverter Mini-Split",
        "category": "Ductless Mini-Split",
        "tonnage": "0.75-1.5",
        "seer_rating": 22.0,
        "description": "Single-zone wall-mount with inverter compressor.",
        "common_issues": [
            {
                "symptom": "Indoor head dripping water onto floor",
                "resolution_tip": (
                    "The condensate drain line on the wall behind the unit is "
                    "clogged. Suction the drain end (often outside) with a wet/dry "
                    "vacuum for 30 seconds."
                ),
            },
            {
                "symptom": "Remote shows E1 or E5 error",
                "resolution_tip": (
                    "E1 = indoor coil sensor fault, E5 = outdoor coil sensor. Both "
                    "require a tech with replacement thermistors — DIY not "
                    "recommended."
                ),
            },
        ],
    },
    {
        "sku": "38MGRQ",
        "family": "Performance",
        "model_name": "Performance Multi-Zone Ductless Outdoor Unit",
        "category": "Ductless Mini-Split",
        "tonnage": "2.0-4.0",
        "seer_rating": 21.5,
        "description": "Supports 2-5 indoor zones via single outdoor condenser.",
        "common_issues": [
            {
                "symptom": "One zone not cooling while others work fine",
                "resolution_tip": (
                    "Check the indoor unit's air filter (sliding panel above the "
                    "front grille). If filter is clean, the electronic expansion "
                    "valve for that zone may be stuck — needs a tech."
                ),
            },
        ],
    },
    {
        "sku": "40MAQB",
        "family": "Comfort",
        "model_name": "Comfort Ductless Cassette",
        "category": "Ductless Mini-Split",
        "tonnage": "1.0-2.0",
        "seer_rating": 19.0,
        "description": "4-way ceiling cassette for ductless retrofits.",
        "common_issues": [
            {
                "symptom": "Ceiling cassette louvers stuck in one position",
                "resolution_tip": (
                    "Try a full remote-reset: hold power for 10 seconds. If louvers "
                    "still don't sweep, the swing motor below the cassette face "
                    "needs replacement."
                ),
            },
        ],
    },
    # ── Packaged / rooftop units ──────────────────────────────────────────────
    {
        "sku": "50TCQ",
        "family": "Carrier Light Commercial",
        "model_name": "Single-Packaged Rooftop Gas/Electric WeatherMaker",
        "category": "Packaged Rooftop",
        "tonnage": "3.0-12.5",
        "seer_rating": 14.0,
        "description": "Single-package gas heat / electric cool for light commercial.",
        "common_issues": [
            {
                "symptom": "Rooftop unit not cooling after thunderstorm",
                "resolution_tip": (
                    "Lightning surges can trip the high-pressure switch. Reset by "
                    "cycling the disconnect at the unit; if it trips again within "
                    "5 minutes, the condenser fan or coil is the issue."
                ),
            },
        ],
    },
    {
        "sku": "48TCE",
        "family": "Carrier Light Commercial",
        "model_name": "WeatherMaker 48TC High-Efficiency Rooftop",
        "category": "Packaged Rooftop",
        "tonnage": "3.0-12.5",
        "seer_rating": 16.0,
        "description": "Electric cool / gas heat rooftop with two-stage compressor.",
        "common_issues": [
            {
                "symptom": "Economizer dampers not opening on cool days",
                "resolution_tip": (
                    "Check the outdoor air sensor (mounted on the economizer hood) "
                    "for wiring damage from rodents — a common rooftop issue. "
                    "Replace if signal is open-circuit."
                ),
            },
        ],
    },
    {
        "sku": "50ZHC",
        "family": "Carrier Light Commercial",
        "model_name": "WeatherMaker 50ZHC Heat Pump Rooftop",
        "category": "Packaged Heat Pump",
        "tonnage": "3.0-25.0",
        "seer_rating": 15.0,
        "description": "Packaged heat pump for retail and light commercial.",
        "common_issues": [
            {
                "symptom": "Heat pump rooftop running on emergency heat constantly",
                "resolution_tip": (
                    "Outdoor coil is likely iced over from a failed defrost board "
                    "or stuck reversing valve. Manual defrost + service call needed."
                ),
            },
        ],
    },
    # ── Air handlers & evaporator coils ───────────────────────────────────────
    {
        "sku": "FE4A",
        "family": "Performance",
        "model_name": "Performance Air Handler with Puron Coil",
        "category": "Air Handler",
        "tonnage": "1.5-5.0",
        "seer_rating": None,
        "description": "Variable-speed ECM blower air handler.",
        "common_issues": [
            {
                "symptom": "Air handler blower won't start",
                "resolution_tip": (
                    "Check the float switch on the secondary drain pan — if it's "
                    "tripped (water present), the blower is interlocked off. Clear "
                    "the drain and reset."
                ),
            },
        ],
    },
    {
        "sku": "FV4C",
        "family": "Infinity",
        "model_name": "Infinity Fan Coil",
        "category": "Air Handler",
        "tonnage": "2.0-5.0",
        "seer_rating": None,
        "description": "Communicating variable-speed fan coil for Infinity systems.",
        "common_issues": [
            {
                "symptom": "Blower runs at high speed constantly",
                "resolution_tip": (
                    "In Infinity systems, the fan coil follows commands from the "
                    "outdoor unit. A stuck-high blower usually means a "
                    "communication wire is shorted — check ABCD terminals."
                ),
            },
        ],
    },
    # ── Geothermal ────────────────────────────────────────────────────────────
    {
        "sku": "GT-PX",
        "family": "Carrier Geothermal",
        "model_name": "Performance Geothermal Heat Pump",
        "category": "Geothermal Heat Pump",
        "tonnage": "2.0-6.0",
        "seer_rating": None,
        "description": "Two-stage water-source geothermal heat pump.",
        "common_issues": [
            {
                "symptom": "Geothermal loop pressure dropping over months",
                "resolution_tip": (
                    "Small loss over a season is normal due to air bleed; a fast "
                    "drop means a ground loop leak. Check the air separator and "
                    "purge valves first."
                ),
            },
        ],
    },
    # ── Thermostats / controls ────────────────────────────────────────────────
    {
        "sku": "SYSTXCCITC01",
        "family": "Infinity",
        "model_name": "Infinity Touch Control Thermostat",
        "category": "Smart Thermostat",
        "tonnage": None,
        "seer_rating": None,
        "description": "Color touchscreen control for Infinity communicating systems.",
        "common_issues": [
            {
                "symptom": "Touch control screen frozen or unresponsive",
                "resolution_tip": (
                    "Remove the control from its wall plate for 30 seconds to "
                    "perform a hard reset, then re-seat firmly. Screen should "
                    "reboot in 60 seconds."
                ),
            },
            {
                "symptom": "Wi-Fi keeps disconnecting from Infinity control",
                "resolution_tip": (
                    "Re-enter the Wi-Fi password under Menu → Wireless. If the "
                    "router is 5GHz-only, switch to a 2.4GHz SSID — the Infinity "
                    "control does not support 5GHz."
                ),
            },
        ],
    },
    {
        "sku": "TP-WEM01",
        "family": "Performance",
        "model_name": "Côr Wi-Fi Thermostat",
        "category": "Smart Thermostat",
        "tonnage": None,
        "seer_rating": None,
        "description": "Wi-Fi thermostat for non-communicating Performance/Comfort systems.",
        "common_issues": [
            {
                "symptom": "Côr thermostat keeps rebooting",
                "resolution_tip": (
                    "Low voltage from the C wire is the most common cause. Confirm "
                    "the C wire is landed at both the thermostat and the air "
                    "handler control board."
                ),
            },
        ],
    },
    # ── Indoor air quality ────────────────────────────────────────────────────
    {
        "sku": "GAPAA",
        "family": "Infinity",
        "model_name": "Infinity Air Purifier",
        "category": "Air Purifier",
        "tonnage": None,
        "seer_rating": None,
        "description": "MERV 15 cabinet-mount air purifier with Captures & Kills tech.",
        "common_issues": [
            {
                "symptom": "Air purifier indicator LED off",
                "resolution_tip": (
                    "Check the 24V power wire from the air handler. If powered, "
                    "the precipitator cell may need cleaning — pull and rinse with "
                    "warm soapy water."
                ),
            },
        ],
    },
    {
        "sku": "HUMCRSBP",
        "family": "Performance",
        "model_name": "Performance Bypass Humidifier",
        "category": "Humidifier",
        "tonnage": None,
        "seer_rating": None,
        "description": "Bypass-style whole-home humidifier mounted on return duct.",
        "common_issues": [
            {
                "symptom": "Humidifier not adding moisture in winter",
                "resolution_tip": (
                    "Replace the water panel (evaporator pad) — it's a yearly "
                    "consumable. Confirm the saddle valve on the cold-water line "
                    "is open and the solenoid is energizing during furnace runs."
                ),
            },
        ],
    },
    # ── Boilers ───────────────────────────────────────────────────────────────
    {
        "sku": "BWMA",
        "family": "Carrier Hydronic",
        "model_name": "Performance Modulating Condensing Gas Boiler",
        "category": "Gas Boiler",
        "tonnage": "80k-200k BTU",
        "seer_rating": None,
        "description": "95% AFUE modulating gas boiler for hydronic systems.",
        "common_issues": [
            {
                "symptom": "Boiler displaying L7 lockout error",
                "resolution_tip": (
                    "L7 = ignition lockout. Cycle power for 60 seconds; if it "
                    "recurs, the gas pressure may be low or the ignition lead may "
                    "be cracked. Tech recommended."
                ),
            },
        ],
    },
    # ── Mini VRF ──────────────────────────────────────────────────────────────
    {
        "sku": "40VMA",
        "family": "Toshiba-Carrier VRF",
        "model_name": "VRF Mini Heat Recovery System",
        "category": "VRF System",
        "tonnage": "3.0-10.0",
        "seer_rating": 20.0,
        "description": "Variable refrigerant flow for multi-zone commercial spaces.",
        "common_issues": [
            {
                "symptom": "Multiple indoor units showing F23 error",
                "resolution_tip": (
                    "F23 = communication error between outdoor and branch box. "
                    "Power cycle the entire system from the main disconnect; if "
                    "the error persists, transmission wiring needs inspection."
                ),
            },
        ],
    },
    # ── Light commercial split AC ─────────────────────────────────────────────
    {
        "sku": "38AUZ",
        "family": "Carrier Light Commercial",
        "model_name": "Commercial Split System Condenser",
        "category": "Commercial Split AC",
        "tonnage": "6.0-12.5",
        "seer_rating": 14.5,
        "description": "Light commercial outdoor condensing unit.",
        "common_issues": [
            {
                "symptom": "Compressor trips on high pressure during peak hours",
                "resolution_tip": (
                    "Outdoor coil needs cleaning — restaurants and retail spaces "
                    "build up grease/dust quickly. Use coil cleaner and rinse "
                    "outward from the inside of the cabinet."
                ),
            },
        ],
    },
]


def _table_for_insert() -> sa.Table:
    """Construct a lightweight Table reference matching the products schema."""
    return sa.table(
        "products",
        sa.column("sku", sa.String),
        sa.column("family", sa.String),
        sa.column("model_name", sa.String),
        sa.column("category", sa.String),
        sa.column("tonnage", sa.String),
        sa.column("seer_rating", sa.Float),
        sa.column("description", sa.Text),
        sa.column("common_issues", sa.JSON),
    )


def upgrade() -> None:
    rows = []
    for p in _PRODUCTS:
        rows.append(
            {
                "sku": p["sku"],
                "family": p.get("family"),
                "model_name": p["model_name"],
                "category": p.get("category"),
                "tonnage": p.get("tonnage"),
                "seer_rating": p.get("seer_rating"),
                "description": p.get("description"),
                # SQLAlchemy JSON binds serialize automatically for most backends,
                # but going through json.dumps avoids surprises with bulk_insert.
                "common_issues": json.dumps(p.get("common_issues") or []),
            }
        )
    op.bulk_insert(_table_for_insert(), rows)


def downgrade() -> None:
    skus = "', '".join(p["sku"] for p in _PRODUCTS)
    op.execute(f"DELETE FROM products WHERE sku IN ('{skus}')")
