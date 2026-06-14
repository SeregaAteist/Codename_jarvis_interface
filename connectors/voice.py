"""Voice connector — proxy to hud/voice module."""

import os
import sys

_HUD_PATH = os.path.join(os.path.dirname(__file__), "..", "hud")
if _HUD_PATH not in sys.path:
    sys.path.insert(0, _HUD_PATH)

from voice import listener
from voice.silero_speaker import speak, stop

__all__ = ["listener", "speak", "stop"]
