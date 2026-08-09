"""
Agent Message Protocol & Router (Task 2.1)
Standardized message-passing between agents, with routing and audit logging.
"""
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from utils.agent_logger import AgentLogger

# Known agents in the system. Populated by each agent module on import via register().
AGENT_REGISTRY: Dict[str, Callable] = {}

_router_logger = AgentLogger("MessageRouter")


def register_agent(name: str, handler: Callable):
    """Register an agent's inbound message handler: handler(message: dict) -> dict"""
    AGENT_REGISTRY[name] = handler


def make_message(sender: str, recipient: str, msg_type: str, payload: Any) -> Dict:
    """Standardized message format used by all agent communication."""
    return {
        "sender": sender,
        "recipient": recipient,
        "type": msg_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class MessageRouter:
    """Routes messages between registered agents and logs every exchange."""

    def __init__(self):
        self.registry = AGENT_REGISTRY
        self.history: List[Dict] = []

    def send(self, sender: str, recipient: str, msg_type: str, payload: Any) -> Optional[Dict]:
        """Send a message to one agent and return its response (or None if unroutable)."""
        message = make_message(sender, recipient, msg_type, payload)
        self.history.append(message)

        handler = self.registry.get(recipient)
        if not handler:
            _router_logger.log_action(
                "send", input_data=message, success=False,
                error_message=f"No handler registered for '{recipient}'", level="WARNING",
            )
            return None

        start = datetime.now(timezone.utc)
        try:
            response = handler(message)
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            _router_logger.log_action(
                f"route:{sender}->{recipient}:{msg_type}",
                input_data={"type": msg_type}, output_data={"ok": True},
                success=True, execution_time_ms=elapsed_ms, level="DEBUG",
            )
            return response
        except Exception as e:
            _router_logger.log_action(
                f"route:{sender}->{recipient}:{msg_type}",
                input_data={"type": msg_type}, success=False,
                error_message=str(e), level="ERROR",
            )
            return None

    def broadcast(self, sender: str, msg_type: str, payload: Any, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send a message to every registered agent except sender/excluded. Returns {agent: response}."""
        exclude = set(exclude or []) | {sender}
        results = {}
        for name in list(self.registry.keys()):
            if name in exclude:
                continue
            results[name] = self.send(sender, name, msg_type, payload)
        return results

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self.history[-limit:]


# Singleton router shared across the pipeline
router = MessageRouter()
