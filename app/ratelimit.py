"""In-memory rate limiter per IP address."""

import time
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from app.config import RATE_LIMIT_CORE_PER_MINUTE, RATE_LIMIT_AI_PER_HOUR

# Storage: dict mapping (ip, limit_type) -> list of timestamp floats
_REQUEST_TIMESTAMPS: Dict[Tuple[str, str], List[float]] = defaultdict(list)


def check_rate_limit(ip: str, limit_type: str = "core") -> Tuple[bool, Optional[int]]:
    """
    Check if IP has exceeded the allowed rate limit.
    limit_type: 'core' (30/min) or 'ai' (10/hr)
    Returns: (allowed: bool, retry_after_seconds: Optional[int])
    """
    now = time.time()
    key = (ip, limit_type)
    timestamps = _REQUEST_TIMESTAMPS[key]

    if limit_type == "ai":
        window_seconds = 3600
        max_requests = RATE_LIMIT_AI_PER_HOUR
    else:
        window_seconds = 60
        max_requests = RATE_LIMIT_CORE_PER_MINUTE

    # Prune old timestamps
    cutoff = now - window_seconds
    valid_timestamps = [t for t in timestamps if t > cutoff]
    _REQUEST_TIMESTAMPS[key] = valid_timestamps

    if len(valid_timestamps) >= max_requests:
        oldest_in_window = valid_timestamps[0]
        retry_after = max(1, int(oldest_in_window + window_seconds - now))
        return False, retry_after

    valid_timestamps.append(now)
    return True, None


def reset_rate_limits() -> None:
    """Reset rate limiter store (used in testing)."""
    _REQUEST_TIMESTAMPS.clear()
