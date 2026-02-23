"""Threshold-based alert system for sensor readings.

Reads alert rules from dashboard.yaml, evaluates them against incoming
sensor data, and publishes notifications to the event bus. Includes
cooldown logic to prevent alert spam.

Alert rules support:
  - Comparison operators: >, <, >=, <=, ==
  - Severity levels: info, warn, critical
  - Cooldown periods (seconds) to suppress repeated triggers
  - Message templates with {value} and {field} placeholders
"""

import logging
import operator
import re
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Operator mapping for condition strings
OPS = {
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
}

# Parse condition like "> 30" or "< 25.5"
CONDITION_RE = re.compile(r'^\s*(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)\s*$')


class AlertManager:
    """Evaluates sensor readings against configurable alert rules."""

    def __init__(self, rules: List[Dict]):
        self._rules: List[Dict] = []
        self._cooldowns: Dict[str, float] = {}  # {alert_id: last_trigger_time}
        self._active: Dict[str, Dict] = {}  # {alert_id: active alert}

        for rule in rules:
            parsed = self._parse_rule(rule)
            if parsed:
                self._rules.append(parsed)
                logger.info(
                    "Alert rule loaded: %s (%s %s)",
                    parsed['id'], parsed['field'], parsed['condition_str'],
                )

    def _parse_rule(self, rule: Dict) -> Optional[Dict]:
        """Parse and validate an alert rule from YAML config."""
        alert_id = rule.get('id')
        field = rule.get('field')
        condition_str = rule.get('condition', '')

        if not alert_id or not field or not condition_str:
            logger.warning("Skipping incomplete alert rule: %s", rule)
            return None

        match = CONDITION_RE.match(condition_str)
        if not match:
            logger.warning("Invalid condition '%s' in alert %s", condition_str, alert_id)
            return None

        op_str, threshold_str = match.groups()

        return {
            'id': alert_id,
            'field': field,
            'condition_str': condition_str,
            'op': OPS[op_str],
            'threshold': float(threshold_str),
            'level': rule.get('level', 'info'),
            'message': rule.get('message', f'{field} alert: {{value}}'),
            'cooldown': rule.get('cooldown', 300),
        }

    def check(self, field: str, value: float) -> List[Dict]:
        """Check a sensor value against all rules for that field.

        Returns a list of triggered alert dicts (may be empty).
        """
        triggered = []

        for rule in self._rules:
            if rule['field'] != field:
                continue

            is_triggered = rule['op'](value, rule['threshold'])

            if is_triggered and self._can_trigger(rule):
                alert = {
                    'id': rule['id'],
                    'level': rule['level'],
                    'field': field,
                    'value': value,
                    'message': rule['message'].format(value=value, field=field),
                    'timestamp': time.time(),
                }
                self._cooldowns[rule['id']] = time.time()
                self._active[rule['id']] = alert
                triggered.append(alert)
                logger.info("Alert triggered: %s — %s", rule['id'], alert['message'])

            elif not is_triggered and rule['id'] in self._active:
                # Condition cleared
                del self._active[rule['id']]

        return triggered

    def _can_trigger(self, rule: Dict) -> bool:
        """Check if an alert has passed its cooldown period."""
        last_triggered = self._cooldowns.get(rule['id'], 0)
        return (time.time() - last_triggered) >= rule['cooldown']

    def get_active_alerts(self) -> List[Dict]:
        """Return all currently active (uncleared) alerts."""
        return list(self._active.values())
