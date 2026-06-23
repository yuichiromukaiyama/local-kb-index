from __future__ import annotations

import contextlib
import functools
import io
import logging
import os
import struct
import warnings
from typing import Iterable, Iterator

from .config import AppConfig
from .errors import KbError

# Hugging Face Hub / transformers の標準出力を抑制
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TQDM_DISABLE", "1")

# huggingface_hub / transformers / sentence-transformers の logger を抑制
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

# warning として出る場合の抑制
warnings.filterwarnings(
    "ignore",
    message=r".*unauthenticated requests to the HF Hub.*",
)
warnings.filterwarnings(
    "ignore",
    message=r".*Please set a HF_TOKEN.*",
)

try:
    from huggingface_hub.utils import disable_progress_bars

    disable_progress_bars()
except Exception:
    pass

_QUIET_ENV_DEFAULTS = {
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "TQDM_DISABLE": "1",
}

_NOISY_LOGGERS = (
    "huggingface_hub",
    "huggingface_hub.file_download",
    "sentence_transformers",
    "transformers",
    "torch",
)


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *[float(x) for x in vector])


def unpack_vector(blob: bytes) -> list[float]:
    if len(blob) % 4 != 0:
        raise ValueError("invalid vector blob length")
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


class EmbeddingProvider:
    def __init__(self, config: AppConfig):
        self.config = config
        self.model = _load_model(
            config.embedding.model,
            config.embedding.revision,
            config.embedding.local_files_only,
            config.embedding.device,
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            kwargs = {
                "batch_size": self.config.embedding.batch_size,
                "normalize_embeddings": self.config.embedding.normalize,
                "show_progress_bar": False,
            }
            with _quiet_external_output():
                arr = self.model.encode(texts, **kwargs)
            return [[float(v) for v in row] for row in arr]
        except Exception as exc:
            raise KbError(
                "KB004",
                f"failed to embed text with model {self.config.embedding.model}: {exc}",
                cause=exc,
            ) from exc

    def dimension(self) -> int:
        try:
            return int(self.model.get_embedding_dimension())
        except Exception:
            vec = self.encode(["dimension probe"])[0]
            return len(vec)


@functools.lru_cache(maxsize=8)
def _load_model(model_name: str, revision: str | None, local_files_only: bool, device: str | None):
    _configure_quiet_external_libraries()
    try:
        with _quiet_external_output():
            from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise KbError(
            "KB014", "sentence-transformers is required for embeddings", cause=exc
        ) from exc
    try:
        kwargs = {"local_files_only": local_files_only}
        if revision:
            kwargs["revision"] = revision
        if device:
            kwargs["device"] = device
        with _quiet_external_output():
            return SentenceTransformer(model_name, **kwargs)
    except Exception as exc:
        raise KbError(
            "KB004",
            f"model={model_name}, revision={revision}, local_files_only={local_files_only}: {exc}",
            cause=exc,
        ) from exc


def _configure_quiet_external_libraries() -> None:
    for key, value in _QUIET_ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    try:
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()
    except Exception:
        pass
    try:
        from transformers.utils import logging as transformers_logging

        transformers_logging.set_verbosity_error()
        transformers_logging.disable_progress_bar()
    except Exception:
        pass


@contextlib.contextmanager
def _quiet_external_output() -> Iterator[None]:
    """Suppress third-party warnings and progress bars emitted to stdout/stderr.

    The search tool is commonly consumed by Copilot/agent contexts where progress bars
    and hub warnings waste tokens and can corrupt JSON output. Set KB_VERBOSE_ML=1 to
    temporarily restore the raw third-party output during local debugging.
    """
    if os.environ.get("KB_VERBOSE_ML") == "1":
        yield
        return
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


def batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]
