#!/usr/bin/env bash
#
# Build the memoria (TFG report) as a single PDF from the per-chapter Markdown
# files in this directory.
#
# Toolchain:
#   - pandoc            (brew install pandoc)
#   - tectonic          (brew install tectonic)   -- XeTeX engine, self-fetching
#   - @mermaid-js/mermaid-cli via npx             -- renders ```mermaid blocks
#   - Google Chrome                               -- headless backend for mermaid-cli
#
# Mermaid blocks are pre-rendered to vector PDF and spliced in as images, because
# pandoc has no native Mermaid support. Everything else is plain Pandoc Markdown.
#
# Output: memoria/memoria.pdf  (git-ignored)
#
set -euo pipefail

cd "$(dirname "$0")"

MAINFONT="${MEMORIA_MAINFONT:-Times New Roman}"
CHROME="${MEMORIA_CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
MERMAID_CLI="@mermaid-js/mermaid-cli@11"
OUT="memoria.pdf"

for bin in pandoc tectonic npx; do
  command -v "$bin" >/dev/null || { echo "ERROR: '$bin' not found on PATH." >&2; exit 1; }
done
[ -x "$CHROME" ] || { echo "ERROR: Chrome not found at: $CHROME (set MEMORIA_CHROME)." >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/puppeteer.json" <<EOF
{ "executablePath": "$CHROME", "args": ["--no-sandbox"] }
EOF

# Collect chapters: NN-name.md, numerically sorted.
shopt -s nullglob
chapters=( [0-9][0-9]-*.md )
shopt -u nullglob
[ ${#chapters[@]} -gt 0 ] || { echo "ERROR: no NN-*.md chapter files here." >&2; exit 1; }
echo "Chapters: ${chapters[*]}"

# Pre-render every ```mermaid block to a cropped vector PDF, rewrite the fence to
# an image include. Diagram files land in $TMP; image paths are absolute.
n_diag=0
render_mermaid() {
  local src="$1" dst="$2" base
  base="$(basename "${src%.md}")"
  awk -v tmp="$TMP" -v base="$base" '
    BEGIN { inblk = 0; idx = 0 }
    /^```mermaid[[:space:]]*$/ { inblk = 1; idx++; mmd = tmp "/" base "-" idx ".mmd"; printf "" > mmd; next }
    inblk && /^```[[:space:]]*$/ {
      inblk = 0
      close(mmd)
      pdf = tmp "/" base "-" idx ".pdf"
      print "%%MERMAID%%" mmd "%%" pdf
      next
    }
    inblk { print $0 >> mmd; next }
    { print }
  ' "$src" > "$dst.stage"

  : > "$dst"
  while IFS= read -r line; do
    case "$line" in
      %%MERMAID%%*)
        local rest="${line#%%MERMAID%%}"
        local mmd="${rest%%%%*}"
        local pdf="${rest#*%%}"
        npx -y "$MERMAID_CLI" -i "$mmd" -o "$pdf" -p "$TMP/puppeteer.json" -f -w 1400 \
          >/dev/null 2>&1
        printf '\n![](%s){width=75%%}\n' "$pdf" >> "$dst"
        n_diag=$((n_diag + 1))
        ;;
      *) printf '%s\n' "$line" >> "$dst" ;;
    esac
  done < "$dst.stage"
  rm -f "$dst.stage"
}

merged="$TMP/memoria.md"
: > "$merged"
for ch in "${chapters[@]}"; do
  echo "  pre-processing $ch"
  render_mermaid "$ch" "$TMP/$(basename "$ch")"
  cat "$TMP/$(basename "$ch")" >> "$merged"
  printf '\n\n\\newpage\n\n' >> "$merged"
done
echo "Rendered $n_diag mermaid diagram(s)."

echo "Running pandoc + tectonic ..."
if ! pandoc "$merged" \
  -o "$OUT" \
  --pdf-engine=tectonic \
  --toc --toc-depth=3 \
  -V documentclass=report \
  -V mainfont="$MAINFONT" \
  -V geometry:margin=2.5cm \
  -V lang=es \
  -V linkcolor=blue \
  > "$TMP/pandoc.log" 2>&1; then
  echo "ERROR: pandoc/tectonic failed:" >&2
  cat "$TMP/pandoc.log" >&2
  exit 1
fi

# Surface only genuine problems, not the routine Overfull/Underfull noise.
grep -iE 'missing character|could not represent|\berror\b' "$TMP/pandoc.log" >&2 || true

echo "Wrote $(pwd)/$OUT"
