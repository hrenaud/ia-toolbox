"""
No remote-service client may enter the worker's dependency closure.

Processing is local by construction, not because a test run happened to make
no network call. The guarantee rests entirely on what is installed: markitdown
publishes an ``all`` extra that pulls Azure Document Intelligence, Azure
Content Understanding and speech clients, so widening the pin from
``[docx,pdf,pptx,xls,xlsx]`` would hand document contents to a remote service
without a single line of our code changing.
"""

from importlib.metadata import distributions

# Distribution name fragments that only appear with a remote-service client.
FORBIDDEN_FRAGMENTS = (
    "azure",
    "boto",
    "google-cloud",
    "openai",
    "anthropic",
    "speechrecognition",
    "youtube-transcript-api",
)


def find_remote_clients(names: list[str]) -> list[str]:
    """
    Return the names that identify a remote-service client.

    Arguments:
        names: Installed distribution names.

    Returns:
        The offending names, sorted.
    """
    return sorted(
        name
        for name in names
        if any(fragment in name.lower() for fragment in FORBIDDEN_FRAGMENTS)
    )


def test_installed_closure_has_no_remote_service_client():
    """The worker environment must be unable to reach a document service."""
    installed = [dist.metadata["Name"] or "" for dist in distributions()]

    assert find_remote_clients(installed) == []


def test_detection_recognises_a_cloud_client():
    """Guard the guard: an empty result must mean a clean closure, not a no-op."""
    assert find_remote_clients(
        ["markitdown", "azure-ai-documentintelligence"]
    ) == ["azure-ai-documentintelligence"]
