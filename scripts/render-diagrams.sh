#!/usr/bin/env bash
# Regenerate SVG + PNG for every .mmd file in diagrams/.
# Source of truth is the .mmd file; the .svg and .png next to it are derived
# artifacts checked in for fast README rendering (no client-side mermaid render).
#
# Usage:
#   bash scripts/render-diagrams.sh           # render all
#   bash scripts/render-diagrams.sh FILE.mmd  # render a single file
#
# Locally you need mermaid-cli once: `npm install -g @mermaid-js/mermaid-cli`
# On push, .github/workflows/render-diagrams.yml does this automatically.

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v mmdc >/dev/null 2>&1; then
  echo "❌ mmdc not found. Install with:" >&2
  echo "     npm install -g @mermaid-js/mermaid-cli" >&2
  exit 1
fi

THEME="${MERMAID_THEME:-default}"
BG="${MERMAID_BG:-#ffffff}"

render_one() {
  local mmd="$1"
  local base="${mmd%.mmd}"
  echo "🎨 Rendering ${mmd} → ${base}.{svg,png}"
  mmdc -i "$mmd" -o "${base}.svg" \
       --theme "$THEME" --backgroundColor "$BG"
  mmdc -i "$mmd" -o "${base}.png" \
       --theme "$THEME" --backgroundColor "$BG" \
       --width 1600 --scale 2
}

if [[ $# -gt 0 ]]; then
  render_one "$1"
else
  shopt -s nullglob
  files=(diagrams/*.mmd)
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No .mmd files under diagrams/. Nothing to do."
    exit 0
  fi
  for mmd in "${files[@]}"; do
    render_one "$mmd"
  done
  echo "✅ Done. Rendered ${#files[@]} diagram(s)."
fi
