"""Provider-agnostic extraction, so the model is a measured choice not a default.

Everything that carries the scientific weight of this pipeline -- the schema, the
prompt, the geocoder, the validation design -- is provider-independent. Only the
call itself differs. This module isolates that difference so you can run the same
dev set through two providers and pick the winner on evidence.

The one real engineering difference between them is schema enforcement:

  Anthropic  `output_config.format` constrains generation against the JSON
             schema. Output that validates is the normal case.
  DeepSeek   OpenAI-compatible JSON mode guarantees *valid JSON*, not JSON
             matching your schema. Wrong enum values and missing fields are
             expected at some rate, so the adapter retries on validation
             failure and reports how often it had to.

That retry rate is not a nuisance metric -- it is part of the cost comparison. A
provider that is 4x cheaper per token but needs 1.3 attempts per document is
3x cheaper in practice, and if the failures correlate with the hard documents
(the ambiguous-species ones) then it is worse in a way a price table will not
show you. `ProviderStats.schema_retry_rate` is what makes that visible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from .extract import SourceDocument, load_system_prompt, _user_content
from .schema import DocumentExtraction


@dataclass
class ProviderStats:
    """Accumulated across a run. Report these next to the accuracy numbers."""

    calls: int = 0
    schema_retries: int = 0
    hard_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def schema_retry_rate(self) -> float:
        return self.schema_retries / self.calls if self.calls else 0.0

    def summary(self) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "schema_retry_rate": round(self.schema_retry_rate, 3),
            "hard_failures": self.hard_failures,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class ExtractionProvider(Protocol):
    name: str
    stats: ProviderStats

    def extract(self, doc: SourceDocument) -> DocumentExtraction | None:
        """Return the extraction, or None if the provider could not produce
        schema-valid output within its retry budget."""
        ...


# --------------------------------------------------------------------------


class AnthropicProvider:
    """Claude via the Anthropic SDK. Schema is enforced during generation."""

    def __init__(self, client, model: str = "claude-haiku-4-5") -> None:
        self.client = client
        self.model = model
        self.name = f"anthropic:{model}"
        self.stats = ProviderStats()

    def extract(self, doc: SourceDocument) -> DocumentExtraction | None:
        from .extract import extract_document

        self.stats.calls += 1
        try:
            return extract_document(self.client, doc, model=self.model)
        except Exception:
            self.stats.hard_failures += 1
            return None


class DeepSeekProvider:
    """DeepSeek via its OpenAI-compatible endpoint.

    Requires the `openai` package and a DeepSeek API key. Model names and prices
    move -- check the current ones at platform.deepseek.com rather than trusting
    a table in a repo. As of writing the chat model is the general-purpose one
    and there is a separate reasoning model; for this task the chat model is the
    right starting point, since schema-constrained extraction is not a reasoning
    problem.

    Note DeepSeek's off-peak discount window (UTC) if you are cost-sensitive:
    a batch of a few thousand documents has no deadline, so scheduling the run
    into that window is free money in the same way the Anthropic batch discount
    is.
    """

    MAX_ATTEMPTS = 3

    def __init__(self, client, model: str = "deepseek-chat") -> None:
        self.client = client          # openai.OpenAI(base_url="https://api.deepseek.com", ...)
        self.model = model
        self.name = f"deepseek:{model}"
        self.stats = ProviderStats()

    def _schema_instruction(self) -> str:
        # JSON mode requires the word "json" to appear in the prompt, and since
        # the schema is not enforced during generation it has to be stated.
        return (
            "Respond with a single json object matching this schema exactly. "
            "Every enum field must use one of its listed values verbatim.\n\n"
            + json.dumps(DocumentExtraction.model_json_schema(), ensure_ascii=False)
        )

    def extract(self, doc: SourceDocument) -> DocumentExtraction | None:
        self.stats.calls += 1
        system = load_system_prompt() + "\n\n" + self._schema_instruction()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": _user_content(doc)},
        ]

        for attempt in range(self.MAX_ATTEMPTS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=8000,
                temperature=0,
            )
            usage = getattr(response, "usage", None)
            if usage:
                self.stats.input_tokens += usage.prompt_tokens or 0
                self.stats.output_tokens += usage.completion_tokens or 0

            text = response.choices[0].message.content or ""
            try:
                return DocumentExtraction.model_validate_json(text)
            except Exception as exc:
                if attempt + 1 < self.MAX_ATTEMPTS:
                    self.stats.schema_retries += 1
                    # Feed the validation error back; it is far more effective
                    # than simply resampling.
                    messages.append({"role": "assistant", "content": text})
                    messages.append({
                        "role": "user",
                        "content": f"That did not match the schema: {exc}. "
                                   f"Return corrected json only.",
                    })

        self.stats.hard_failures += 1
        return None
