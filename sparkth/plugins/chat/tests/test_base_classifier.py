"""Tests for the shared classifier base.

The base owns three things and decides nothing else: which model a provider gets, that the system
prompt leads the messages a subclass built, and that a failed call reaches the subclass as one
exception type. What a payload must look like is now the signature's job — ``classify`` takes the
input schema itself, so a wrong shape is a type error rather than a test case.

Each is asserted here against a throwaway subclass, so the two real
classifiers can be read for what makes them different rather than for this plumbing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from sparkth.lib.llm import get_provider_catalog
from sparkth.plugins.chat.classifiers.base import SMALL_MODELS, BaseClassifier, small_model_for
from sparkth.plugins.chat.exceptions import ClassifierError

_SYSTEM_PROMPT = "Decide whether the colour is warm."

_GET_PROVIDER = "sparkth.plugins.chat.classifiers.base.get_provider"


class _ColourInput(BaseModel):
    colour: str


class _ColourVerdict(BaseModel):
    warm: bool


class _ColourClassifier(BaseClassifier[_ColourInput, _ColourVerdict]):
    """The smallest possible subclass: one human turn carrying the validated colour."""

    def __init__(self, provider_name: str = "anthropic", api_key: str = "test-key") -> None:
        super().__init__(_SYSTEM_PROMPT, _ColourVerdict, provider_name, api_key)

    def _build_messages(self, payload: _ColourInput) -> list[BaseMessage]:
        return [HumanMessage(content=payload.colour)]


def _a_validation_error() -> ValidationError:
    """A real pydantic ValidationError, as structured output raises when a model's answer
    does not fit the schema. Constructed from the schema rather than hand-built so it stays
    the same error type the runtime would see."""
    with pytest.raises(ValidationError) as excinfo:
        _ColourVerdict.model_validate({})
    return excinfo.value


def _classifier_with(chain: MagicMock, provider_name: str = "anthropic") -> _ColourClassifier:
    """A classifier whose facade-built LLM is replaced by one yielding ``chain``."""
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    provider = MagicMock()
    provider.create_llm.return_value = llm
    with patch(_GET_PROVIDER, return_value=provider):
        return _ColourClassifier(provider_name)


def _chain_returning(verdict: _ColourVerdict) -> MagicMock:
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=verdict)
    return chain


class TestModelSelection:
    """Whichever provider the user chose for chat, the classifier runs on its smallest model.

    The client itself is built by the lib facade, which owns provider-to-client construction for
    the whole codebase — so what is asserted here is what the facade is asked for, not how any one
    provider's client takes its arguments.
    """

    @pytest.mark.parametrize("provider_name", ["openai", "anthropic", "google"])
    def test_each_provider_is_asked_for_its_smallest_model(self, provider_name: str) -> None:
        with patch(_GET_PROVIDER) as mock_get_provider:
            _ColourClassifier(provider_name, "user-key")

        assert mock_get_provider.call_args.args == (provider_name, "user-key", SMALL_MODELS[provider_name])

    def test_the_model_is_asked_for_at_temperature_zero(self) -> None:
        """A classification is a verdict, not prose: the same turn should not get two answers."""
        with patch(_GET_PROVIDER) as mock_get_provider:
            _ColourClassifier("anthropic", "user-key")

        assert mock_get_provider.call_args.kwargs["temperature"] == 0

    def test_an_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported provider"):
            _ColourClassifier("cohere")

    def test_every_provider_the_facade_supports_has_a_small_model(self) -> None:
        """SMALL_MODELS is plugin-local, while the facade's registry is what a stored LLMConfig is
        validated against. A provider added there with no entry here raises for every chat request
        from a user who selected it, before their conversation is even resolved."""
        assert {entry["id"] for entry in get_provider_catalog()} == set(SMALL_MODELS)

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

        await classifier.classify(_ColourInput(colour="crimson"))

        messages = chain.ainvoke.await_args.args[0]
        assert isinstance(messages[0], SystemMessage)
        assert messages[0].content == _SYSTEM_PROMPT
        assert [m.content for m in messages[1:]] == ["crimson"]

    def test_the_output_schema_is_what_defines_the_answer_format(self) -> None:
        """No format instruction is written into the prompt: the schema handed to
        with_structured_output is the whole contract."""
        llm = MagicMock()
        provider = MagicMock()
        provider.create_llm.return_value = llm
        with patch(_GET_PROVIDER, return_value=provider):
            _ColourClassifier()

        llm.with_structured_output.assert_called_once_with(_ColourVerdict)

    @pytest.mark.asyncio
    async def test_the_parsed_output_model_is_returned_unchanged(self) -> None:
        verdict = _ColourVerdict(warm=False)
        classifier = _classifier_with(_chain_returning(verdict))

        assert await classifier.classify(_ColourInput(colour="cyan")) is verdict


class TestTheOutputSchemaIsEnforcedOnTheAnswer:
    """The declared schema is what a caller gets back, whatever the provider returned.

    Structured output normally hands back a parsed model, and these assertions do not depend
    on that: a provider path that returns the raw mapping instead must still be validated
    here, because a subclass reads fields off the result and an unvalidated mapping would fail
    at the attribute rather than at the boundary.
    """

    @pytest.mark.asyncio
    async def test_a_raw_mapping_is_validated_into_the_output_model(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(return_value={"warm": True})
        classifier = _classifier_with(chain)

        verdict = await classifier.classify(_ColourInput(colour="amber"))

        assert isinstance(verdict, _ColourVerdict)
        assert verdict.warm is True

    @pytest.mark.asyncio
    async def test_a_mapping_that_does_not_fit_the_schema_becomes_a_classifier_error(self) -> None:
        """An answer that cannot be made into the output model is a failed classification, not
        something to hand onward."""
        chain = MagicMock()
        chain.ainvoke = AsyncMock(return_value={"lukewarm": True})
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError):
            await classifier.classify(_ColourInput(colour="amber"))

    @pytest.mark.asyncio
    async def test_an_already_parsed_model_is_returned_as_it_is(self) -> None:
        """The common path: the parser did the work, so there is nothing to redo."""
        verdict = _ColourVerdict(warm=False)
        classifier = _classifier_with(_chain_returning(verdict))

        assert await classifier.classify(_ColourInput(colour="cyan")) is verdict


class TestFailureTranslation:
    """Whatever the provider or the parser raises, a subclass sees one exception type."""

    @pytest.mark.asyncio
    async def test_a_failed_model_call_becomes_a_classifier_error(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=LangChainException("provider is down"))
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError):
            await classifier.classify(_ColourInput(colour="amber"))

    @pytest.mark.asyncio
    async def test_an_answer_that_does_not_fit_the_schema_becomes_a_classifier_error(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=_a_validation_error())
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError):
            await classifier.classify(_ColourInput(colour="amber"))

    @pytest.mark.asyncio
    async def test_the_original_failure_is_kept_as_the_cause(self) -> None:
        """The subclass decides what to do about the failure; whoever reads the traceback
        still needs to see what the provider actually said."""
        cause = LangChainException("rate limited")
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=cause)
        classifier = _classifier_with(chain)

        with pytest.raises(ClassifierError) as excinfo:
            await classifier.classify(_ColourInput(colour="amber"))

        assert excinfo.value.__cause__ is cause
