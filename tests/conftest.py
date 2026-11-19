import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("LONGSHOT_NETWORK_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="network test; set LONGSHOT_NETWORK_TESTS=1 to run")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
