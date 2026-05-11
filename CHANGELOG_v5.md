# Bird Call Alert — change notes

## v5.2 — 2026-05-11 (third deploy same day)

**Foundation for BoundaryBirds.** This is the deploy that sets up the data flywheel for our future home-grown classifier. Adds explicit confirm action, auto-dismiss-on-correct, per-card corpus visibility, and a Pi-side handler for confirmed clips.

### Web app changes

**New Confirm button (blue ✓).** Top-right of every card alongside the Dismiss button (×). One tap = "BirdNET is right, I'm sure" → writes `metadata.confirmed=true` AND `dismissed=true` in one PATCH → card moves to history → Pi promote-poll copies WAV into `training-corpus/<species_guess>/`.

**Auto-dismiss on save correction.** Saving a manual label now also dismisses in the same PATCH. One action instead of two taps.

**Per-card corpus stat.** Below the confidence label on every card, small text like "47 clips ●". Tier dots: green ● for 30+, yellow ◐ for 15-29, blank below 15. Lets you decide at-a-glance whether a species needs more clips or already has enough.

**Training corpus panel in Settings.** Collapsible section, default closed, near the bottom. Shows all species you've contributed clips for, sorted by count desc. Same tier dots as cards.

**Two badge colours in history.** Green ✓ for corrections (BirdNET wrong, you supplied truth), blue ✓ for confirmations (BirdNET right, you agreed). Visually distinct so you can tell what kind of action a given history card represents.

**Restore button removed.** It doesn't fit the new "Confirm/Dismiss/Correct" workflow. To act on a history card now, use the Confirm/Dismiss buttons directly (available on cards without existing actions) or tap to expand and Correct.

**Behaviour cleanup: history actions.** Cards in history without an existing action (corrected or confirmed) show the same Confirm/Dismiss buttons as live cards. Lets you action clips that aged out of the 24h window without ever being reviewed. Cards already actioned show no buttons (the action is done).

### Pi changes

**New `_v5_2_handle_confirmed_rows()` function** appended to `~/audio_detector.py` via `patch_audio_detector_v5_2.py`. Polls Supabase every 120s for rows where `metadata->>confirmed=true`, copies the WAV from `clips/<filename>` to `training-corpus/<normalised-species-guess>/<basename>`. Marks each handled row with `metadata._v5_2_corpus_done=true` so it's idempotent.

The patch:
- Backs up `audio_detector.py` before modification
- Refuses to re-apply if already patched (idempotent)
- Auto-starts a daemon thread on detector startup
- Logs "v5.2: confirmed-poll thread started (120s interval)" on success

### Data model additions

- `metadata.confirmed: true` — new field set by web app when user taps Confirm
- `metadata._v5_2_corpus_done: true` — internal sentinel set by Pi after copying

Both are jsonb fields on `candidate_sightings`. No schema migration needed.

### Tests to run after deploy

1. **Web app:** footer reads v5.2, hard-refresh confirmed.
2. **Confirm flow:** find a high-confidence detection of a species you know is correct. Tap blue ✓. Card disappears from live, shows in history with blue ✓ badge.
3. **Corpus stat updates:** species count on cards/Settings ticks up within ~120 seconds.
4. **Pi side:** `ssh ... "ls /home/matt/training-corpus/<species>/"` shows the new WAV.
5. **Auto-dismiss on correct:** expand a card, type a label, save → card moves to history in one go (no second tap on X).
6. **History buttons:** open History → Today, find a card that wasn't actioned. Confirm/Dismiss buttons should be visible. On a corrected/confirmed card, they should not.

### Deferred to v5.3 or later

- **Inline audio playback** (still opens new tab; requires Tailscale or Supabase Storage proxy)
- **Autocomplete on correction labels** (would help label consistency)
- **Region-aware confidence floor** (per-species confidence multipliers)
- **First BoundaryBirds training run** — waiting for ≥30 clips per species

---

## v5.1 — 2026-05-11 (same day as v5.0)

**Bug fix.** Today bucket of history was showing everything from today, not just dismissed-today items. This duplicated the live feed inside history and made history look like it was filling up on its own.

**Fix:** Today bucket now filters to `dismissed = true`. Empty until you actually dismiss something. Yesterday and older buckets unchanged (still show everything in range, since they're the archive view).

**Updated empty-state copy** for Today bucket: "Nothing dismissed today yet. Tap the × on a live card to file it here."

**Test:** Open History. Today should now show 0 items if you haven't dismissed anything. Tap the × on a live card → it should appear in Today instantly.

---

## v5.0 — 2026-05-11

**Deploy date target:** 2026-05-11
**Files changed:** `index.html` only (web app). No Pi changes, no Supabase schema changes.

## What changed

### 1. Fixed: history was "empty" past ~7 hours

Root cause was `limit=100` on the Supabase query combined with high post-v4 detection volume (~60-80/hr peak). Old dismissed rows existed in Supabase but were pushed out of the 100-row response before reaching the browser.

Fix: split into two query scopes —
- **Live window:** rows from last 24 hours, `limit=500` safety cap, polled every 20s
- **History buckets:** lazy-loaded per bucket on expand, `limit=1000` per bucket

### 2. New: time-based live/history split

Old behaviour: live shows non-dismissed, history shows dismissed. Boundary defined by user action.

New behaviour: live shows non-dismissed AND less than 24h old. History shows everything else, organised by calendar buckets:
- **Today** (derived from live window — instant, no extra query)
- **Yesterday** (lazy fetch)
- **This week** (lazy fetch)
- **This month** (lazy fetch)
- **Older** (lazy fetch)

All buckets except Today default to collapsed. Tap header to expand and trigger fetch.

### 3. New: history classification filter

Chip-row at top of history: Priority / Suspect / Normal. All on by default. Muted excluded entirely from history (it's noise). Filter applies across all buckets and updates counts live.

### 4. New: green ✓ "corrected" badge on cards

Cards where `metadata.manual_label` exists AND differs from `species_guess` get a small green ✓ badge in the top-right corner. Visible at a glance when scanning a list. Shows in both live and history modes. Confirmations (where manual_label matches species_guess) don't trigger the badge.

### 5. Fixed: PI_AUDIO_BASE port

Changed from `:8080` to `:8090`. The v4 deploy needed a manual sed during deploy to fix this; now baked into the source.

### 6. Removed: Range header that capped responses regardless of URL

Old: `Range: 0-99` header forced 100 rows even if the URL asked for more. Removed.

### 7. New: version stamp footer

Small "Bird Call Alert · v5.0 · 2026-05-11" at the bottom of every page. **Bump on every deploy.** Two constants at top of script: `APP_VERSION` and `APP_VERSION_DATE`.

## Things to test after deploy

1. **Live feed shows last 24h only.** Hard refresh. Verify only recent detections appear.
2. **Footer shows v5.0 + today's date.** If still v4, hard refresh / clear cache.
3. **History opens with five buckets visible.** Today auto-loaded with count; others collapsed showing "tap to load".
4. **Tap each non-Today bucket header.** Each should fetch and populate. Counts should match what you saw in the SQL query yesterday.
5. **Classification filter chips at top of history.** Toggle Priority off. All priority items should disappear across all buckets. Toggle back on.
6. **Dismiss something in live → check Today bucket.** Should appear immediately (same data, no fetch).
7. **Corrected badge.** Find a card you've corrected. Should have a green ✓ in the top-right. If you haven't corrected anything yet, expand a card, type a label in "What is this actually?", save. ✓ should appear immediately.
8. **Audio playback.** Tap a card with a clip → "Play clip in new tab". Should open `http://eaglecam.local:8090/clips/...`. If it 404s, the 8080→8090 fix may have a Pi-side mismatch; check what port `audio_server.py` is actually listening on.

## Things to watch for (potential issues)

- **Empty live feed when Pi has been quiet.** Used to show 100 rows back to whenever; now shows nothing if no detections in last 24h. New empty-state copy points users to History. Expected, not a bug.
- **Settings → Species classification list now narrower.** Only species heard in last 24h appear. To classify a species you haven't heard recently, find it in History and tap the card to set classification.
- **Bucket fetch on slow connection.** Each bucket fires its own request. Cached after first load. If you tap multiple buckets fast, they fire in parallel, fine.

## Files in this deploy

- `index.html` (the only file you need to upload)

## Rollback plan

If anything breaks, redeploy `birdcallalert_v4/index.html` from your Downloads folder. No database changes were made, no Pi changes, so rollback is just re-uploading the previous HTML.
