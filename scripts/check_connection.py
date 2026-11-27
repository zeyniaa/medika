"""Safe connection diagnostic: model identifiers only, never URLs or keys."""
import json
from medika.config import Settings
from medika.provider import BaselineProvider, ProviderError

p = BaselineProvider(Settings.load())
try:
    body = p._request("GET", "/models").json()
    print(json.dumps({"response_type": type(body).__name__, "keys": list(body) if isinstance(body, dict) else None}))
    if isinstance(body, dict):
        for key in ("data", "models"):
            entries = body.get(key)
            if isinstance(entries, list):
                print(json.dumps({"field": key, "models": [{k: v for k, v in entry.items() if k in {"id", "name", "model", "object"}} if isinstance(entry, dict) else str(entry)[:150] for entry in entries]}, ensure_ascii=False))
            elif isinstance(entries, dict):
                print(json.dumps({"field": key, "keys": list(entries)}))
except ProviderError as exc:
    print(json.dumps({"error": str(exc)}))
