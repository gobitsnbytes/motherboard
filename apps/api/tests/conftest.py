"""pytest configuration for bnb-api test suite."""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


# Use asyncio mode = auto so all async tests run without explicit decoration
