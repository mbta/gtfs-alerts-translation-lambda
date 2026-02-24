"""Tests for translation timeout handling."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from google.transit import gtfs_realtime_pb2

from gtfs_translation.lambda_handler import run_translation


@pytest.fixture
def mock_s3() -> Any:
    with patch("gtfs_translation.lambda_handler.s3") as mock:
        yield mock


@pytest.fixture
def mock_settings() -> Any:
    with patch("gtfs_translation.config.settings") as mock:
        mock.source_url = "http://example.com/alerts.pb"
        mock.destination_bucket_url_list = ["s3://test-bucket/alerts.pb"]
        mock.target_lang_list = ["es-419"]
        mock.concurrency_limit = 20
        mock.translation_timeout = 1  # Short timeout for testing
        mock.smartling_project_id = "test-project"
        mock.smartling_user_id = "test-user"
        mock.smartling_user_secret = "test-secret"
        mock.smartling_job_name_template = "Test Job"
        yield mock


@pytest.fixture
def sample_feed() -> gtfs_realtime_pb2.FeedMessage:
    """Create a sample GTFS-RT feed for testing."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1234567890

    entity = feed.entity.add()
    entity.id = "test-alert-1"
    alert = entity.alert

    header = alert.header_text.translation.add()
    header.text = "Test Alert"
    header.language = "en"

    desc = alert.description_text.translation.add()
    desc.text = "This is a test alert description."
    desc.language = "en"

    return feed


@pytest.mark.asyncio
async def test_translation_timeout_publishes_untranslated_feed(
    mock_s3: Any, mock_settings: Any, sample_feed: gtfs_realtime_pb2.FeedMessage
) -> None:
    """Test that feed is published without translations when translation times out."""

    async def slow_translate_batch(
        texts: list[str], target_langs: list[str]
    ) -> dict[str, list[str]]:
        """Simulate a slow translation that exceeds timeout."""
        await asyncio.sleep(5)  # Longer than our 1 second timeout
        return {lang: [f"[{lang}] {text}" for text in texts] for lang in target_langs}

    with (
        patch("gtfs_translation.lambda_handler.fetch_source") as mock_fetch_source,
        patch("gtfs_translation.lambda_handler.fetch_old_feed") as mock_fetch_old_feed,
        patch("gtfs_translation.lambda_handler.get_s3_parts") as mock_get_s3_parts,
        patch(
            "gtfs_translation.lambda_handler.SmartlingJobBatchesTranslator"
        ) as mock_translator_class,
    ):
        # Setup mocks
        mock_fetch_source.return_value = (sample_feed.SerializeToString(), "pb")
        mock_fetch_old_feed.return_value = (None, None)
        mock_get_s3_parts.return_value = ("test-bucket", "alerts.pb")

        # Create mock translator with slow translate_batch
        mock_translator = AsyncMock()
        mock_translator.translate_batch = AsyncMock(side_effect=slow_translate_batch)
        mock_translator.close = AsyncMock()
        mock_translator_class.return_value = mock_translator

        # Run translation
        await run_translation(mock_settings.source_url, mock_settings.destination_bucket_url_list)

        # Verify feed was uploaded despite timeout
        assert mock_s3.put_object.called
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == "alerts.pb"
        assert call_args[1]["ContentType"] == "application/x-protobuf"

        # Verify translator was closed
        mock_translator.close.assert_called_once()


@pytest.mark.asyncio
async def test_translation_error_publishes_untranslated_feed(
    mock_s3: Any, mock_settings: Any, sample_feed: gtfs_realtime_pb2.FeedMessage
) -> None:
    """Test that feed is published without translations when translation raises an error."""

    async def failing_translate_batch(
        texts: list[str], target_langs: list[str]
    ) -> dict[str, list[str]]:
        """Simulate a translation that fails."""
        raise Exception("Smartling API error")

    with (
        patch("gtfs_translation.lambda_handler.fetch_source") as mock_fetch_source,
        patch("gtfs_translation.lambda_handler.fetch_old_feed") as mock_fetch_old_feed,
        patch("gtfs_translation.lambda_handler.get_s3_parts") as mock_get_s3_parts,
        patch(
            "gtfs_translation.lambda_handler.SmartlingJobBatchesTranslator"
        ) as mock_translator_class,
    ):
        # Setup mocks
        mock_fetch_source.return_value = (sample_feed.SerializeToString(), "pb")
        mock_fetch_old_feed.return_value = (None, None)
        mock_get_s3_parts.return_value = ("test-bucket", "alerts.pb")

        # Create mock translator with failing translate_batch
        mock_translator = AsyncMock()
        mock_translator.translate_batch = AsyncMock(side_effect=failing_translate_batch)
        mock_translator.close = AsyncMock()
        mock_translator_class.return_value = mock_translator

        # Run translation
        await run_translation(mock_settings.source_url, mock_settings.destination_bucket_url_list)

        # Verify feed was uploaded despite error
        assert mock_s3.put_object.called
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == "alerts.pb"

        # Verify translator was closed
        mock_translator.close.assert_called_once()


@pytest.mark.asyncio
async def test_successful_translation_uploads_translated_feed(
    mock_s3: Any, mock_settings: Any, sample_feed: gtfs_realtime_pb2.FeedMessage
) -> None:
    """Test that feed with translations is uploaded when translation succeeds."""

    async def successful_translate_batch(
        texts: list[str], target_langs: list[str]
    ) -> dict[str, list[str]]:
        """Simulate a successful translation."""
        await asyncio.sleep(0.1)  # Short delay, under timeout
        return {lang: [f"[{lang}] {text}" for text in texts] for lang in target_langs}

    with (
        patch("gtfs_translation.lambda_handler.fetch_source") as mock_fetch_source,
        patch("gtfs_translation.lambda_handler.fetch_old_feed") as mock_fetch_old_feed,
        patch("gtfs_translation.lambda_handler.get_s3_parts") as mock_get_s3_parts,
        patch(
            "gtfs_translation.lambda_handler.SmartlingJobBatchesTranslator"
        ) as mock_translator_class,
    ):
        # Setup mocks
        mock_fetch_source.return_value = (sample_feed.SerializeToString(), "pb")
        mock_fetch_old_feed.return_value = (None, None)
        mock_get_s3_parts.return_value = ("test-bucket", "alerts.pb")

        # Create mock translator with successful translate_batch
        mock_translator = AsyncMock()
        mock_translator.translate_batch = AsyncMock(side_effect=successful_translate_batch)
        mock_translator.close = AsyncMock()
        mock_translator_class.return_value = mock_translator

        # Run translation
        await run_translation(mock_settings.source_url, mock_settings.destination_bucket_url_list)

        # Verify feed was uploaded
        assert mock_s3.put_object.called
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == "alerts.pb"

        # Verify translator was closed
        mock_translator.close.assert_called_once()
