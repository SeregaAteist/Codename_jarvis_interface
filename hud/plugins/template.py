"""
Jarvis plugin template.
Copy this file, fill in the fields, and drop in ~/jarvis/plugins/.
Jarvis auto-discovers .py files in that directory on startup.
"""

PLUGIN_META = {
    "name":        "my_plugin",
    "description": "What this plugin does",
    "version":     "1.0",
    "author":      "Sergey",
    "triggers":    ["keyword1", "keyword2"],
    "requires":    [],   # pip packages, e.g. ["requests"]
}


def handler(text: str) -> str:
    """Receives the user's full text, returns Jarvis reply."""
    return f"Plugin '{PLUGIN_META['name']}' processed: {text}"


def setup() -> bool:
    """Called once on load. Return True to activate, False to abort."""
    return True
