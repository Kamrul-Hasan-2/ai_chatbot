"""
Business Rule Engine: Core logic processing
Part of BDStall Chatbot System Architecture

This module handles:
- Business logic rules and policies
- Decision making based on business rules
- Rule evaluation and execution
- Dynamic rule management
- Business context validation
"""
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
from datetime import datetime, time
import json
import re
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RuleType(Enum):
    """Types of business rules"""
    BUSINESS_HOURS = "business_hours"
    PRODUCT_AVAILABILITY = "product_availability"
    PRICING_RULES = "pricing_rules"
    CUSTOMER_ELIGIBILITY = "customer_eligibility"
    ORDER_VALIDATION = "order_validation"
    ESCALATION_RULES = "escalation_rules"
    RESPONSE_FILTERING = "response_filtering"
    PROMOTIONAL_RULES = "promotional_rules"
    INVENTORY_RULES = "inventory_rules"
    GEOGRAPHIC_RULES = "geographic_rules"


class RulePriority(Enum):
    """Priority levels for rules"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class RuleStatus(Enum):
    """Status of rules"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"


@dataclass
class RuleCondition:
    """Represents a condition that must be met for a rule"""
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, in, not_in, contains, regex
    value: Any
    description: Optional[str] = None
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate if condition is met"""
        try:
            field_value = self._get_nested_value(data, self.field)
            
            if self.operator == "eq":
                return field_value == self.value
            elif self.operator == "ne":
                return field_value != self.value
            elif self.operator == "gt":
                return field_value > self.value
            elif self.operator == "lt":
                return field_value < self.value
            elif self.operator == "gte":
                return field_value >= self.value
            elif self.operator == "lte":
                return field_value <= self.value
            elif self.operator == "in":
                return field_value in self.value
            elif self.operator == "not_in":
                return field_value not in self.value
            elif self.operator == "contains":
                return self.value in str(field_value)
            elif self.operator == "regex":
                return bool(re.search(self.value, str(field_value), re.IGNORECASE))
            else:
                logger.warning(f"Unknown operator: {self.operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating condition {self.field} {self.operator} {self.value}: {e}")
            return False
    
    def _get_nested_value(self, data: Dict, field: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        try:
            keys = field.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None


@dataclass
class RuleAction:
    """Action to be taken when rule conditions are met"""
    action_type: str  # set, append, remove, calculate, redirect, escalate
    target: str
    value: Any
    parameters: Optional[Dict] = None
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the rule action"""
        try:
            result = context.copy()
            
            if self.action_type == "set":
                self._set_nested_value(result, self.target, self.value)
            elif self.action_type == "append":
                current = self._get_nested_value(result, self.target) or []
                if isinstance(current, list):
                    current.append(self.value)
                    self._set_nested_value(result, self.target, current)
            elif self.action_type == "calculate":
                # Simple calculation support
                if self.parameters and "formula" in self.parameters:
                    calculated_value = self._calculate_formula(
                        self.parameters["formula"], result
                    )
                    self._set_nested_value(result, self.target, calculated_value)
            elif self.action_type == "redirect":
                result["_redirect"] = self.value
            elif self.action_type == "escalate":
                result["_escalate"] = {
                    "reason": self.value,
                    "priority": self.parameters.get("priority", "medium"),
                    "department": self.parameters.get("department", "customer_service")
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing action {self.action_type}: {e}")
            return context
    
    def _get_nested_value(self, data: Dict, field: str) -> Any:
        """Get value from nested dictionary"""
        try:
            keys = field.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None
    
    def _set_nested_value(self, data: Dict, field: str, value: Any):
        """Set value in nested dictionary"""
        try:
            keys = field.split('.')
            current = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value
        except Exception as e:
            logger.error(f"Error setting nested value {field}: {e}")
    
    def _calculate_formula(self, formula: str, context: Dict) -> Any:
        """Simple formula calculation (security-conscious)"""
        try:
            # Only allow basic math operations for security
            allowed_ops = {'+', '-', '*', '/', '(', ')', '.', ' '}
            allowed_funcs = {'min', 'max', 'abs', 'round'}
            
            # Replace variables with values
            for key, value in context.items():
                if isinstance(value, (int, float)):
                    formula = formula.replace(f'{{{key}}}', str(value))
            
            # Basic validation
            if not all(c.isdigit() or c in allowed_ops for c in formula.replace(' ', '')):
                return 0
            
            # Evaluate safely (limited scope)
            try:
                return eval(formula, {"__builtins__": {}}, {})
            except:
                return 0
        except Exception:
            return 0


class BusinessRule:
    """Represents a business rule"""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        rule_type: RuleType,
        conditions: List[RuleCondition],
        actions: List[RuleAction],
        priority: RulePriority = RulePriority.MEDIUM,
        status: RuleStatus = RuleStatus.ACTIVE,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        self.rule_id = rule_id
        self.name = name
        self.rule_type = rule_type
        self.conditions = conditions
        self.actions = actions
        self.priority = priority
        self.status = status
        self.description = description or ""
        self.tags = tags or []
        
        self.created_at = datetime.now()
        self.last_modified = datetime.now()
        self.execution_count = 0
        self.success_count = 0
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate if all conditions are met"""
        try:
            if self.status != RuleStatus.ACTIVE:
                return False
            
            # All conditions must be true (AND logic)
            for condition in self.conditions:
                if not condition.evaluate(context):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating rule {self.rule_id}: {e}")
            return False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute rule actions if conditions are met"""
        try:
            self.execution_count += 1
            
            if not self.evaluate(context):
                return context
            
            # Execute all actions
            result = context.copy()
            for action in self.actions:
                result = action.execute(result)
            
            self.success_count += 1
            self.last_modified = datetime.now()
            
            logger.info(f"Executed rule: {self.name}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing rule {self.rule_id}: {e}")
            return context
    
    def get_success_rate(self) -> float:
        """Get rule success rate"""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count
    
    def to_dict(self) -> Dict:
        """Convert rule to dictionary"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "rule_type": self.rule_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "description": self.description,
            "tags": self.tags,
            "conditions_count": len(self.conditions),
            "actions_count": len(self.actions),
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "success_rate": self.get_success_rate(),
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat()
        }


class BusinessRuleEngine:
    """
    Core business rule engine for processing business logic
    """
    
    def __init__(
        self,
        config_file: Optional[str] = None
    ):
        self.rules: Dict[str, BusinessRule] = {}
        self.rule_groups: Dict[RuleType, List[str]] = {}
        
        # Load default business rules
        self._load_default_rules()
        
        # Load custom rules from config if provided
        if config_file:
            self._load_rules_from_config(config_file)
        
        logger.info("Business Rule Engine initialized")
    
    def _load_default_rules(self):
        """Load default business rules"""
        
        # Business Hours Rule
        business_hours_rule = BusinessRule(
            rule_id="business_hours_check",
            name="Business Hours Validation",
            rule_type=RuleType.BUSINESS_HOURS,
            conditions=[
                RuleCondition("current_time.hour", "gte", 9),
                RuleCondition("current_time.hour", "lt", 18),
                RuleCondition("current_time.weekday", "lt", 5)  # Monday=0, Sunday=6
            ],
            actions=[
                RuleAction("set", "business_context.is_business_hours", True),
                RuleAction("set", "response_context.can_process_orders", True)
            ],
            priority=RulePriority.HIGH,
            description="Check if request is during business hours"
        )
        
        # After Hours Rule
        after_hours_rule = BusinessRule(
            rule_id="after_hours_check",
            name="After Hours Response",
            rule_type=RuleType.BUSINESS_HOURS,
            conditions=[
                RuleCondition("current_time.hour", "lt", 9),
                RuleCondition("current_time.hour", "gte", 18)
            ],
            actions=[
                RuleAction("set", "business_context.is_business_hours", False),
                RuleAction("set", "response_context.after_hours_message", 
                          "আমাদের অফিস সময়: সকাল ৯টা - সন্ধ্যা ৬টা। অফিস সময়ে যোগাযোগ করুন।"),
                RuleAction("set", "response_context.can_process_orders", False)
            ],
            priority=RulePriority.HIGH,
            description="Handle after hours requests"
        )
        
        # High Value Customer Rule
        vip_customer_rule = BusinessRule(
            rule_id="vip_customer_priority",
            name="VIP Customer Priority",
            rule_type=RuleType.CUSTOMER_ELIGIBILITY,
            conditions=[
                RuleCondition("user_context.total_orders", "gte", 10),
                RuleCondition("user_context.total_spent", "gte", 50000)
            ],
            actions=[
                RuleAction("set", "customer_context.is_vip", True),
                RuleAction("set", "response_context.priority_support", True),
                RuleAction("set", "response_context.discount_eligible", True)
            ],
            priority=RulePriority.HIGH,
            description="Identify and prioritize VIP customers"
        )
        
        # Complex Query Escalation Rule
        escalation_rule = BusinessRule(
            rule_id="complex_query_escalation",
            name="Complex Query Escalation",
            rule_type=RuleType.ESCALATION_RULES,
            conditions=[
                RuleCondition("message_context.complexity_score", "gt", 0.8),
                RuleCondition("conversation_context.turn_count", "gt", 5),
                RuleCondition("intent_context.confidence", "lt", 0.6)
            ],
            actions=[
                RuleAction("escalate", "Complex technical query requiring human assistance", {
                    "priority": "high",
                    "department": "technical_support",
                    "estimated_wait": "5-10 minutes"
                })
            ],
            priority=RulePriority.CRITICAL,
            description="Escalate complex queries to human agents"
        )
        
        # Product Availability Rule
        product_availability_rule = BusinessRule(
            rule_id="product_availability_check",
            name="Product Availability Validation",
            rule_type=RuleType.PRODUCT_AVAILABILITY,
            conditions=[
                RuleCondition("product_context.stock_quantity", "gt", 0),
                RuleCondition("product_context.is_active", "eq", True)
            ],
            actions=[
                RuleAction("set", "product_context.available", True),
                RuleAction("set", "response_context.show_price", True),
                RuleAction("set", "response_context.show_order_button", True)
            ],
            priority=RulePriority.HIGH,
            description="Check product availability and set response context"
        )
        
        # Add rules to engine
        rules = [
            business_hours_rule,
            after_hours_rule,
            vip_customer_rule,
            escalation_rule,
            product_availability_rule
        ]
        
        for rule in rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: BusinessRule):
        """Add a business rule to the engine"""
        try:
            self.rules[rule.rule_id] = rule
            
            # Add to rule groups
            if rule.rule_type not in self.rule_groups:
                self.rule_groups[rule.rule_type] = []
            
            if rule.rule_id not in self.rule_groups[rule.rule_type]:
                self.rule_groups[rule.rule_type].append(rule.rule_id)
            
            logger.info(f"Added business rule: {rule.name}")
            
        except Exception as e:
            logger.error(f"Error adding rule {rule.rule_id}: {e}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a business rule"""
        try:
            if rule_id in self.rules:
                rule = self.rules[rule_id]
                
                # Remove from rule groups
                if rule.rule_type in self.rule_groups:
                    if rule_id in self.rule_groups[rule.rule_type]:
                        self.rule_groups[rule.rule_type].remove(rule_id)
                
                # Remove the rule
                del self.rules[rule_id]
                logger.info(f"Removed business rule: {rule_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing rule {rule_id}: {e}")
            return False
    
    def execute_rules(
        self,
        context: Dict[str, Any],
        rule_types: Optional[List[RuleType]] = None,
        priority_filter: Optional[RulePriority] = None
    ) -> Dict[str, Any]:
        """
        Execute business rules on given context
        
        Args:
            context: Current context data
            rule_types: Optional filter for rule types
            priority_filter: Optional priority filter
            
        Returns:
            Updated context after rule execution
        """
        try:
            # Add current time context
            now = datetime.now()
            if "current_time" not in context:
                context["current_time"] = {
                    "hour": now.hour,
                    "minute": now.minute,
                    "weekday": now.weekday(),  # Monday=0
                    "timestamp": now.timestamp()
                }
            
            # Get applicable rules
            applicable_rules = self._get_applicable_rules(context, rule_types, priority_filter)
            
            # Execute rules in priority order
            result = context.copy()
            executed_rules = []
            
            for rule in applicable_rules:
                try:
                    updated_context = rule.execute(result)
                    if updated_context != result:  # Rule made changes
                        result = updated_context
                        executed_rules.append(rule.rule_id)
                except Exception as e:
                    logger.error(f"Error executing rule {rule.rule_id}: {e}")
            
            # Add execution metadata
            result["_rule_execution"] = {
                "executed_rules": executed_rules,
                "execution_time": datetime.now().isoformat(),
                "rules_evaluated": len(applicable_rules)
            }
            
            logger.info(f"Executed {len(executed_rules)} business rules")
            return result
            
        except Exception as e:
            logger.error(f"Error executing rules: {e}")
            return context
    
    def _get_applicable_rules(
        self,
        context: Dict[str, Any],
        rule_types: Optional[List[RuleType]] = None,
        priority_filter: Optional[RulePriority] = None
    ) -> List[BusinessRule]:
        """Get applicable rules based on filters"""
        try:
            applicable_rules = []
            
            for rule in self.rules.values():
                # Filter by rule type
                if rule_types and rule.rule_type not in rule_types:
                    continue
                
                # Filter by priority
                if priority_filter and rule.priority != priority_filter:
                    continue
                
                # Only active rules
                if rule.status != RuleStatus.ACTIVE:
                    continue
                
                applicable_rules.append(rule)
            
            # Sort by priority (critical first)
            priority_order = [
                RulePriority.CRITICAL,
                RulePriority.HIGH,
                RulePriority.MEDIUM,
                RulePriority.LOW
            ]
            
            applicable_rules.sort(
                key=lambda r: priority_order.index(r.priority)
            )
            
            return applicable_rules
            
        except Exception as e:
            logger.error(f"Error getting applicable rules: {e}")
            return []
    
    def validate_business_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate business context and add business-specific information"""
        try:
            # Execute business validation rules
            validated_context = self.execute_rules(
                context,
                rule_types=[
                    RuleType.BUSINESS_HOURS,
                    RuleType.CUSTOMER_ELIGIBILITY,
                    RuleType.PRODUCT_AVAILABILITY
                ]
            )
            
            # Add business validation results
            validation_results = {
                "is_valid_business_request": True,
                "business_hours_status": validated_context.get("business_context", {}).get("is_business_hours", True),
                "customer_status": "regular",
                "validation_timestamp": datetime.now().isoformat()
            }
            
            # Update customer status
            if validated_context.get("customer_context", {}).get("is_vip"):
                validation_results["customer_status"] = "vip"
            
            # Check for escalation needs
            if "_escalate" in validated_context:
                validation_results["requires_escalation"] = True
                validation_results["escalation_info"] = validated_context["_escalate"]
            
            validated_context["business_validation"] = validation_results
            
            return validated_context
            
        except Exception as e:
            logger.error(f"Error validating business context: {e}")
            context["business_validation"] = {"error": str(e)}
            return context
    
    def get_rule_by_id(self, rule_id: str) -> Optional[BusinessRule]:
        """Get rule by ID"""
        return self.rules.get(rule_id)
    
    def get_rules_by_type(self, rule_type: RuleType) -> List[BusinessRule]:
        """Get all rules of specific type"""
        try:
            rule_ids = self.rule_groups.get(rule_type, [])
            return [self.rules[rule_id] for rule_id in rule_ids if rule_id in self.rules]
        except Exception as e:
            logger.error(f"Error getting rules by type {rule_type}: {e}")
            return []
    
    def update_rule_status(self, rule_id: str, status: RuleStatus) -> bool:
        """Update rule status"""
        try:
            if rule_id in self.rules:
                self.rules[rule_id].status = status
                self.rules[rule_id].last_modified = datetime.now()
                logger.info(f"Updated rule {rule_id} status to {status.value}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating rule status: {e}")
            return False
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        try:
            stats = {
                "total_rules": len(self.rules),
                "rules_by_type": {},
                "rules_by_status": {},
                "rules_by_priority": {},
                "execution_stats": {
                    "total_executions": sum(rule.execution_count for rule in self.rules.values()),
                    "total_successes": sum(rule.success_count for rule in self.rules.values()),
                    "average_success_rate": 0.0
                }
            }
            
            # Count by type, status, priority
            for rule in self.rules.values():
                # By type
                rule_type = rule.rule_type.value
                stats["rules_by_type"][rule_type] = stats["rules_by_type"].get(rule_type, 0) + 1
                
                # By status
                status = rule.status.value
                stats["rules_by_status"][status] = stats["rules_by_status"].get(status, 0) + 1
                
                # By priority
                priority = rule.priority.value
                stats["rules_by_priority"][priority] = stats["rules_by_priority"].get(priority, 0) + 1
            
            # Calculate average success rate
            if self.rules:
                total_success_rate = sum(rule.get_success_rate() for rule in self.rules.values())
                stats["execution_stats"]["average_success_rate"] = total_success_rate / len(self.rules)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting engine stats: {e}")
            return {"error": str(e)}
    
    def _load_rules_from_config(self, config_file: str):
        """Load rules from configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for rule_data in config.get("rules", []):
                # Parse rule from config
                # This would need more implementation for full config support
                logger.info(f"Loading rule from config: {rule_data.get('name', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error loading rules from config {config_file}: {e}")


if __name__ == "__main__":
    # Test the Business Rule Engine
    engine = BusinessRuleEngine()
    
    # Test context
    test_context = {
        "user_context": {
            "user_id": "user123",
            "total_orders": 15,
            "total_spent": 75000
        },
        "message_context": {
            "message": "Do you have iPhone 13 in stock?",
            "complexity_score": 0.3
        },
        "intent_context": {
            "intent": "product_inquiry",
            "confidence": 0.85
        },
        "conversation_context": {
            "turn_count": 2
        },
        "product_context": {
            "product_id": "iphone13",
            "stock_quantity": 25,
            "is_active": True,
            "price": 85000
        }
    }
    
    print("Testing Business Rule Engine:")
    print("=" * 50)
    
    # Execute rules
    result = engine.execute_rules(test_context)
    
    print("Rule Execution Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    print("\nEngine Stats:")
    print(json.dumps(engine.get_engine_stats(), indent=2))