"""OpenAPI schema tests for the chat completions route."""

from app.main import assemble_app

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
