#!/bin/bash
# Устанавливает git-хуки JARVIS в .git/hooks (хуки не версионируются автоматически).
# Запуск: bash automation/git-hooks/install.sh
set -e
ROOT="$(git rev-parse --show-toplevel)"
cp "$ROOT/automation/git-hooks/pre-commit"  "$ROOT/.git/hooks/pre-commit"
cp "$ROOT/automation/git-hooks/post-commit" "$ROOT/.git/hooks/post-commit"
chmod +x "$ROOT/.git/hooks/pre-commit" "$ROOT/.git/hooks/post-commit"
echo "✅ Хуки установлены: pre-commit (сканер секретов) + post-commit (автопуш)"
