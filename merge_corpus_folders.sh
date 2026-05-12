#!/usr/bin/env bash
# Merge training-corpus folders to match the consolidated label names.
# Run on the Pi (or via ssh from the Mac). Safe to re-run; mv only happens
# if source folder exists.
#
# Mapping (matches consolidate_labels.sql):
#   common-mynah/   -> common-myna/
#   raven/          -> little-raven/
#   australian-raven/ -> little-raven/  (questionable - see comment below)
#   corella/        -> little-corella/
#   wattlebird/     -> little-wattlebird/
#   not-a-bird/     -> not-bird/        (canonical form is "Not Bird")
#
# NOTE on australian-raven: BirdNET CAN identify Australian Raven specifically.
# We're merging it to little-raven only because your Q2 answer was "merge
# generic Raven to Little Raven" - I'm including australian-raven here as a
# choice point. If you want to KEEP australian-raven separate (because BirdNET
# distinguishes the species), comment out that line below.

set -euo pipefail

CORPUS=/home/matt/training-corpus
cd "$CORPUS"

echo "=== Before ==="
find . -mindepth 2 -name '*.wav' | sed 's|^\./||;s|/.*||' | sort | uniq -c | sort -rn

merge_folder() {
    local src="$1"
    local dst="$2"
    if [[ -d "$src" ]]; then
        mkdir -p "$dst"
        # Move WAVs one at a time; if any have name clashes, rename with suffix.
        for f in "$src"/*.wav; do
            [[ -f "$f" ]] || continue
            base=$(basename "$f")
            if [[ -e "$dst/$base" ]]; then
                # Name clash, very unlikely. Add a suffix.
                ts=$(date +%s%N)
                mv "$f" "$dst/${base%.wav}.merged-${ts}.wav"
            else
                mv "$f" "$dst/"
            fi
        done
        # Remove now-empty source folder
        rmdir "$src" 2>/dev/null || echo "  WARN: $src not empty after merge"
        echo "  merged $src -> $dst"
    fi
}

echo ""
echo "=== Merging ==="
merge_folder common-mynah     common-myna
merge_folder raven            little-raven
merge_folder australian-raven little-raven    # comment out if you want Australian Raven kept separate
merge_folder corella          little-corella
merge_folder wattlebird       little-wattlebird
merge_folder not-a-bird       not-bird

echo ""
echo "=== After ==="
find . -mindepth 2 -name '*.wav' | sed 's|^\./||;s|/.*||' | sort | uniq -c | sort -rn
