"""Shared machinery for the chat plugin's classifiers.

A classifier here is one structured-output model call, not an agent: no tools, no reasoning
loop, no retries. What makes each one distinct is its system prompt, the two schemas it is
generic over — what it is asked to judge and the shape of the answer — and how it turns an input
into messages. Subclasses provide exactly those; this module owns the rest, so a classifier
module can be read for its judgement instead of its plumbing.

The model is never the user's chat model: classification is a few tokens and wants low
latency, so it runs on the smallest model of whichever provider the user already configured
for chat, under that same key. Which model that is, is the only provider-specific thing here —
the client is built by the lib facade, which every other caller in the codebase goes through.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from langchain_core.exceptions import LangChainException
from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from sparkth.lib.llm import get_provider
from sparkth.plugins.chat.exceptions import ClassifierError

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

# Smallest capable model per provider, keyed by the provider names an LLMConfig can carry.
SMALL_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-2.0-flash",
}


def small_model_for(provider_name: str) -> str:
    """Return the smallest classification model registered for ``provider_name``.

    Raises:
        ValueError: no small model is registered for that provider.
    """
    model = SMALL_MODELS.get(provider_name)
    if model is None:
        raise ValueError(f"Unsupported provider for classifier: {provider_name!r}")
    return model


class BaseClassifier(ABC, Generic[InputT, OutputT]):
    """One structured-output model call, with the plumbing every chat classifier shares.

    A subclass declares its prompt and its two schemas through ``__init__`` and implements
    ``_build_messages``. Everything the base then does is mechanical: validate, assemble,
    call, translate a failure. It reaches no verdict of its own and applies no fallback —
    what a failed classification means differs per classifier, so that choice stays with the
    subclass that owns it.
    """

    def __init__(
        self,
        system_prompt: str,
        output_schema: type[OutputT],
        provider_name: str,
        api_key: str,
    ) -> None:
        """Wire a classifier to the smallest model of the user's configured provider.

        Args:
            system_prompt: Sent as the leading message of every call.
            output_schema: The shape the answer comes back in. Handed to
                ``with_structured_output``, so it defines the answer format on its own —
                the prompt carries no format instruction — and enforced again on the answer
                itself, so a caller always receives an instance of it.
            provider_name: The provider the user chose for chat (``openai``, ``anthropic``
                or ``google``).
            api_key: The user's key for that provider.

        Raises:
            ValueError: the provider has no small model registered.
        """
        self.model = small_model_for(provider_name)
        self._system_prompt = system_prompt
        self._output_schema = output_schema
        # The lib facade owns provider-to-client construction for the whole codebase; a
        # classifier only chooses which model and at what temperature.
        llm = get_provider(provider_name, api_key, self.model, temperature=0).create_llm()
        self._chain = llm.with_structured_output(output_schema)

    @abstractmethod
    def _build_messages(self, payload: InputT) -> list[BaseMessage]:
        """Render a validated payload into the messages that follow the system prompt.

        This is where classifiers genuinely differ — one replays conversation turns, another
        summarises attachments — so the base supplies no default.
        """

    async def classify(self, payload: InputT) -> OutputT:
        """Classify ``payload`` and return the answer as this classifier's output schema.

        Taking the input schema itself rather than a mapping is what makes a call site checkable:
        a caller building the wrong shape is a type error, not a runtime one, and pydantic has
        already validated the values by the time the instance exists.

        Raises:
            ClassifierError: the model call failed, or its answer did not fit the output
                schema. The original failure is kept as the cause.
        """
        messages: list[BaseMessage] = [
            SystemMessage(content=self._system_prompt),
            *self._build_messages(payload),
        ]

        try:
            answer = await self._chain.ainvoke(messages)
            # Structured output usually parses the answer already; a raw mapping is validated,
            # not trusted.
            if isinstance(answer, self._output_schema):
                return answer
            return self._output_schema.model_validate(answer)
        except (LangChainException, ValidationError) as exc:
            raise ClassifierError(f"{type(self).__name__} failed on model {self.model}: {exc}") from exc
