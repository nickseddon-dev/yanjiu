"""
Pytest fixtures and configuration for quant-os integration tests.
"""

import os
import time
import uuid
from contextlib import contextmanager
from typing import Generator

import pytest
import requests


# ---------------------------------------------------------------------------
# Service endpoints (from infra/compose/docker-compose.yml)
# ---------------------------------------------------------------------------
COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "..", "infra", "compose", "docker-compose.yml")

SERVICE_ENDPOINTS = {
    "data_gateway": "http://localhost:8091",
    "event_gateway": "http://localhost:8092",
    "signal_publisher": "http://localhost:8093",
    "feature_service": "http://localhost:8094",
    "orchestrator": "http://localhost:8095",
    "risk_control": "http://localhost:8096",
    "execution_control": "http://localhost:8097",
    "report_generator": "http://localhost:8098",
    "signal_bridge": "http://localhost:8090",
    "research_runner": "http://localhost:8099",
    "ops_dashboard": "http://localhost:3000",
    "analytics": "http://localhost:3010",
}

INFRA_ENDPOINTS = {
    "postgres": "http://localhost:5432",
    "redis": "http://localhost:6379",
    "prefect": "http://localhost:4200",
    "prometheus": "http://localhost:9090",
    "grafana": "http://localhost:3001",
}

ALL_ENDPOINTS = {**INFRA_ENDPOINTS, **SERVICE_ENDPOINTS}


# ---------------------------------------------------------------------------
# Docker Compose helpers
# ---------------------------------------------------------------------------

def docker_compose_cmd() -> list[str]:
    """Return the docker compose command (works for both compose v1 and v2)."""
    # Prefer docker compose v2 (standalone) if available, else fall back to plugin
    for cmd in ["docker-compose", "docker compose"]:
        return [cmd]


@contextmanager
def docker_compose_project(project_name: str = "quant-os-test"):
    """
    Start a docker compose project and tear it down after the context.

    Uses infra/compose/docker-compose.yml as the compose file.
    """
    import subprocess

    compose_cmd = docker_compose_cmd()
    compose_cmd += [
        "-f", COMPOSE_FILE,
        "-p", project_name,
        "up",
        "-d",
        "--build",
    ]

    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = "quantos_test"
    env["GRAFANA_PASSWORD"] = "admin"
    env["PREFECT_API_KEY"] = ""

    # Start services
    subprocess.run(compose_cmd, check=True, env=env, cwd=os.path.dirname(COMPOSE_FILE))

    try:
        yield
    finally:
        # Tear down
        teardown_cmd = docker_compose_cmd() + [
            "-f", COMPOSE_FILE,
            "-p", project_name,
            "down",
            "-v",  # remove volumes for clean state
            "--remove-orphans",
        ]
        subprocess.run(teardown_cmd, check=False, env=env, cwd=os.path.dirname(COMPOSE_FILE))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def dockerComposeProject() -> Generator[None, None, None]:
    """
    Session-scoped fixture that starts the full docker compose stack
    and tears it down after all tests complete.
    """
    project_name = f"quant-os-test-{uuid.uuid4().hex[:8]}"
    with docker_compose_project(project_name) as cm:
        yield


@pytest.fixture(scope="session")
def dockerComposeProjectForTeardown() -> Generator[str, None, None]:
    """
    Session-scoped fixture that returns the project name and keeps the stack alive.
    Use this when you need to inspect services after tests.
    """
    project_name = f"quant-os-test-{uuid.uuid4().hex[:8]}"
    compose_cmd = docker_compose_cmd()
    compose_cmd += [
        "-f", COMPOSE_FILE,
        "-p", project_name,
        "up",
        "-d",
        "--build",
    ]
    import subprocess
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = "quantos_test"
    env["GRAFANA_PASSWORD"] = "admin"
    env["PREFECT_API_KEY"] = ""

    subprocess.run(compose_cmd, check=True, env=env, cwd=os.path.dirname(COMPOSE_FILE))

    yield project_name

    teardown_cmd = docker_compose_cmd() + [
        "-f", COMPOSE_FILE,
        "-p", project_name,
        "down",
        "-v",
        "--remove-orphans",
    ]
    subprocess.run(teardown_cmd, check=False, env=env, cwd=os.path.dirname(COMPOSE_FILE))


# ---------------------------------------------------------------------------
# Health check helpers
# ---------------------------------------------------------------------------

def wait_for_service(
    url: str,
    path: str = "/health",
    timeout: int = 120,
    interval: float = 2.0,
) -> bool:
    """
    Block until a service responds 200 on its /health endpoint (or custom path).
    Returns True if the service became healthy within `timeout` seconds,
    False otherwise.
    """
    full_url = url.rstrip("/") + path
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            resp = requests.get(full_url, timeout=5)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)

    return False


# ---------------------------------------------------------------------------
# Per-service health check fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def waitForDataGateway(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["data_gateway"], timeout=120)


@pytest.fixture(scope="session")
def waitForEventGateway(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["event_gateway"], timeout=120)


@pytest.fixture(scope="session")
def waitForSignalPublisher(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["signal_publisher"], timeout=120)


@pytest.fixture(scope="session")
def waitForFeatureService(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["feature_service"], timeout=120)


@pytest.fixture(scope="session")
def waitForOrchestrator(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["orchestrator"], timeout=120)


@pytest.fixture(scope="session")
def waitForRiskControl(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["risk_control"], timeout=120)


@pytest.fixture(scope="session")
def waitForExecutionControl(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["execution_control"], timeout=120)


@pytest.fixture(scope="session")
def waitForReportGenerator(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["report_generator"], timeout=120)


@pytest.fixture(scope="session")
def waitForSignalBridge(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["signal_bridge"], timeout=120)


@pytest.fixture(scope="session")
def waitForResearchRunner(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["research_runner"], timeout=120)


@pytest.fixture(scope="session")
def waitForOpsDashboard(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["ops_dashboard"], timeout=120)


@pytest.fixture(scope="session")
def waitForAnalytics(dockerComposeProject) -> bool:
    return wait_for_service(SERVICE_ENDPOINTS["analytics"], timeout=120)


# ---------------------------------------------------------------------------
# Mock Redis fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_redis():
    """
    Provides a clean Redis client connected to the docker-compose redis service.
    Tests should use this when they need to manipulate Redis directly
    (e.g., seeding keys, verifying stream entries, flushing test data).
    """
    import redis

    client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        decode_responses=True,
    )

    # Flush test namespace before each test to avoid cross-test pollution
    # Only flush keys prefixed with "test:" so we don't destroy production data
    for key in client.scan_iter("test:*"):
        client.delete(key)

    yield client

    # Cleanup after test
    for key in client.scan_iter("test:*"):
        client.delete(key)


# ---------------------------------------------------------------------------
# Mock Postgres fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_postgres():
    """
    Provides a psycopg2 connection to the docker-compose postgres service.
    Tests should use this when they need to run SQL queries directly
    (e.g., seeding tables, verifying records).
    """
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        database=os.environ.get("POSTGRES_DB", "quantos"),
        user=os.environ.get("POSTGRES_USER", "quantos"),
        password=os.environ.get("POSTGRES_PASSWORD", "quantos_dev"),
    )
    conn.autocommit = True

    yield conn

    conn.close()


# ---------------------------------------------------------------------------
# Convenience session-scoped health check that waits for ALL services
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def all_services_healthy(dockerComposeProject) -> dict[str, bool]:
    """
    Waits for all services in docker-compose to become healthy and returns
    a dict mapping service name -> health status (True/False).
    """
    results = {}
    for name, url in SERVICE_ENDPOINTS.items():
        results[name] = wait_for_service(url, timeout=180, interval=3.0)
    return results