from typing import Any

import httpx
import pytest

from gtfs_translation.core.smartling import (
    SmartlingFileTranslator,
    SmartlingJobBatchesTranslator,
    SmartlingTranslator,
)


@pytest.mark.asyncio
async def test_smartling_auth_caching(respx_mock: Any) -> None:
    # Mock auth endpoint
    auth_route = respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "test-token", "expiresIn": 3600}}}
        )
    )

    # Mock translate endpoint
    trans_route = respx_mock.post(
        "https://api.smartling.com/mt-router-api/v2/accounts/acc123/smartling-mt"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "data": {"items": [{"key": "0", "translationText": "Hola", "provider": "test"}]}
                }
            },
        )
    )

    translator = SmartlingTranslator("user", "secret", "acc123")

    # First call: Auth + Translate
    res1 = await translator.translate_batch(["Hello"], ["es"])
    assert res1 == {"es": ["Hola"]}
    assert auth_route.call_count == 1
    assert trans_route.call_count == 1

    # Second call: Should use cached token
    res2 = await translator.translate_batch(["Hello"], ["es"])
    assert res2 == {"es": ["Hola"]}
    assert auth_route.call_count == 1  # Still 1
    assert trans_route.call_count == 2

    await translator.close()


@pytest.mark.asyncio
async def test_smartling_auth_retry_on_401(respx_mock: Any) -> None:
    # Mock auth endpoint (returns same token)
    respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "new-token", "expiresIn": 3600}}}
        )
    )

    # Mock translate endpoint to fail first with 401, then succeed
    trans_route = respx_mock.post(
        "https://api.smartling.com/mt-router-api/v2/accounts/acc123/smartling-mt"
    )
    trans_route.side_effect = [
        httpx.Response(401),
        httpx.Response(
            200,
            json={
                "response": {
                    "data": {
                        "items": [
                            {"key": "0", "translationText": "Retry Success", "provider": "test"}
                        ]
                    }
                }
            },
        ),
    ]

    translator = SmartlingTranslator("user", "secret", "acc123")
    # Pre-set a "stale" token
    translator._token = "stale"
    translator._token_expiry = 9999999999

    res = await translator.translate_batch(["Hello"], ["es"])
    assert res == {"es": ["Retry Success"]}
    assert trans_route.call_count == 2

    await translator.close()


@pytest.mark.asyncio
async def test_smartling_job_batches_translator(respx_mock: Any) -> None:
    # Auth
    respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "test-token", "expiresIn": 3600}}}
        )
    )

    # Job
    respx_mock.post("https://api.smartling.com/job-batches-api/v2/projects/proj123/jobs").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"translationJobUid": "job123"}}}
        )
    )

    # Batch
    respx_mock.post("https://api.smartling.com/job-batches-api/v2/projects/proj123/batches").mock(
        return_value=httpx.Response(200, json={"response": {"data": {"batchUid": "batch123"}}})
    )

    # Upload
    respx_mock.post(
        "https://api.smartling.com/job-batches-api/v2/projects/proj123/batches/batch123/file"
    ).mock(return_value=httpx.Response(202, json={"response": {"code": "ACCEPTED"}}))

    # Status
    respx_mock.get(
        "https://api.smartling.com/job-batches-api/v2/projects/proj123/batches/batch123"
    ).mock(return_value=httpx.Response(200, json={"response": {"data": {"status": "COMPLETED"}}}))

    # Download
    respx_mock.get("https://api.smartling.com/files-api/v2/projects/proj123/locales/es/file").mock(
        return_value=httpx.Response(200, json=["Hola"])
    )

    translator = SmartlingJobBatchesTranslator("user", "secret", "proj123", "s3://bucket/key.json")
    res = await translator.translate_batch(["Hello"], ["es"])

    assert res == {"es": ["Hola"]}
    await translator.close()


@pytest.mark.asyncio
async def test_smartling_file_translator(respx_mock: Any) -> None:
    # Mock auth endpoint
    respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "test-token", "expiresIn": 3600}}}
        )
    )

    # Mock file upload
    upload_route = respx_mock.post(
        "https://api.smartling.com/file-translations-api/v2/accounts/acc123/files"
    ).mock(return_value=httpx.Response(200, json={"response": {"data": {"fileUid": "file123"}}}))

    # Mock MT start
    mt_start_route = respx_mock.post(
        "https://api.smartling.com/file-translations-api/v2/accounts/acc123/files/file123/mt"
    ).mock(return_value=httpx.Response(200, json={"response": {"data": {"mtUid": "mt123"}}}))

    # Mock status check (first IN_PROGRESS, then COMPLETED)
    status_route = respx_mock.get(
        "https://api.smartling.com/file-translations-api/v2/accounts/acc123/files/file123/mt/mt123/status"
    )
    status_route.side_effect = [
        httpx.Response(200, json={"response": {"data": {"status": "IN_PROGRESS"}}}),
        httpx.Response(200, json={"response": {"data": {"status": "COMPLETED"}}}),
    ]

    # Mock download
    dl_route = respx_mock.get(
        "https://api.smartling.com/file-translations-api/v2/accounts/acc123/files/file123/mt/mt123/locales/es/file"
    ).mock(return_value=httpx.Response(200, json=["Hola", "Mundo"]))

    translator = SmartlingFileTranslator("user", "secret", "acc123")
    res = await translator.translate_batch(["Hello", "World"], ["es"])

    assert res == {"es": ["Hola", "Mundo"]}
    assert upload_route.call_count == 1
    assert mt_start_route.call_count == 1
    assert status_route.call_count == 2
    assert dl_route.call_count == 1

    await translator.close()


@pytest.mark.asyncio
async def test_upload_file_to_batch_locale_ids_format(respx_mock: Any) -> None:
    """Test that localeIdsToAuthorize[] is sent as a single comma-separated value."""
    # Mock auth endpoint
    respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "test-token", "expiresIn": 3600}}}
        )
    )

    # Track the upload request
    upload_requests = []

    def capture_upload_request(request: httpx.Request) -> httpx.Response:
        """Capture the request for inspection."""
        upload_requests.append(request)
        return httpx.Response(202, json={"response": {"code": "ACCEPTED"}})

    # Mock batch upload endpoint
    respx_mock.post(
        "https://api.smartling.com/job-batches-api/v2/projects/proj123/batches/batch123/file"
    ).mock(side_effect=capture_upload_request)

    translator = SmartlingJobBatchesTranslator("user", "secret", "proj123", "s3://bucket/key.json")

    # Manually call the upload method
    headers = {"Authorization": "Bearer test-token"}
    target_langs = ["es", "fr", "pt"]

    await translator._upload_file_to_batch(headers, "batch123", ["Hello", "World"], target_langs)

    # Verify the request was made
    assert len(upload_requests) == 1
    request = upload_requests[0]

    # Parse the multipart form data
    content = request.content.decode("utf-8")

    # Verify that localeIdsToAuthorize[] appears once with comma-separated values
    # The exact format depends on how httpx encodes multipart, but we can check:
    # 1. It contains the field name
    assert 'name="localeIdsToAuthorize[]"' in content

    # 2. It contains the comma-separated language codes
    assert "es,fr,pt" in content

    # 3. Verify there's only ONE occurrence of the field (not multiple)
    locale_field_count = content.count('name="localeIdsToAuthorize[]"')
    assert locale_field_count == 1, (
        f"Expected 1 localeIdsToAuthorize[] field, found {locale_field_count}"
    )

    await translator.close()


@pytest.mark.asyncio
async def test_upload_file_to_batch_single_language(respx_mock: Any) -> None:
    """Test that localeIdsToAuthorize[] works correctly with a single language."""
    # Mock auth endpoint
    respx_mock.post("https://api.smartling.com/auth-api/v2/authenticate").mock(
        return_value=httpx.Response(
            200, json={"response": {"data": {"accessToken": "test-token", "expiresIn": 3600}}}
        )
    )

    # Track the upload request
    upload_requests = []

    def capture_upload_request(request: httpx.Request) -> httpx.Response:
        """Capture the request for inspection."""
        upload_requests.append(request)
        return httpx.Response(202, json={"response": {"code": "ACCEPTED"}})

    # Mock batch upload endpoint
    respx_mock.post(
        "https://api.smartling.com/job-batches-api/v2/projects/proj123/batches/batch123/file"
    ).mock(side_effect=capture_upload_request)

    translator = SmartlingJobBatchesTranslator("user", "secret", "proj123", "s3://bucket/key.json")

    # Manually call the upload method with a single language
    headers = {"Authorization": "Bearer test-token"}
    target_langs = ["es"]

    await translator._upload_file_to_batch(headers, "batch123", ["Hello"], target_langs)

    # Verify the request was made
    assert len(upload_requests) == 1
    request = upload_requests[0]

    # Parse the multipart form data
    content = request.content.decode("utf-8")

    # Verify that localeIdsToAuthorize[] appears once with the single language
    assert 'name="localeIdsToAuthorize[]"' in content
    assert "es" in content

    # Verify there's only ONE occurrence of the field
    locale_field_count = content.count('name="localeIdsToAuthorize[]"')
    assert locale_field_count == 1

    await translator.close()
