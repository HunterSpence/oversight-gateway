"""Configuration management for Oversight Gateway"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class RiskThresholds:
    """Risk threshold configuration"""
    checkpoint_trigger: float = 0.6
    session_budget: float = 0.8


@dataclass
class ActionRule:
    """Rule for specific action patterns"""
    pattern: str
    impact_floor: float
    always_checkpoint: bool = False
    metadata_boosts: Dict[str, float] = field(default_factory=dict)
    description: str = ""


@dataclass
class CompoundDetection:
    """Compound action detection configuration"""
    time_window_seconds: int = 300
    same_resource_boost: float = 0.2
    min_count: int = 2


@dataclass
class NearMissConfig:
    """Near-miss learning configuration"""
    half_life_hours: float = 24.0
    max_multiplier: float = 2.0
    min_severity: float = 0.1


@dataclass
class ApprovalConfig:
    """Approval workflow configuration"""
    auto_approve_timeout: int = 0
    require_notes: bool = False
    max_pending_per_session: int = 10


@dataclass
class PolicyConfig:
    """Complete policy configuration"""
    risk_thresholds: RiskThresholds
    action_rules: List[ActionRule]
    compound_detection: CompoundDetection
    near_miss: NearMissConfig
    approval: ApprovalConfig
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyConfig":
        """Load policy from dictionary"""
        return cls(
            risk_thresholds=RiskThresholds(**data.get("risk_thresholds", {})),
            action_rules=[
                ActionRule(**rule) for rule in data.get("action_rules", [])
            ],
            compound_detection=CompoundDetection(**data.get("compound_detection", {})),
            near_miss=NearMissConfig(**data.get("near_miss", {})),
            approval=ApprovalConfig(**data.get("approval", {})),
        )
    
    @classmethod
    def from_yaml(cls, path: Path) -> "PolicyConfig":
        """Load policy from YAML file"""
        logger.info("loading_policy", path=str(path))
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def get_action_rule(self, action: str) -> Optional[ActionRule]:
        """Get rule for specific action (pattern matching)"""
        for rule in self.action_rules:
            # Simple pattern matching (supports * wildcard)
            pattern = rule.pattern.replace("*", ".*")
            import re
            if re.match(pattern, action, re.IGNORECASE):
                return rule
        return None


class Config:
    """Global configuration manager"""
    
    def __init__(self, policy_path: Optional[Path] = None):
        self.policy_path = policy_path or self._default_policy_path()
        self.policy = self.load_policy()
        self.database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./oversight_gateway.db")
        self.otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
        self.service_name = os.getenv("SERVICE_NAME", "oversight-gateway")
    
    @staticmethod
    def _default_policy_path() -> Path:
        """Get default policy path"""
        base = Path(__file__).parent.parent
        return base / "policies" / "default.yaml"
    
    def load_policy(self) -> PolicyConfig:
        """Load or reload policy configuration"""
        return PolicyConfig.from_yaml(self.policy_path)
    
    def reload_policy(self) -> None:
        """Hot-reload policy configuration"""
        logger.info("reloading_policy")
        self.policy = self.load_policy()


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> None:
    """Reload configuration"""
    get_config().reload_policy()
