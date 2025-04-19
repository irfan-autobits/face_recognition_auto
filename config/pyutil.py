import os

def get_env_bool(key: str, default: str = "true") -> bool:
    val = os.getenv(key, default)
    # if somebody ever passes a real bool into os.environ (unusual!), honor it
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes", "y")