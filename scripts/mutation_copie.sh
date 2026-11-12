#!/usr/bin/env bash
# Copie l'arbre de travail (sans .git) dans un dossier jetable pour y appliquer
# un mutant sans jamais toucher l'arbre réel.
#
# Usage : bash scripts/mutation_copie.sh <destination>
set -euo pipefail
DEST="$1"
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "$DEST"
mkdir -p "$DEST"
for entree in src tests eval demo scenarios regles schemas pyproject.toml scripts; do
  if [ -e "$RACINE/$entree" ]; then
    cp -r "$RACINE/$entree" "$DEST/"
  fi
done
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "$DEST"
