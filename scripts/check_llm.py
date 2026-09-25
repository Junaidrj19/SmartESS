#!/usr/bin/env python3
"""Minimal real-model connectivity check for the M9 LLM layer.

Usage:
    python3 scripts/check_llm.py

Verifies, using the *existing* M9 LLM abstraction (no architecture change):

1. the endpoint is reachable and authentication succeeds
2. the configured model responds to a chat completion
3. a response can be parsed into a Pydantic model via structured_completion
4. malformed output is rejected rather than silently accepted

Only safe metadata is printed: provider, model, endpoint host, request status and
parse status. The API key is never printed, logged or written to disk.

Exit codes: 0 = real inference verified, 2 = not configured (mock fallback),
3 = connectivity/parsing failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel

from backend.agents.investigation.models.hypothesis import Hypothesis
from backend.llm.factory import create_llm_client
from backend.llm.interface import LLMMessage
from backend.llm.providers.experiential import ExperientialClient
from backend.llm.settings import LLMSettings, is_production_env


class ConnectivityProbe(BaseModel):
    status: str
    model_family: str = ""


def main() -> int:
    settings = LLMSettings()
    print(f"provider: {settings.provider or '(none)'}")
    print(f"model: {settings.model or '(none)'}")
    print(f"endpoint host: {settings.endpoint_host or '(none)'}")
    print(f"api key: {'present (not displayed)' if settings.api_key else 'absent'}")

    if not settings.configured:
        if is_production_env():
            print("RESULT: NOT_CONFIGURED — production refuses mock inference")
        else:
            print("RESULT: NOT_CONFIGURED — development falls back to MockLLMClient")
        return 2

    client = create_llm_client(settings)
    print(f"client: {type(client).__name__} provider_name={client.provider_name}")

    # 1+2: reachability, authentication and a plain completion.
    try:
        response = client.chat_completion(
            [LLMMessage(role="user", content="Reply with the single word: ok")],
            temperature=0.0,
            max_tokens=64,
        )
    except Exception as e:
        print(f"chat_completion: FAILED ({type(e).__name__})")
        print(f"RESULT: REQUEST_FAILED — {type(e).__name__}")
        return 3

    text = (response.content or "").strip()
    print(f"chat_completion: ok (finish_reason={response.finish_reason!r}, {len(text)} chars)")
    if "ok" not in text.lower():
        print(f"chat_completion content unexpected: {text[:80]!r}")

    # 3: structured output through the M9 abstraction.
    try:
        probe = client.structured_completion(
            [LLMMessage(role="user", content="Return the probe JSON with status set to ready.")],
            response_model=ConnectivityProbe,
            system="You are a JSON-only connectivity probe.",
            temperature=0.0,
            max_tokens=512,
        )
        print(f"structured_completion: ok (status={probe.status!r})")
    except Exception as e:
        print(f"structured_completion: FAILED ({type(e).__name__})")
        print("RESULT: STRUCTURED_OUTPUT_FAILED")
        return 3

    # 3b: can the real model satisfy the Hypothesis schema used by the agent?
    try:
        hypothesis = client.structured_completion(
            [
                LLMMessage(
                    role="user",
                    content=(
                        "deterministic_results: []\n"
                        "evidence_records:\n"
                        '{"evidence_id": "ev-probe-1", "title": "probe", "text": '
                        '"RDS(on) drift can be influenced by temperature and package degradation."}\n'
                        "Produce a Hypothesis JSON for module_id 'probe-module'. If the evidence does not "
                        "discriminate a mechanism, say so with status INSUFFICIENT_EVIDENCE."
                    ),
                )
            ],
            response_model=Hypothesis,
            system=(
                "You are the hypothesis agent of a SiC MOSFET reliability investigation. Never claim a "
                "confirmed physical failure, cite only the evidence ids provided, and keep mechanisms at "
                "candidate status."
            ),
            temperature=0.0,
            max_tokens=1200,
        )
        cited = {eid for c in hypothesis.candidates for eid in c.supporting_evidence_ids}
        unknown = sorted(cited - {"ev-probe-1"})
        print(
            f"hypothesis_schema: ok (module_id={hypothesis.module_id!r}, "
            f"candidates={len(hypothesis.candidates)}, unknown_citations={unknown})"
        )
    except Exception as e:
        print(f"hypothesis_schema: FAILED ({type(e).__name__})")
        print("RESULT: STRUCTURED_OUTPUT_FAILED")
        return 3

    # 4: malformed output handling stays functional.
    try:
        ExperientialClient._extract_json("this is not json")
    except json.JSONDecodeError:
        print("malformed_output_handling: ok (rejected)")
    else:
        print("malformed_output_handling: FAILED (garbage accepted)")
        return 3

    print("RESULT: REAL_INFERENCE_VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
