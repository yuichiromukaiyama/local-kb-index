from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any

SECRET_KEYS = {"password", "secret", "token", "key", "authorization", "apikey", "api_key"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in SECRET_KEYS):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class JsonLogger:
    def __init__(self, path: Path, redact_content: bool = True):
        self.path = path
        self.redact_content = redact_content
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, **payload: Any) -> None:
        data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "event": event,
            **payload,
        }
        if self.redact_content:
            data = redact(data)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")

    def exception(self, event: str, exc: Exception, **payload: Any) -> None:
        self.event(event, error=str(exc), traceback=traceback.format_exc(), **payload)


def command_logger(db_dir: Path, command: str, redact_content: bool = True) -> JsonLogger:
    return JsonLogger(db_dir / "logs" / f"{command}.log", redact_content=redact_content)
