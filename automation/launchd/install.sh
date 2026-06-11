#!/bin/bash
# Устанавливает все launchd-агенты JARVIS из этой папки в ~/Library/LaunchAgents и грузит их.
# Запуск: bash automation/launchd/install.sh [label]   (без аргумента — все)
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="$HOME/Library/LaunchAgents"
GUI="gui/$(id -u)"
mkdir -p "$DST" "$HOME/Projects/jarvis/logs"
for plist in "$SRC"/com.jarvis.*.plist; do
    label="$(basename "$plist" .plist)"
    [ -n "$1" ] && [ "$1" != "$label" ] && continue
    cp "$plist" "$DST/"
    launchctl bootout "$GUI/$label" 2>/dev/null || true
    launchctl bootstrap "$GUI" "$DST/$label.plist" && echo "✅ загружен $label" || echo "⚠️ $label"
done
