"""Schema tests for the chat completions request and response."""

import pytest
from pydantic import ValidationError

from sparkth.main import assemble_app
from sparkth.plugins.chat.schemas import AttachmentMeta, ChatCompletionRequest, ChatMessage

COMPLETIONS_PATH = "/api/v1/chat/completions"


def test_completions_200_response_declares_json_and_sse_union() -> None:
    """The 200 response must advertise both the JSON and SSE bodies.

    The route returns ChatCompletionResponse when stream=false and an SSE
    StreamingResponse when stream=true; the generated frontend types rely on
    the schema describing both shapes.
    """
    schema = assemble_app().openapi()
    content = schema["paths"][COMPLETIONS_PATH]["post"]["responses"]["200"]["content"]

    assert content["application/json"]["schema"]["$ref"] == "#/components/schemas/ChatCompletionResponse"
    assert "text/event-stream" in content


class TestTheRequestMustCarryAUserTurn:
    """A completion is a reply to something a user sent.

    Downstream code reads the last user message to know what to answer, judge for scope and
    retrieve against. A request with no user turn at all has nothing to answer, and letting it
    through means every one of those readers has to invent behaviour for a turn that does not
    exist — so it is refused at the boundary.
    """

    def test_a_request_with_no_user_message_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="user message"):
            ChatCompletionRequest(
                llm_config_id=1,
                messages=[ChatMessage(role="assistant", content="how can I help?")],
            )

    def test_a_user_message_anywhere_in_the_list_satisfies_it(self) -> None:
        """A system preamble ahead of the user's turn is normal, not malformed."""
        request = ChatCompletionRequest(
            llm_config_id=1,
            messages=[
                ChatMessage(role="system", content="be concise"),
                ChatMessage(role="user", content="Create a course on data privacy"),
            ],
        )

        assert len(request.messages) == 2

    def test_an_attachment_only_user_turn_is_still_a_user_turn(self) -> None:
        """Sending a document with no words is a real request; only the text is absent."""
        request = ChatCompletionRequest(
            llm_config_id=1,
            messages=[
                ChatMessage(
                    role="user",
                    content=[{"type": "document", "source": {"type": "base64", "data": ""}}],
                    attachment=AttachmentMeta(name="syllabus.pdf", size=1024),
                )
            ],
        )

        assert request.messages[0].attachment is not None
