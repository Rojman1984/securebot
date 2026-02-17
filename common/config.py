#!/usr/bin/env python3
"""
Configuration Management
Loads user configuration from ~/.securebot/config.yml with fallback to defaults

Author: SecureBot Project
License: MIT
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages user configuration with defaults"""

    DEFAULT_CONFIG = {
        "skills": {
            "enabled_skills": None,  # None means all enabled
            "disabled_skills": [],
            "search_priority": {
                "search-google": 1,
                "search-tavily": 2,
                "search-duckduckgo": 3
            }
        },
        "gateway": {
            "search_detection": "normal",
            "max_search_results": 3
        },
        "vault": {
            "rate_limits": {
                "google": {
                    "daily": 100,
                    "monthly": 3000
                },
                "tavily": {
                    "monthly": 1000
                }
            }
        },
        "orchestrator": {
            "skill_creation": "normal",
            "ollama_model": "phi4-mini:3.8b",
            "claude_model": "claude-sonnet-4-20250514"
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to config file. If None, checks:
                        1. ~/.securebot/config.yml
                        2. /home/tasker0/securebot/config/config.yml
                        3. Falls back to defaults
        """
        self.config = self.DEFAULT_CONFIG.copy()

        if config_path:
            self._load_config(config_path)
        else:
            # Try user config first
            user_config = Path.home() / ".securebot" / "config.yml"
            if user_config.exists():
                self._load_config(str(user_config))
                logger.info(f"Loaded user config from {user_config}")
            else:
                # Try project config
                project_config = Path("/home/tasker0/securebot/config/config.yml")
                if project_config.exists():
                    self._load_config(str(project_config))
                    logger.info(f"Loaded project config from {project_config}")
                else:
                    logger.info("No config file found, using defaults")

    def _load_config(self, config_path: str) -> None:
        """Load and merge configuration from file"""
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f) or {}

            # Deep merge with defaults
            self.config = self._deep_merge(self.DEFAULT_CONFIG, user_config)

        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            logger.warning("Using default configuration")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            path: Dot-separated path (e.g., 'skills.search_priority')
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        keys = path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def is_skill_enabled(self, skill_name: str) -> bool:
        """
        Check if a skill is enabled

        Args:
            skill_name: Name of the skill

        Returns:
            True if skill is enabled
        """
        # Check disabled list first
        disabled = self.get("skills.disabled_skills", [])
        if skill_name in disabled:
            return False

        # Check enabled list
        enabled = self.get("skills.enabled_skills")
        if enabled is None:
            # None means all enabled (except disabled)
            return True

        return skill_name in enabled

    def get_skill_priority(self, skill_name: str, default: int = 999) -> int:
        """
        Get priority for a skill

        Args:
            skill_name: Name of the skill
            default: Default priority if not specified

        Returns:
            Priority number (lower = higher priority)
        """
        return self.get(f"skills.search_priority.{skill_name}", default)

    def get_rate_limit(self, provider: str, limit_type: str) -> Optional[int]:
        """
        Get rate limit for a provider

        Args:
            provider: Provider name (e.g., 'google', 'tavily')
            limit_type: Type of limit ('daily' or 'monthly')

        Returns:
            Rate limit value or None
        """
        return self.get(f"vault.rate_limits.{provider}.{limit_type}")


# Global config instance
_config_instance = None


def get_config() -> ConfigManager:
    """Get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> ConfigManager:
    """Reload configuration from file"""
    global _config_instance
    _config_instance = ConfigManager(config_path)
    return _config_instance
