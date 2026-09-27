import os


def is_synthetic_mode() -> bool:
    """Use generated data only in development unless explicitly configured."""
    default_mode = "live" if os.getenv("APP_ENV", "development").lower() == "production" else "synthetic"
    mode = os.getenv("INGESTION_MODE", default_mode).lower()
    if mode not in {"synthetic", "live"}:
        raise RuntimeError("INGESTION_MODE must be either 'synthetic' or 'live'")
    return mode == "synthetic"


def synthetic_record_count(default: int = 100) -> int:
    """Return a bounded per-source synthetic batch size for local load testing."""
    try:
        count = int(os.getenv("SYNTHETIC_RECORD_COUNT", str(default)))
    except ValueError as exc:
        raise RuntimeError("SYNTHETIC_RECORD_COUNT must be an integer from 1 to 10000") from exc
    if not 1 <= count <= 10000:
        raise RuntimeError("SYNTHETIC_RECORD_COUNT must be between 1 and 10000")
    return count