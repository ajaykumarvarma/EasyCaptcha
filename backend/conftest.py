"""
pytest configuration for EasyCaptcha tests.
Registers the --integration flag used by TestIntegration.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests against a live service on http://localhost:8080",
    )


# Tell pytest-asyncio to use auto mode so @pytest.mark.asyncio works
# without requiring explicit fixture configuration.
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio coroutine"
    )
