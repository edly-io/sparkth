"""Tests for embedding provider initialization."""

from unittest.mock import MagicMock, patch


class TestInitProvider:
    def test_init_provider_sets_single_threaded_torch(self) -> None:
        """Verify init_provider calls torch.set_num_threads(1)."""
        from app.rag.provider import init_provider, reset_provider

        reset_provider()

        mock_torch = MagicMock()
        with (
            patch("app.rag.provider.get_settings") as mock_settings,
            patch("app.rag.provider._build_provider") as mock_build,
            patch("app.rag.provider.log_memory_snapshot"),
            patch.dict("sys.modules", {"torch": mock_torch}),
        ):
            mock_settings.return_value.RAG_EMBEDDING_PROVIDER = "huggingface"
            mock_settings.return_value.RAG_EMBEDDING_MODEL = "test-model"

            mock_model = MagicMock()
            mock_model.embed_documents.return_value = [[0.1] * 384]
            mock_provider = MagicMock()
            mock_provider.get_embeddings_model.return_value = mock_model
            mock_build.return_value = mock_provider

            init_provider()

        # Verify torch.set_num_threads(1) was called
        mock_torch.set_num_threads.assert_called_once_with(1)
        mock_torch.set_num_interop_threads.assert_called_once_with(1)
        reset_provider()

    def test_init_provider_calls_warmup_inference(self) -> None:
        """Verify init_provider runs embed_documents(['warmup']) after loading weights."""
        from app.rag.provider import init_provider, reset_provider

        reset_provider()

        with (
            patch("app.rag.provider.get_settings") as mock_settings,
            patch("app.rag.provider._build_provider") as mock_build,
            patch("app.rag.provider.log_memory_snapshot"),
        ):
            mock_settings.return_value.RAG_EMBEDDING_PROVIDER = "huggingface"
            mock_settings.return_value.RAG_EMBEDDING_MODEL = "test-model"

            mock_model = MagicMock()
            mock_model.embed_documents.return_value = [[0.1] * 384]
            mock_provider = MagicMock()
            mock_provider.get_embeddings_model.return_value = mock_model
            mock_build.return_value = mock_provider

            init_provider()

        mock_model.embed_documents.assert_called_once_with(["warmup"])
        reset_provider()
