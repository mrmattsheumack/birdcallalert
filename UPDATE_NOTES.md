# Bird Call Alert v2 — what changed and how to deploy

## The user-visible changes

**Filter UI simplified.** The old four-button preset (All / Raptors / Woodland / Waterbirds) is replaced with a two-way picker: **All** vs **Priority only**. Living in the Settings sheet, same place as before.

**Notification preference added.** Three modes: **Priority only** (default), **All detections**, or **Off**. Also in Settings. Previously notifications fired for hardcoded "interesting" species; now you control which detections trigger them.

**Live feed now shows everything (not just target species).** Each card has an X button in its action area to clear it. Cleared items move to the History page, they aren't deleted from Supabase. Priority items keep the star icon and orange accent border; non-priority items render plain.

**Sort order: priority first.** Within the live feed, priority detections are pinned at the top (sorted newest-first within that bucket), then non-priority detections newest-first below them. Even if a non-priority Rainbow Lorikeet just came in 30 seconds ago, a priority detection from an hour ago will be above it.

**History page.** New tab accessed via the 🗂 icon in the top-right of the header (between refresh and settings). Shows cleared detections grouped by **Today / Yesterday / This week / Older**. Each item has a "↩ Restore" button to put it back in the live feed.

**Confidence threshold default unchanged at 40%.** The Pi's threshold dropped from 40% to 25% (see Pi-side change below), but the UI slider still defaults to 40% so the live feed should look essentially the same to start with. Drag the slider down to see what the Pi is now picking up at lower confidence.

## The architectural changes

These are decisions that matter if/when we extend further:

**Priority is now computed in the UI from `PRIORITY_SPECIES` in `index.html`.** Adding/removing priority species is a one-side edit. The Pi script keeps its `TARGET_SPECIES` set as the source of truth for the *priority flag* (the flag is set based on whether the species is in `TARGET_SPECIES`), but no longer uses it to filter what gets posted. Both lists exist for now and need to stay in sync.

**The `priority` flag now rides in the Supabase row's `metadata`.** The web app could read this flag rather than computing client-side from PRIORITY_SPECIES, but I left the client-side computation as the source of truth so list edits are one-sided. The metadata flag is still useful for any future server-side queries or analytics.

**Dismissal uses the existing `dismissed` boolean column on `candidate_sightings`.** No schema change. The PATCH from the web app is anonymous (uses the same Supabase anon key as reads). Make sure RLS allows UPDATE on this table for anon — see "RLS check" below.

## Files in this update

- `index.html` — full v2 web app (replaces the existing one in `birdcallalert/`)
- `patch_audio_detector.py` — Python patch script for the Pi side
- `UPDATE_NOTES.md` — this file

## Deployment steps

### Web side (do this first; UI gracefully handles old Pi data)

1. In your local `birdcallalert/` folder, replace `index.html` with the new one.
2. Smoke-test locally first if you can:

   ```bash
   cd birdcallalert
   python3 -m http.server 8000
   # open http://localhost:8000 in a browser
   ```

3. Push to your Netlify-deployed repo (or drag-and-drop to Netlify if that's your flow). It should pick up the change automatically.
4. Hard-refresh on your phone (browser cache loves to hold onto inline `<script>` blocks).

The new app reads existing Supabase rows fine. They won't have `priority` in metadata (that's a Pi-side change coming next), but priority is computed client-side from `PRIORITY_SPECIES` so existing rows still get categorised correctly.

### Pi side

```bash
# 1. SSH in
ssh -i ~/.ssh/eaglecam_key matt@eaglecam.local

# 2. Stop the service so we don't patch a running file
sudo systemctl stop audio-detector

# 3. Copy the patch script over from your Mac (in another terminal):
#    scp -i ~/.ssh/eaglecam_key patch_audio_detector.py matt@eaglecam.local:/home/matt/

# 4. Run the patch
python3 /home/matt/patch_audio_detector.py /home/matt/audio_detector.py

# 5. Drop the threshold from 40% to 25% in the env file
nano /home/matt/audio_detector.env
# Change:  BIRDNET_MIN_CONFIDENCE=0.40
# To:      BIRDNET_MIN_CONFIDENCE=0.25
# Save and exit

# 6. Start the service back up
sudo systemctl start audio-detector

# 7. Watch a few chunks go through to make sure nothing exploded
journalctl -u audio-detector -f
# You should see "raw: ..." lines and "-> Supabase: 201 ..." lines.
# Detections that were "off-list" before are now posted (and you'll see
# the priority flag in the metadata).
# Ctrl+C to stop following.
```

If the patch script fails or refuses to run, it'll print a clear message. Most likely cause: the unified `audio_detector.py` has a slightly different structure from the original `bird_detection_alert.py` that the script was written against. In that case, the manual edits are:

1. Find the block:
   ```python
   if label not in TARGET_SPECIES:
       print(f"  off-list: {label} ({conf*100:.0f}%)", flush=True)
       continue
   ```
   Replace with:
   ```python
   priority = label in TARGET_SPECIES
   ```

2. Find the `post_to_supabase` function definition and change:
   ```python
   def post_to_supabase(detection):
   ```
   to:
   ```python
   def post_to_supabase(detection, priority=False):
   ```

3. Inside the metadata dict in that function, alongside `"detector": "birdnet",`, add:
   ```python
   "priority": bool(priority),
   ```

4. Find where `post_to_supabase(d)` is called and change to:
   ```python
   if post_to_supabase(d, priority=priority):
   ```

### RLS check (one-time, important)

The web app's clear/restore feature needs UPDATE permission on `candidate_sightings` for anonymous users. Without it, the X button will fail silently and the item will reappear on next fetch.

In the Supabase dashboard:

1. Database → Tables → `candidate_sightings` → "Auth Policies"
2. If there's no UPDATE policy for `anon`, add one:
   - Policy name: `Allow anon to dismiss/restore`
   - Allowed operation: UPDATE
   - Target roles: `anon`
   - USING expression: `true`
   - WITH CHECK expression: `true`

This is loose (anyone with the deployed URL can update any field). If you want tighter, restrict to only the `dismissed` column via a RLS policy that uses `WITH CHECK ((dismissed IS NOT NULL))` — though that's more pain than it's worth for a personal app.

**Alternative if you'd rather not loosen RLS:** I can change the web app to call a Supabase Edge Function for dismiss/restore that uses a service-role key server-side. Mention if you want that path instead.

## Rolling back

The patch script writes a timestamped `.bak.YYYYMMDD-HHMMSS` file before any change, so:

```bash
# Pi side rollback
sudo systemctl stop audio-detector
cp /home/matt/audio_detector.py.bak.YYYYMMDD-HHMMSS /home/matt/audio_detector.py
# Restore env: edit BIRDNET_MIN_CONFIDENCE=0.40 again
sudo systemctl start audio-detector
```

For the web app, the previous `index.html` is in your git history (or your last Netlify deploy's "Deploys" tab — every Netlify deploy is preserved and can be redeployed with one click).

## Things I'd flag for next iteration

1. **Per-species priority editing in the UI.** Right now `PRIORITY_SPECIES` is hardcoded in `index.html`. To change it you edit the file and redeploy. Database-driven lists (the option you said "later if we need to") are the natural next step once you've seen which species you actually want to flag.

2. **Push notifications when the app isn't open.** The current Notification API only fires while a tab is open. If you want true background push (e.g. an alert at 3am for a Powerful Owl when your phone is asleep), that needs Web Push with VAPID keys, a service worker, and the Pi script signing pushes. Bigger project, but doable.

3. **Audio level watchdog.** Suggested earlier: if peak audio is near-silent for ~20 chunks in a row, post an alert that the mic is probably muted/unplugged. Catches the SR-EA2S mute button being pressed accidentally.

4. **Tape over the SR-EA2S mute button.** Mentioned as a long-overdue physical fix.

5. **PWA icons.** `icon-192.png` and `icon-512.png` still aren't in the `birdcallalert/` folder. The app works fine without them but "Add to Home Screen" looks ugly.
