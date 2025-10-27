"""Simple event hook system for notifications and extensibility."""

import logging
import subprocess
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)


class HookManager:
    """Manages event hooks for CLI notifications."""

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}

    def register(self, event: str, callback: Callable):
        """
        Register a callback for an event.

        Args:
            event: Event name (e.g., 'sync_complete', 'sync_error')
            callback: Function to call when event fires
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
        logger.debug(f"Registered hook for event: {event}")

    def trigger(self, event: str, **kwargs):
        """
        Trigger all callbacks for an event.

        Args:
            event: Event name
            **kwargs: Arguments to pass to callbacks
        """
        if event not in self._hooks:
            return

        logger.debug(f"Triggering event: {event}")
        for callback in self._hooks[event]:
            try:
                callback(**kwargs)
            except Exception as e:
                logger.error(f"Hook callback failed for {event}: {e}")

    def load_from_config(self, config):
        """
        Load hooks from configuration.

        Expected config format:
        hooks:
          sync_complete:
            - type: command
              command: "notify-send 'Sync complete'"
            - type: webhook
              url: "https://..."
          sync_error:
            - type: command
              command: "notify-send 'Sync failed'"

        Args:
            config: Config object
        """
        hooks_config = config.get("hooks", {})

        for event, hook_configs in hooks_config.items():
            if not isinstance(hook_configs, list):
                continue

            for hook_config in hook_configs:
                hook_type = hook_config.get("type")

                if hook_type == "command":
                    command = hook_config.get("command")
                    if command:
                        self.register(event, self._create_command_hook(command))

                elif hook_type == "webhook":
                    url = hook_config.get("url")
                    if url:
                        self.register(event, self._create_webhook_hook(url))

    def _create_command_hook(self, command: str) -> Callable:
        """Create a command execution hook."""
        def hook(**kwargs):
            try:
                subprocess.run(command, shell=True, check=False, capture_output=True)
                logger.debug(f"Executed hook command: {command}")
            except Exception as e:
                logger.error(f"Failed to execute hook command: {e}")
        return hook

    def _create_webhook_hook(self, url: str) -> Callable:
        """Create a webhook HTTP POST hook."""
        def hook(**kwargs):
            try:
                import requests
                requests.post(url, json=kwargs, timeout=5)
                logger.debug(f"Sent webhook to: {url}")
            except ImportError:
                logger.warning("requests library not installed, webhook skipped")
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")
        return hook


# Global hook manager instance
_hook_manager = HookManager()


def get_hook_manager() -> HookManager:
    """Get the global hook manager instance."""
    return _hook_manager


def register_hook(event: str, callback: Callable):
    """Convenience function to register a hook."""
    _hook_manager.register(event, callback)


def trigger_hook(event: str, **kwargs):
    """Convenience function to trigger a hook."""
    _hook_manager.trigger(event, **kwargs)
