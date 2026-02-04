"""Risk level calculation service for Decision Visibility (P0).

This service calculates risk levels based on file change patterns.
Implements rules R001-R007 from gen2 vision document.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass

from zloth_api.domain.enums import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class RiskRule:
    """Risk rule definition."""

    id: str
    level: RiskLevel
    patterns: list[str]
    description: str


class RiskService:
    """Service for calculating risk levels based on file changes.

    Risk Rules (from gen2 vision document):
    - R001: Dependencies (HIGH) - package.json, requirements.txt, go.mod, etc.
    - R002: Security (HIGH) - auth/, security/, crypto/, *.secret
    - R003: Infrastructure (HIGH) - terraform/, kubernetes/, docker-compose.yml
    - R004: Core (MEDIUM) - src/, lib/, app/ (default for code changes)
    - R005: Tests (LOW) - tests/, *_test.*, *.spec.*
    - R006: Docs (LOW) - docs/, *.md, README
    - R007: Config (MEDIUM) - .eslintrc, tsconfig.json, pyproject.toml
    """

    # HIGH risk patterns
    DEPENDENCY_PATTERNS = [
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "requirements.txt",
        "requirements*.txt",
        "Pipfile",
        "Pipfile.lock",
        "pyproject.toml",
        "poetry.lock",
        "go.mod",
        "go.sum",
        "Cargo.toml",
        "Cargo.lock",
        "Gemfile",
        "Gemfile.lock",
        "composer.json",
        "composer.lock",
    ]

    SECURITY_PATTERNS = [
        "auth/*",
        "*/auth/*",
        "security/*",
        "*/security/*",
        "crypto/*",
        "*/crypto/*",
        "*.secret",
        "*.key",
        "*.pem",
        "*.crt",
        "**/secrets/*",
        "**/credentials/*",
    ]

    INFRA_PATTERNS = [
        "terraform/*",
        "*/terraform/*",
        "*.tf",
        "kubernetes/*",
        "*/kubernetes/*",
        "k8s/*",
        "*/k8s/*",
        "*.yaml",  # k8s manifests (conservative)
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose*.yml",
        "docker-compose*.yaml",
        "Dockerfile",
        "Dockerfile.*",
        ".github/workflows/*",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        "cloudbuild.yaml",
    ]

    # LOW risk patterns
    DOCS_PATTERNS = [
        "docs/*",
        "*/docs/*",
        "*.md",
        "README",
        "README.*",
        "CHANGELOG",
        "CHANGELOG.*",
        "LICENSE",
        "LICENSE.*",
        "CONTRIBUTING",
        "CONTRIBUTING.*",
    ]

    TEST_PATTERNS = [
        "tests/*",
        "*/tests/*",
        "test/*",
        "*/test/*",
        "__tests__/*",
        "*/__tests__/*",
        "*_test.py",
        "*_test.go",
        "*_test.ts",
        "*_test.js",
        "*.test.ts",
        "*.test.js",
        "*.test.tsx",
        "*.test.jsx",
        "*.spec.ts",
        "*.spec.js",
        "*.spec.tsx",
        "*.spec.jsx",
        "test_*.py",
    ]

    # MEDIUM risk patterns (config files)
    CONFIG_PATTERNS = [
        ".eslintrc",
        ".eslintrc.*",
        ".prettierrc",
        ".prettierrc.*",
        "tsconfig.json",
        "tsconfig.*.json",
        "jest.config.*",
        "vitest.config.*",
        "webpack.config.*",
        "vite.config.*",
        "next.config.*",
        "nuxt.config.*",
        ".env.example",
        "ruff.toml",
        "mypy.ini",
        "setup.py",
        "setup.cfg",
    ]

    RULES: list[RiskRule] = [
        RiskRule(
            id="R001",
            level=RiskLevel.HIGH,
            patterns=DEPENDENCY_PATTERNS,
            description="Dependency file changes",
        ),
        RiskRule(
            id="R002",
            level=RiskLevel.HIGH,
            patterns=SECURITY_PATTERNS,
            description="Security-related file changes",
        ),
        RiskRule(
            id="R003",
            level=RiskLevel.HIGH,
            patterns=INFRA_PATTERNS,
            description="Infrastructure file changes",
        ),
        RiskRule(
            id="R005",
            level=RiskLevel.LOW,
            patterns=TEST_PATTERNS,
            description="Test file changes only",
        ),
        RiskRule(
            id="R006",
            level=RiskLevel.LOW,
            patterns=DOCS_PATTERNS,
            description="Documentation changes only",
        ),
        RiskRule(
            id="R007",
            level=RiskLevel.MEDIUM,
            patterns=CONFIG_PATTERNS,
            description="Configuration file changes",
        ),
    ]

    def _matches_patterns(self, path: str, patterns: list[str]) -> bool:
        """Check if a file path matches any of the patterns.

        Args:
            path: File path to check.
            patterns: List of glob patterns.

        Returns:
            True if path matches any pattern.
        """
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check basename for simple patterns
            if "/" not in pattern and fnmatch.fnmatch(path.split("/")[-1], pattern):
                return True
        return False

    def _get_matching_rules(self, files: list[str]) -> list[RiskRule]:
        """Get all rules that match the given files.

        Args:
            files: List of file paths.

        Returns:
            List of matching rules.
        """
        matched_rules: list[RiskRule] = []

        for rule in self.RULES:
            for file_path in files:
                if self._matches_patterns(file_path, rule.patterns):
                    if rule not in matched_rules:
                        matched_rules.append(rule)
                    break

        return matched_rules

    def calculate_risk_level(self, files_changed: list[str]) -> tuple[RiskLevel, str]:
        """Calculate risk level based on changed files.

        The highest risk level among all matched rules is returned.
        If no rules match, MEDIUM is returned as default for code changes.

        Args:
            files_changed: List of changed file paths.

        Returns:
            Tuple of (RiskLevel, reason string).
        """
        if not files_changed:
            return RiskLevel.LOW, "No files changed"

        matched_rules = self._get_matching_rules(files_changed)

        if not matched_rules:
            # Default to MEDIUM for code changes that don't match specific rules
            return RiskLevel.MEDIUM, "Standard code changes (R004)"

        # Check if ALL files are low-risk (tests/docs only)
        all_low_risk = True
        for file_path in files_changed:
            is_low_risk = self._matches_patterns(
                file_path, self.TEST_PATTERNS
            ) or self._matches_patterns(file_path, self.DOCS_PATTERNS)
            if not is_low_risk:
                all_low_risk = False
                break

        if all_low_risk:
            # All files are tests or docs
            rule_ids = [r.id for r in matched_rules if r.level == RiskLevel.LOW]
            return RiskLevel.LOW, f"Low-risk changes only ({', '.join(rule_ids)})"

        # Find highest risk level
        high_rules = [r for r in matched_rules if r.level == RiskLevel.HIGH]
        if high_rules:
            rule_ids = [r.id for r in high_rules]
            descriptions = [r.description for r in high_rules]
            return RiskLevel.HIGH, f"{'; '.join(descriptions)} ({', '.join(rule_ids)})"

        medium_rules = [r for r in matched_rules if r.level == RiskLevel.MEDIUM]
        if medium_rules:
            rule_ids = [r.id for r in medium_rules]
            descriptions = [r.description for r in medium_rules]
            return RiskLevel.MEDIUM, f"{'; '.join(descriptions)} ({', '.join(rule_ids)})"

        # Fallback
        return RiskLevel.MEDIUM, "Standard code changes"

    def get_risk_details(self, files_changed: list[str]) -> dict[str, list[str]]:
        """Get detailed breakdown of files by risk category.

        Args:
            files_changed: List of changed file paths.

        Returns:
            Dictionary mapping risk category to file paths.
        """
        details: dict[str, list[str]] = {
            "high_risk": [],
            "medium_risk": [],
            "low_risk": [],
            "other": [],
        }

        high_patterns = self.DEPENDENCY_PATTERNS + self.SECURITY_PATTERNS + self.INFRA_PATTERNS
        low_patterns = self.TEST_PATTERNS + self.DOCS_PATTERNS

        for file_path in files_changed:
            if self._matches_patterns(file_path, high_patterns):
                details["high_risk"].append(file_path)
            elif self._matches_patterns(file_path, low_patterns):
                details["low_risk"].append(file_path)
            elif self._matches_patterns(file_path, self.CONFIG_PATTERNS):
                details["medium_risk"].append(file_path)
            else:
                details["other"].append(file_path)

        return details
