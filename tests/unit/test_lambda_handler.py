import os
from typing import Any

import pytest
from pytest_mock import MockerFixture

# Set env vars before importing lambda_handler to satisfy Pydantic
os.environ["SMARTLING_USER_ID"] = "test"
os.environ["SMARTLING_USER_SECRET"] = "test"
os.environ["SMARTLING_ACCOUNT_UID"] = "test"

from gtfs_translation.lambda_handler import lambda_handler


def test_lambda_handler_s3_event(mocker: MockerFixture) -> None:
    # Mock settings
    mocker.patch("gtfs_translation.config.settings.destination_bucket_url", "s3://dest/feed.pb")
    mocker.patch("gtfs_translation.config.settings.target_languages", "es")

    # Mock run_translation
    mock_run = mocker.patch("gtfs_translation.lambda_handler.run_translation")

    event: dict[str, Any] = {
        "Records": [{"s3": {"bucket": {"name": "source-bucket"}, "object": {"key": "alerts.pb"}}}]
    }

    lambda_handler(event, None)

    # Verify it called run_translation with the correct S3 URL
    mock_run.assert_called_once_with("s3://source-bucket/alerts.pb", "s3://dest/feed.pb")


def test_lambda_handler_same_source_dest(mocker: MockerFixture) -> None:
    mocker.patch("gtfs_translation.config.settings.source_url", "s3://same/path")
    mocker.patch("gtfs_translation.config.settings.destination_bucket_url", "s3://same/path")

    with pytest.raises(ValueError, match="Source and destination URL are the same"):
        lambda_handler({}, None)
