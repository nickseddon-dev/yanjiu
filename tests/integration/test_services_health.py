"""
Integration tests: verify all services respond to /health when running via docker compose.
"""

import pytest


class TestServicesHealth:
    """
    Test that every service defined in docker-compose.yml exposes a /health
    endpoint and responds with HTTP 200 after the stack is fully started.
    """

    def test_data_gateway_health(self, waitForDataGateway: bool):
        assert waitForDataGateway, "data_gateway did not become healthy"

    def test_event_gateway_health(self, waitForEventGateway: bool):
        assert waitForEventGateway, "event_gateway did not become healthy"

    def test_signal_publisher_health(self, waitForSignalPublisher: bool):
        assert waitForSignalPublisher, "signal_publisher did not become healthy"

    def test_feature_service_health(self, waitForFeatureService: bool):
        assert waitForFeatureService, "feature_service did not become healthy"

    def test_orchestrator_health(self, waitForOrchestrator: bool):
        assert waitForOrchestrator, "orchestrator did not become healthy"

    def test_risk_control_health(self, waitForRiskControl: bool):
        assert waitForRiskControl, "risk_control did not become healthy"

    def test_execution_control_health(self, waitForExecutionControl: bool):
        assert waitForExecutionControl, "execution_control did not become healthy"

    def test_report_generator_health(self, waitForReportGenerator: bool):
        assert waitForReportGenerator, "report_generator did not become healthy"

    def test_signal_bridge_health(self, waitForSignalBridge: bool):
        assert waitForSignalBridge, "signal_bridge did not become healthy"

    def test_research_runner_health(self, waitForResearchRunner: bool):
        assert waitForResearchRunner, "research_runner did not become healthy"

    def test_ops_dashboard_health(self, waitForOpsDashboard: bool):
        assert waitForOpsDashboard, "ops_dashboard did not become healthy"

    def test_analytics_health(self, waitForAnalytics: bool):
        assert waitForAnalytics, "analytics did not become healthy"

    def test_all_services_healthy_summary(self, all_services_healthy: dict):
        """Meta-test: fail if any service failed to become healthy."""
        failures = [name for name, ok in all_services_healthy.items() if not ok]
        assert not failures, f"Services failed to become healthy: {failures}"