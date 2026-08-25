"""Tests for the shared classifier base.

The base owns four things and decides nothing else: which model a provider gets, that a
payload satisfies the declared input schema before any model is called, that the system
prompt leads the messages a subclass built, and that a failed call reaches the subclass as
one exception type. Each is asserted here against a throwaway subclass, so the two real
classifiers can be read for what makes them different rather than for this plumbing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from sparkth.plugins.chat.classifiers.base import SMALL_MODELS, BaseClassifier, small_model_for
from sparkth.plugins.chat.exceptions import ClassifierError, ClassifierInputError

_SYSTEM_PROMPT = "Decide whether the colour is warm."

_PROVIDER_CLIENTS = {
    "openai": "sparkth.plugins.chat.classifiers.base.ChatOpenAI",
    "anthropic": "sparkth.plugins.chat.classifiers.base.ChatAnthropic",
    "google": "sparkth.plugins.chat.classifiers.base.ChatGoogleGenerativeAI",
}


class _ColourInput(BaseModel):
    colour: str


class _ColourVerdict(BaseModel):
    warm: bool


class _ColourClassifier(BaseClassifier[_ColourInput, _ColourVerdict]):
    """The smallest possible subclass: one human turn carrying the validated colour."""

    def __init__(self, provider_name: str = "anthropic", api_key: str = "test-key") -> None:
        super().__init__(_SYSTEM_PROMPT, _ColourInput, _ColourVerdict, provider_name, api_key)

    def _build_messages(self, payload: _ColourInput) -> list[BaseMessage]:
        return [HumanMessage(content=payload.colour)]


class _MessagelessClassifier(BaseClassifier[_ColourInput, _ColourVerdict]):
    """Implements nothing — used to prove the base will not render messages on a subclass's
    behalf."""


def _a_validation_error() -> ValidationError:
    """A real pydantic ValidationError, as structured output raises when a model's answer
    does not fit the schema. Constructed from the schema rather than hand-built so it stays
    the same error type the runtime would see."""
    with pytest.raises(ValidationError) as excinfo:
        _ColourVerdict.model_validate({})
    return excinfo.value


def _classifier_with(chain: MagicMock, provider_name: str = "anthropic") -> _ColourClassifier:
    """A classifier whose provider client is replaced by an LLM yielding ``chain``."""
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    with patch(_PROVIDER_CLIENTS[provider_name], return_value=llm):
        return _ColourClassifier(provider_name)


def _chain_returning(verdict: _ColourVerdict) -> MagicMock:
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=verdict)
    return chain


class TestModelSelection:
    """Whichever provider the user chose for chat, the classifier runs on its smallest model."""

    @pytest.mark.parametrize("provider_name", ["openai", "anthropic", "google"])
    def test_each_provider_gets_its_smallest_model_at_temperature_zero(self, provider_name: str) -> None:
        with patch(_PROVIDER_CLIENTS[provider_name]) as MockClient:
            _ColourClassifier(provider_name, "user-key")

        kwargs = MockClient.call_args.kwargs
        assert kwargs["model"] == SMALL_MODELS[provider_name]
        assert kwargs["temperature"] == 0

    def test_the_users_own_key_is_what_reaches_the_client(self) -> None:
        """The classifier has no key of its own — it rides on the one configured for chat."""
        with patch(_PROVIDER_CLIENTS["google"]) as MockClient:
            _ColourClassifier("google", "user-key")

        assert MockClient.call_args.kwargs["google_api_key"] == "user-key"

    def test_an_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported provider"):
            _ColourClassifier("cohere")

    def test_small_model_for_reports_the_same_model_the_instance_uses(self) -> None:
        """The resolved name is readable on the instance, so a subclass can log which model
        decided without repeating the lookup."""
        classifier = _classifier_with(_chain_returning(_ColourVerdict(warm=True)))

        assert classifier.model == small_model_for("anthropic")


class TestPromptAssembly:
    """The base contributes the system prompt and the output format, nothing else."""

    @pytest.mark.asyncio
    async def test_the_system_prompt_leads_the_messages_the_subclass_built(self) -> None:
        chain = _chain_returning(_ColourVerdict(warm=True))
        classifier = _classifier_with(chain)

        await classifier.classify({"colour": "crimson"})

        messages = chain.ainvoke.await_args.args[0]
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == _SYSTEM_PROMPT
        assert [m.content for m in messages[1:]] == ["crimson"]

    def test_the_output_schema_is_what_defines_the_answer_format(self) -> None:
        """No format instruction is written into the prompt: the schema handed to
        with_structured_output is the whole contract."""
        llm = MagicMock()
        with patch(_PROVIDER_CLIENTS["anthropic"], return_value=llm):
            _ColourClassifier()

        llm.with_structured_output.assert_called_once_with(_ColourVerdict)

    def test_a_subclass_must_build_its_own_messages(self) -> None:
        """There is no default rendering to fall back on: a classifier that does not say how
        its input becomes messages cannot be constructed at all."""
        with pytest.raises(TypeError, match="_build_messages"):
            _MessagelessClassifier(_SYSTEM_PROMPT, _ColourInput, _ColourVerdict, "anthropic", "k")  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_the_parsed_output_model_is_returned_unchanged(self) -> None:
        verdict = _ColourVerdict(warm=False)
        classifier = _classifier_with(_chain_returning(verdict))

        assert await classifier.classify({"colour": "cyan"}) is verdict


class TestInputValidation:
    """A payload is checked against the declared schema before a model is ever called."""

    @pytest.mark.asyncio
    async def test_a_missing_field_raises_without_calling_the_model(self) -> None:
        """The point of validating first: a malformed call costs nothing."""
        chain = _chain_returning(_ColourVerdict(warm=True))
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierInputError):
            await classifier.classify({})

        chain.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_field_of_the_wrong_type_raises(self) -> None:
        classifier = _classifier_with(_chain_returning(_ColourVerdict(warm=True)))

        with pytest.raises(ClassifierInputError):
            await classifier.classify({"colour": ["not", "a", "string"]})

    @pytest.mark.asyncio
    async def test_the_error_names_the_schema_that_rejected_the_payload(self) -> None:
        """A caller reading the log needs to know which schema it failed, not just that
        something did — the base serves several classifiers."""
        classifier = _classifier_with(_chain_returning(_ColourVerdict(warm=True)))

        with pytest.raises(ClassifierInputError, match="_ColourInput"):
            await classifier.classify({})

    def test_a_bad_payload_is_not_a_classification_failure(self) -> None:
        """A subclass that falls back on ClassifierError must not also swallow a malformed
        call: one is a model that failed, the other is a bug at the call site."""
        assert not issubclass(ClassifierInputError, ClassifierError)


class TestFailureTranslation:
    """Whatever the provider or the parser raises, a subclass sees one exception type."""

    @pytest.mark.asyncio
    async def test_a_failed_model_call_becomes_a_classifier_error(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=LangChainException("provider is down"))
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError):
            await classifier.classify({"colour": "amber"})

    @pytest.mark.asyncio
    async def test_an_answer_that_does_not_fit_the_schema_becomes_a_classifier_error(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=_a_validation_error())
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError):
            await classifier.classify({"colour": "amber"})

    @pytest.mark.asyncio
    async def test_the_original_failure_is_kept_as_the_cause(self) -> None:
        """The subclass decides what to do about the failure; whoever reads the traceback
        still needs to see what the provider actually said."""
        cause = LangChainException("rate limited")
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=cause)
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError) as excinfo:
            await classifier.classify({"colour": "amber"})

        assert excinfo.value.__cause__ is cause
