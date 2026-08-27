"""Shared machinery for the chat plugin's classifiers.

A classifier here is one structured-output model call, not an agent: no tools, no reasoning
loop, no retries. What makes each one distinct is three declarations — the system prompt, the
input schema a payload must satisfy, and the output schema the answer comes back in — plus how
it turns a validated input into messages. Subclasses provide exactly those; this module owns
the rest, so a classifier module can be read for its judgement instead of its plumbing.

The model is never the user's chat model: classification is a few tokens and wants low
latency, so it runs on the smallest model of whichever provider the user already configured
for chat, under that same key.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.exceptions import LangChainException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr, ValidationError

from sparkth.plugins.chat.exceptions import ClassifierError, ClassifierInputError

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


def build_classifier_llm(provider_name: str, model: str, api_key: str) -> BaseChatModel:
    """Build ``provider_name``'s client for ``model``, at the temperature classification wants.

    Each client is constructed through its own field names — ``openai_api_key`` and ``model_name``
    for OpenAI, ``anthropic_api_key`` and ``model`` for Anthropic — rather than the ``api_key`` and
    ``model`` aliases their docs show. The aliases work at runtime but are absent from the
    ``__init__`` signatures pydantic generates, so reaching for them costs a type-ignore per call.

    Raises:
        ValueError: no client is wired here for that provider.
    """
    key = SecretStr(api_key)
    match provider_name:
        case "openai":
            return ChatOpenAI(openai_api_key=key, model_name=model, temperature=0)
        case "anthropic":
            return ChatAnthropic(anthropic_api_key=key, model=model, temperature=0)
        case "google":
            return ChatGoogleGenerativeAI(google_api_key=key, model=model, temperature=0)
    # Only if SMALL_MODELS gains a provider with no client above — a gap here, not bad input.
    raise ValueError(f"No client wired for provider {provider_name!r}")


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
        input_schema: type[InputT],
        output_schema: type[OutputT],
        provider_name: str,
        api_key: str,
    ) -> None:
        """Wire a classifier to the smallest model of the user's configured provider.

        Args:
            system_prompt: Sent as the leading message of every call.
            input_schema: What a payload must satisfy before the model is called.
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
        self._input_schema = input_schema
        self._output_schema = output_schema
        self._chain = build_classifier_llm(provider_name, self.model, api_key).with_structured_output(output_schema)

    @abstractmethod
    def _build_messages(self, payload: InputT) -> list[BaseMessage]:
        """Render a validated payload into the messages that follow the system prompt.

        This is where classifiers genuinely differ — one replays conversation turns, another
        summarises attachments — so the base supplies no default.
        """

    async def classify(self, payload: dict[str, object]) -> OutputT:
        """Classify ``payload`` and return the answer as this classifier's output schema.

        Raises:
            ClassifierInputError: ``payload`` does not satisfy the input schema. Raised
                before any model call, so a malformed call costs nothing.
            ClassifierError: the model call failed, or its answer did not fit the output
                schema. The original failure is kept as the cause.
        """
        try:
            validated = self._input_schema.model_validate(payload)
        except ValidationError as exc:
            raise ClassifierInputError(f"Payload does not satisfy {self._input_schema.__name__}: {exc}") from exc

        messages: list[BaseMessage] = [
            SystemMessage(content=self._system_prompt),
            *self._build_messages(validated),
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
