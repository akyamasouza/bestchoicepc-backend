import re

# Source: user-provided TechPowerUp "Relative Performance - Applications" chart.
# Baseline example in the chart: Ryzen 7 9800X3D (Stock) = 100.0.
TECHPOWERUP_CPU_APPLICATION_SCORES = {
    "amd ryzen 9 9950x": 125.1,
    "intel core ultra 9 285k": 121.0,
    "amd ryzen 9 7950x": 120.9,
    "intel core i9 14900k": 119.5,
    "intel core i9 13900k": 116.6,
    "amd ryzen 9 7950x3d": 116.3,
    "intel core ultra 7 265k": 113.3,
    "amd ryzen 9 9900x": 112.0,
    "intel core i7 14700k": 110.2,
    "amd ryzen 9 7900x": 107.1,
    "intel core i7 13700k": 103.6,
    "amd ryzen 7 9800x3d": 100.0,
    "amd ryzen 9 7900": 98.5,
    "intel core ultra 5 245k": 95.6,
    "intel core i9 12900k": 95.6,
    "amd ryzen 7 9700x": 94.1,
    "intel core i5 14600k": 93.3,
    "amd ryzen 7 7700x": 90.7,
    "intel core i5 13600k": 89.5,
    "amd ryzen 9 5950x": 89.3,
    "amd ryzen 7 7700": 87.4,
    "intel core i7 12700k": 86.7,
    "amd ryzen 7 7800x3d": 85.1,
    "amd ryzen 5 9600x": 83.1,
    "amd ryzen 9 5900x": 82.0,
    "amd ryzen 5 7600x": 77.4,
    "intel core i5 12600k": 75.1,
    "amd ryzen 5 7600": 73.9,
    "intel core i9 11900k": 68.9,
    "amd ryzen 7 5800x": 68.3,
    "amd ryzen 7 5800x3d": 68.1,
    "amd ryzen 9 3900x": 67.9,
    "intel core i5 13400f": 67.6,
    "intel core i7 11700kf": 65.6,
    "amd ryzen 7 5700x": 64.9,
    "amd ryzen 7 5700g": 62.5,
    "amd ryzen 5 8500g": 60.8,
    "intel core i5 12400f": 58.4,
    "amd ryzen 5 5600x": 58.1,
    "intel core i5 11600k": 57.5,
    "amd ryzen 7 3700x": 56.1,
    "intel core i3 14100": 49.7,
    "amd ryzen 5 3600": 47.3,
    "intel core i3 12100f": 45.0,
    "intel core i5 11400f": 44.6,
    "amd ryzen 7 2700x": 43.6,
    "amd ryzen 3 3300x": 38.3,
}


def normalize_cpu_name(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("(r)", "")
    normalized = normalized.replace("(tm)", "")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^a-z0-9+]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def resolve_techpowerup_cpu_application_score(*candidates: str | None) -> float | None:
    for candidate in candidates:
        if not candidate:
            continue

        for alias in candidate.split(","):
            score = TECHPOWERUP_CPU_APPLICATION_SCORES.get(normalize_cpu_name(alias))
            if score is not None:
                return score

    return None
