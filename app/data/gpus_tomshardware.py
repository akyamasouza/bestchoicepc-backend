import re

# Source: user-provided Tom's Hardware 1080p Medium GPU hierarchy chart.
TOMSHARDWARE_GPU_1080P_MEDIUM_SCORES = {
    "geforce rtx 5090": 100.0,
    "geforce rtx 4090": 99.0,
    "geforce rtx 5080": 90.4,
    "geforce rtx 4080 super": 89.7,
    "geforce rtx 4080": 88.6,
    "radeon rx 7900 xtx": 88.1,
    "geforce rtx 5070 ti": 85.7,
    "radeon rx 9070 xt": 85.6,
    "radeon rx 7900 xt": 82.6,
    "geforce rtx 4070 ti super": 81.7,
    "radeon rx 9070": 80.6,
    "geforce rtx 4070 ti": 78.5,
    "geforce rtx 5070": 75.5,
    "geforce rtx 4070 super": 74.7,
    "radeon rx 7900 gre": 71.4,
    "radeon rx 7800 xt": 67.4,
    "geforce rtx 4070": 66.2,
    "geforce rtx 5060 ti 16gb": 60.9,
    "radeon rx 9060 xt 16gb": 59.6,
    "geforce rtx 5060 ti 8gb": 59.6,
    "radeon rx 7700 xt": 58.0,
    "geforce rtx 4060 ti 16gb": 52.3,
    "geforce rtx 4060 ti 8gb": 52.4,
    "geforce rtx 5060": 52.0,
    "radeon rx 7600 xt": 42.8,
    "geforce rtx 4060": 42.5,
    "intel arc b580": 40.5,
    "radeon rx 7600": 40.2,
    "intel arc b570": 36.6,
    "geforce rtx 3060 12gb": 35.5,
    "geforce rtx 3060": 35.5,
    "radeon rx 6600": 32.5,
    "intel arc a770 16gb": 32.1,
    "intel arc a750": 29.0,
    "intel arc a580": 27.7,
}


def normalize_gpu_name(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("(r)", "")
    normalized = normalized.replace("(tm)", "")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def resolve_tomshardware_gpu_1080p_medium_score(*candidates: str | None) -> float | None:
    for candidate in candidates:
        if not candidate:
            continue

        for alias in candidate.split(","):
            score = TOMSHARDWARE_GPU_1080P_MEDIUM_SCORES.get(normalize_gpu_name(alias))
            if score is not None:
                return score

    return None
