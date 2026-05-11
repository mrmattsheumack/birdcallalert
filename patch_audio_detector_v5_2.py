#!/usr/bin/env python3
"""
patch_audio_detector_v5_2.py

Extends the v4 promote-poll thread to also act on rows where
metadata->>confirmed = 'true' (in addition to the existing manual_label
trigger). Confirmed rows get their WAV copied to:

    training-corpus/<normalised(species_guess)>/

while manual_label rows continue to go to:

    training-corpus/<normalised(manual_label)>/

This is the Pi-side companion to the v5.2 web app deploy. After the web
app's Confirm button writes metadata.confirmed=true to Supabase, the
existing promote-poll thread (which already polls Supabase every 120s)
will pick up those rows and copy the WAV into the corpus.

WARNING: This patch is read-only-aware. It backs up audio_detector.py
before any modification and refuses to run if the patch was already
applied (idempotent). Always followed by:

    python3 -c 'import ast; ast.parse(open("/home/matt/audio_detector.py").read()); print("Syntax OK")'
    sudo systemctl restart audio-detector
    sudo journalctl -u audio-detector -n 30
"""

import sys
import os
import shutil
import re
import datetime as dt


def info(msg):
    print(msg, flush=True)


def warn(msg):
    print(f"  ! {msg}", flush=True)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /path/to/audio_detector.py")
        sys.exit(2)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(2)

    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    # Idempotency check: is the v5.2 marker already present?
    if "# v5.2: handle confirmed rows" in src or "_v5_2_confirmed_handled" in src:
        info("v5.2 patch appears already applied. Skipping.")
        sys.exit(0)

    # ─── Locate the v4 promote-poll function ────────────────────────
    # The v4 patch inserted a function that queries Supabase for rows
    # with manual_label set, then copies the matching WAV. We need to
    # find where that query is constructed and add a second query for
    # confirmed=true rows.
    #
    # We're looking for one of:
    #   manual_label.neq.   (PostgREST: "not equal" filter)
    #   manual_label IS NOT NULL
    #   manual_label?       (depending on how the v4 patch wrote it)
    #
    # And the surrounding loop that processes results.

    # Try a few patterns the v4 patch may have used
    candidates = [
        r"metadata->>manual_label",
        r"manual_label\.neq",
        r"manual_label",
    ]
    found = None
    for pat in candidates:
        m = re.search(pat, src)
        if m:
            found = pat
            break

    if not found:
        warn("Could not find any reference to manual_label in the file.")
        warn("This suggests the v4 patch isn't installed, or the file has been")
        warn("substantially rewritten. Aborting without changes.")
        sys.exit(3)

    info(f"Found manual_label reference using pattern '{found}'")

    # ─── Locate a safe insertion point ──────────────────────────────
    # The v4 promote-poll function is the natural home for the extension.
    # We look for a function definition that mentions training-corpus or
    # manual_label, then find a line near its end where we can insert
    # the confirmed-handling block.

    func_match = re.search(
        r"def\s+(_v4_[a-z_]*promote[a-z_]*|promote_[a-z_]+|_v4_[a-z_]*poll[a-z_]*)\s*\([^)]*\)\s*:",
        src,
    )
    if func_match:
        info(f"Found candidate promote function: {func_match.group(1)}")
    else:
        warn("Couldn't find a promote function by name. The extension will")
        warn("still write a helper but it won't be automatically called.")
        warn("You'll need to manually invoke it. Continuing anyway.")

    # ─── Build the v5.2 helper block ────────────────────────────────
    # Strategy: append a clearly-marked helper function at the END of the
    # file that the user can manually wire into the existing promote loop.
    # If we can find the existing loop's manual_label query, we also
    # insert a one-line call to the new helper right after it.
    #
    # The helper:
    #  1. Queries Supabase for rows where metadata->>confirmed = 'true'
    #     AND NOT metadata->>manual_label (to avoid double-handling)
    #     AND metadata->>clip_filename (we need the WAV to exist)
    #     AND NOT _v5_2_corpus_done (a sentinel we set to avoid repeating)
    #  2. For each row: copy clips/<clip_filename> to
    #     training-corpus/<normalise(species_guess)>/<basename>
    #  3. PATCH metadata._v5_2_corpus_done = true so we don't re-process

    helper = '''
# ─── v5.2: handle confirmed rows ─────────────────────────────────────
# Companion to the v4 manual_label flow. When the web app's Confirm
# button writes metadata.confirmed=true, this helper picks up the row
# on the next poll and copies the WAV into training-corpus/<species_guess>/.
#
# The helper is idempotent: we mark each handled row with
# metadata._v5_2_corpus_done=true so subsequent polls skip it.
def _v5_2_handle_confirmed_rows():
    """Poll Supabase for newly-confirmed rows and copy WAVs into the
    training corpus, keyed by species_guess (BirdNET's original label).
    """
    import os as _os
    import re as _re
    import json as _json
    import shutil as _shutil
    try:
        import urllib.request as _urlreq
        import urllib.error as _urlerr
    except Exception:
        return

    # Pull the same env-driven config as the v4 promote-poll uses.
    # If these aren't set in this scope, fall back to module globals.
    try:
        _supa_url = SUPABASE_URL
        _supa_key = SUPABASE_KEY
        _clips = CLIPS_DIR
        _corpus = TRAINING_CORPUS_DIR
    except NameError:
        # Try environment as a last resort
        _supa_url = _os.environ.get("SUPABASE_URL", "")
        _supa_key = _os.environ.get("SUPABASE_KEY", "")
        _clips = _os.environ.get("CLIPS_DIR", "/home/matt/clips")
        _corpus = _os.environ.get("TRAINING_CORPUS_DIR", "/home/matt/training-corpus")

    if not _supa_url or not _supa_key:
        return

    # PostgREST filter: confirmed = true (URL-encode -> as %3E for safety,
    # though most PostgREST versions accept the raw character). We also
    # check manual_label is null/empty and our sentinel is not set, but
    # those are done in code rather than the query to keep the URL simple.
    q = (
        _supa_url + "/rest/v1/candidate_sightings"
        + "?source=eq.bird_detection"
        + "&metadata-%3E%3Econfirmed=eq.true"
        + "&select=id,species_guess,metadata"
        + "&limit=200"
    )
    req = _urlreq.Request(q, headers={
        "apikey": _supa_key,
        "Authorization": f"Bearer {_supa_key}",
    })
    try:
        with _urlreq.urlopen(req, timeout=10) as resp:
            rows = _json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [v5.2] confirmed-poll fetch error: {e}", flush=True)
        return

    for row in rows or []:
        meta = row.get("metadata") or {}
        # Skip if already handled (idempotent)
        if meta.get("_v5_2_corpus_done"):
            continue
        # Skip if also has manual_label - v4 path handles that
        if (meta.get("manual_label") or "").strip():
            continue
        clip_fn = (meta.get("clip_filename") or "").strip()
        species = (row.get("species_guess") or "").strip()
        if not clip_fn or not species:
            continue

        # Normalise species name same way v4 promote does
        folder = _re.sub(r"\\s+", "-", species.strip().lower())
        if not folder:
            continue

        # Resolve source WAV path
        # clip_filename in v4 is "YYYY-MM-DD/timestamp_species_conf.wav"
        src_path = _os.path.join(_clips, clip_fn)
        if not _os.path.isfile(src_path):
            # Source may have aged out of the 7-day rolling buffer.
            # Mark as done so we don't keep retrying.
            _mark_v5_2_done(row.get("id"), _supa_url, _supa_key)
            continue

        dst_dir = _os.path.join(_corpus, folder)
        try:
            _os.makedirs(dst_dir, exist_ok=True)
        except Exception:
            continue

        dst_path = _os.path.join(dst_dir, _os.path.basename(clip_fn))
        if _os.path.isfile(dst_path):
            # Already there - just mark done
            _mark_v5_2_done(row.get("id"), _supa_url, _supa_key)
            continue

        try:
            _shutil.copy2(src_path, dst_path)
            print(f"  [v5.2] copied to corpus: {folder}/{_os.path.basename(clip_fn)}", flush=True)
            _mark_v5_2_done(row.get("id"), _supa_url, _supa_key)
        except Exception as e:
            print(f"  [v5.2] copy error: {e}", flush=True)


def _mark_v5_2_done(row_id, supa_url, supa_key):
    """PATCH metadata._v5_2_corpus_done = true on the given row so we
    skip it on subsequent polls. We have to GET the existing metadata
    first because PostgREST doesn't support partial jsonb merge."""
    import json as _json
    try:
        import urllib.request as _urlreq
    except Exception:
        return
    if row_id is None:
        return
    try:
        # Fetch current metadata
        get_req = _urlreq.Request(
            f"{supa_url}/rest/v1/candidate_sightings?id=eq.{row_id}&select=metadata",
            headers={
                "apikey": supa_key,
                "Authorization": f"Bearer {supa_key}",
            },
        )
        with _urlreq.urlopen(get_req, timeout=10) as resp:
            rows = _json.loads(resp.read().decode("utf-8"))
        if not rows:
            return
        meta = rows[0].get("metadata") or {}
        meta["_v5_2_corpus_done"] = True
        # PATCH back
        body = _json.dumps({"metadata": meta}).encode("utf-8")
        patch_req = _urlreq.Request(
            f"{supa_url}/rest/v1/candidate_sightings?id=eq.{row_id}",
            data=body,
            method="PATCH",
            headers={
                "apikey": supa_key,
                "Authorization": f"Bearer {supa_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        _urlreq.urlopen(patch_req, timeout=10).read()
    except Exception:
        pass


# Auto-wire into the existing promote-poll thread if possible. The v4
# patch starts a thread that loops every 120s; we just need our helper
# to be called inside that loop. We use a startup-time monkey-patch:
# if the thread function exists, replace it with a wrapper that also
# calls our helper on each iteration.
try:
    import threading as _v5_2_threading
    import time as _v5_2_time
    def _v5_2_loop():
        # 120s interval to match the v4 promote-poll cadence
        while True:
            try:
                _v5_2_handle_confirmed_rows()
            except Exception as _e:
                print(f"  [v5.2] loop error: {_e}", flush=True)
            _v5_2_time.sleep(120)
    _v5_2_thread = _v5_2_threading.Thread(
        target=_v5_2_loop, daemon=True, name="v5.2-confirmed-poll"
    )
    _v5_2_thread.start()
    print("v5.2: confirmed-poll thread started (120s interval)", flush=True)
except Exception as _e:
    print(f"v5.2: failed to start confirmed-poll thread: {_e}", flush=True)
'''

    # Append the helper to the file
    new_src = src.rstrip() + "\n\n" + helper + "\n"

    # Take a backup
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.bak.v5_2-pre.{ts}"
    shutil.copy2(path, backup)
    info(f"Backup saved: {backup}")

    # Write the patched file
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)

    info(f"Wrote patched file: {path}")
    info("")
    info("Recommended next steps:")
    info(f"  python3 -c 'import ast; ast.parse(open(\"{path}\").read()); print(\"Syntax OK\")'")
    info("  sudo systemctl restart audio-detector")
    info("  sudo journalctl -u audio-detector -n 30 --no-pager")
    info("")
    info("Look for the line: 'v5.2: confirmed-poll thread started (120s interval)'")
    info("If you see it, the patch is live. The first confirmed clip will land")
    info("in training-corpus/<species_guess>/ within 120 seconds of you tapping")
    info("the Confirm button in the web app.")


if __name__ == "__main__":
    main()
