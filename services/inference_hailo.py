from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
from typing import Any, Callable

import config
from services.inference_common import InferenceError

logger = logging.getLogger(__name__)

_assess_callable: Callable[..., Any] | None = None
_chat_callable: Callable[..., Any] | None = None


def _resolve_callable(module: Any, callable_path: str) -> Callable[..., Any]:
    target: Any = module
    for part in callable_path.split("."):
        if not hasattr(target, part):
            raise InferenceError(
                f"Hailo callable '{callable_path}' not found in module '{config.HAILO_MODULE}'"
            )
        target = getattr(target, part)
    if not callable(target):
        raise InferenceError(
            f"Hailo target '{callable_path}' is not callable in module '{config.HAILO_MODULE}'"
        )
    return target


async def _invoke(func: Callable[..., Any], **kwargs) -> Any:
    try:
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)  # type: ignore[misc]
        return await asyncio.to_thread(func, **kwargs)
    except TypeError as exc:
        raise InferenceError(
            f"Hailo callable invocation failed. Check function signature. Details: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise InferenceError(f"Hailo backend call failed: {exc}") from exc


def init_backend() -> None:
    global _assess_callable, _chat_callable  # noqa: PLW0603
    if _assess_callable is not None and _chat_callable is not None:
        return

    if not config.HAILO_MODULE:
        raise InferenceError(
            "HAILO_MODULE is required for Hailo inference "
            "(example: export HAILO_MODULE='my_hailo_bridge')"
        )

    module = importlib.import_module(config.HAILO_MODULE)
    _assess_callable = _resolve_callable(module, config.HAILO_ASSESS_CALLABLE)
    _chat_callable = _resolve_callable(module, config.HAILO_CHAT_CALLABLE)
    logger.info(
        "Hailo backend initialised (module=%s, assess=%s, chat=%s)",
        config.HAILO_MODULE,
        config.HAILO_ASSESS_CALLABLE,
        config.HAILO_CHAT_CALLABLE,
    )


async def shutdown_backend() -> None:
    # Bridge callables may manage persistent contexts externally.
    logger.info("Hailo backend shut down")


async def assess_raw(image_base64: str) -> str:
    if _assess_callable is None:
        raise RuntimeError("Hailo backend not initialised — call init_backend() at startup")
    result = await _invoke(
        _assess_callable,
        image_base64=image_base64,
        prompt=config.TRIAGE_PROMPT,
        model=config.VLM_MODEL,
        few_shot_examples=config.FEW_SHOT_EXAMPLES,
    )
    if not isinstance(result, str):
        raise InferenceError(
            "Hailo assess callable must return a string response in triage format"
        )
    return result


async def chat_raw(image_base64: str, question: str, history: list[dict]) -> str:
    if _chat_callable is None:
        raise RuntimeError("Hailo backend not initialised — call init_backend() at startup")
    result = await _invoke(
        _chat_callable,
        image_base64=image_base64,
        question=question,
        history=history,
        system_prompt=config.CHAT_SYSTEM_PROMPT,
        model=config.VLM_MODEL,
    )
    if not isinstance(result, str):
        raise InferenceError("Hailo chat callable must return a string answer")
    return result
