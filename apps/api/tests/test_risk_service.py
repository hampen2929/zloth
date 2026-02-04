"""Tests for RiskService."""

from __future__ import annotations

import pytest

from zloth_api.domain.enums import RiskLevel
from zloth_api.services.risk_service import RiskService


@pytest.fixture
def risk_service() -> RiskService:
    """Create a RiskService instance."""
    return RiskService()


class TestRiskLevelCalculation:
    """Tests for risk level calculation."""

    def test_high_risk_dependency_files(self, risk_service: RiskService) -> None:
        """Test that dependency file changes are HIGH risk."""
        files = ["package.json", "src/app.ts"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH
        assert "R001" in reason
        assert "Dependency" in reason

    def test_high_risk_requirements_txt(self, risk_service: RiskService) -> None:
        """Test that requirements.txt changes are HIGH risk."""
        files = ["requirements.txt"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH
        assert "R001" in reason

    def test_high_risk_go_mod(self, risk_service: RiskService) -> None:
        """Test that go.mod changes are HIGH risk."""
        files = ["go.mod", "go.sum"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH

    def test_high_risk_security_paths(self, risk_service: RiskService) -> None:
        """Test that security path changes are HIGH risk."""
        files = ["src/auth/login.py", "src/app.py"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH
        assert "R002" in reason
        assert "Security" in reason

    def test_high_risk_crypto_files(self, risk_service: RiskService) -> None:
        """Test that crypto-related file changes are HIGH risk."""
        files = ["lib/crypto/encrypt.py"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH
        assert "R002" in reason

    def test_high_risk_infra_files(self, risk_service: RiskService) -> None:
        """Test that infrastructure file changes are HIGH risk."""
        files = ["terraform/main.tf", "README.md"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH
        assert "R003" in reason
        assert "Infrastructure" in reason

    def test_high_risk_docker_compose(self, risk_service: RiskService) -> None:
        """Test that docker-compose changes are HIGH risk."""
        files = ["docker-compose.yml"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH

    def test_high_risk_github_workflows(self, risk_service: RiskService) -> None:
        """Test that GitHub workflow changes are HIGH risk."""
        files = [".github/workflows/ci.yml"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH

    def test_low_risk_docs_only(self, risk_service: RiskService) -> None:
        """Test that documentation-only changes are LOW risk."""
        files = ["docs/guide.md", "README.md", "CHANGELOG.md"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.LOW
        assert "R006" in reason

    def test_low_risk_tests_only(self, risk_service: RiskService) -> None:
        """Test that test-only changes are LOW risk."""
        files = ["tests/test_api.py", "tests/test_utils.py"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.LOW
        assert "R005" in reason

    def test_low_risk_test_files_various_patterns(self, risk_service: RiskService) -> None:
        """Test various test file patterns are LOW risk."""
        test_patterns = [
            ["src/__tests__/component.test.ts"],
            ["api/user_test.go"],
            ["lib/utils.spec.js"],
            ["test_main.py"],
        ]

        for files in test_patterns:
            level, _ = risk_service.calculate_risk_level(files)
            assert level == RiskLevel.LOW, f"Failed for {files}"

    def test_medium_risk_default(self, risk_service: RiskService) -> None:
        """Test that standard code changes are MEDIUM risk."""
        files = ["src/components/Button.tsx", "src/utils/helpers.ts"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.MEDIUM
        assert "R004" in reason or "Standard" in reason

    def test_medium_risk_config_files(self, risk_service: RiskService) -> None:
        """Test that config file changes are MEDIUM risk."""
        files = ["tsconfig.json", ".eslintrc.js"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.MEDIUM
        assert "R007" in reason

    def test_multiple_rules_highest_wins(self, risk_service: RiskService) -> None:
        """Test that highest risk level is used when multiple rules match."""
        # Mix of HIGH risk (package.json) and LOW risk (test file)
        files = ["package.json", "tests/test_api.py"]
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.HIGH

    def test_empty_files_is_low_risk(self, risk_service: RiskService) -> None:
        """Test that empty file list is LOW risk."""
        files: list[str] = []
        level, reason = risk_service.calculate_risk_level(files)

        assert level == RiskLevel.LOW
        assert "No files changed" in reason


class TestRiskDetails:
    """Tests for risk details breakdown."""

    def test_get_risk_details(self, risk_service: RiskService) -> None:
        """Test getting detailed risk breakdown."""
        files = [
            "package.json",  # HIGH
            "src/auth/login.py",  # HIGH
            "tests/test_api.py",  # LOW
            "docs/README.md",  # LOW
            "src/app.py",  # Other
            "tsconfig.json",  # MEDIUM
        ]

        details = risk_service.get_risk_details(files)

        assert "package.json" in details["high_risk"]
        assert "src/auth/login.py" in details["high_risk"]
        assert "tests/test_api.py" in details["low_risk"]
        assert "docs/README.md" in details["low_risk"]
        assert "src/app.py" in details["other"]
        assert "tsconfig.json" in details["medium_risk"]

    def test_get_risk_details_empty(self, risk_service: RiskService) -> None:
        """Test risk details for empty file list."""
        details = risk_service.get_risk_details([])

        assert details["high_risk"] == []
        assert details["medium_risk"] == []
        assert details["low_risk"] == []
        assert details["other"] == []
