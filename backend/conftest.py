"""
pytest configuration for EasyCaptcha tests.
Registers the --integration flag used by TestIntegration.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests against a live service on http://localhost:8080",
    )
