"""Unit tests for gwark.core.async_utils."""

import pytest
from unittest.mock import MagicMock

from gwark.core.async_utils import retry_execute, check_anthropic_key


class TestRetryExecute:
    def test_success_on_first_try(self):
        mock_request = MagicMock()
        mock_request.execute.return_value = {"result": "ok"}
        result = retry_execute(mock_request, operation="test")
        assert result == {"result": "ok"}
        assert mock_request.execute.call_count == 1

    def test_retries_on_429(self):
        from googleapiclient.errors import HttpError
        import json

        mock_request = MagicMock()
        error_content = json.dumps({"error": {"message": "Rate limited"}}).encode()
        error_resp = MagicMock()
        error_resp.status = 429
        error_resp.reason = "Too Many Requests"

        mock_request.execute.side_effect = [
            HttpError(error_resp, error_content),
            {"result": "ok"},
        ]
        result = retry_execute(mock_request, operation="test")
        assert result == {"result": "ok"}
        assert mock_request.execute.call_count == 2

    def test_raises_on_non_retryable(self):
        from googleapiclient.errors import HttpError
        import json

        mock_request = MagicMock()
        error_content = json.dumps({"error": {"message": "Not found"}}).encode()
        error_resp = MagicMock()
        error_resp.status = 404
        error_resp.reason = "Not Found"

        mock_request.execute.side_effect = HttpError(error_resp, error_content)
        with pytest.raises(HttpError):
            retry_execute(mock_request, operation="test")


class TestCheckAnthropicKey:
    def test_returns_false_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert check_anthropic_key() is False

    def test_returns_true_with_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        assert check_anthropic_key() is True

    def test_returns_false_with_empty_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        assert check_anthropic_key() is False
