# Tailscale + v5.3 deploy — evening checklist

Step through these in order tonight. Each step is independent. If anything goes wrong, stop and ask Claude — don't push through.

---

## Pre-flight (already done today)

- ✓ Tailscale phone app installed and signed in
- ✓ Tailscale on Pi installed and signed in
- ✓ Both devices on the same tailnet
  - paranoid-android (phone): 100.95.133.6
  - eaglecam (Pi): 100.99.80.39

You're 80% of the way there.

---

## Step 1: Deploy v5.3 web app (5 minutes)

The new `index.html` is in your Downloads (`~/Downloads/index.html`). It has the Tailscale IP baked in and version bumped to v5.3.

1. Open `~/Downloads/index.html` in TextEdit (right-click → Open With → TextEdit)
2. **Cmd+A**, **Cmd+C** to copy everything
3. Go to your `birdcallalert` GitHub repo in a browser
4. Click on `index.html`
5. Pencil icon to edit
6. **Cmd+A** in the editor, delete everything
7. **Cmd+V** to paste the new content
8. Scroll to bottom: commit message `v5.3 deploy: Tailscale audio routing`
9. Click green **Commit changes** button
10. Wait 60-90 seconds for Netlify

### Verify

On phone, open Bird Call Alert, hard refresh (close tab, reopen). Footer should read:

```
Bird Call Alert · v5.3 · 2026-05-12
```

If yes, proceed. If still v5.2, refresh harder.

---

## Step 2: Verify Tailscale is running on phone (1 minute)

1. Pull down the notification shade on your phone
2. Look for a Tailscale key icon. Should say something like "Tailscale connected" or "VPN active"

If you don't see it, open the Tailscale app and tap **Connect**. The key should appear in the notification shade. This needs to stay there. If you ever swipe it away, Tailscale stops.

---

## Step 3: Test audio playback FROM HOME WIFI first (2 minutes)

This is the easier case to test. Confirms we didn't break anything.

1. On your phone, on home wifi, open Bird Call Alert
2. Find any card with audio (a card showing "▶ Play clip in new tab")
3. Tap the play button
4. A new tab should open and audio should play

**Worked:** great, move to Step 4.

**Didn't work:** SSH into the Pi from your Mac and run:

```
sudo systemctl status audio-server
```

The service should be `active (running)`. If not:

```
sudo systemctl start audio-server
```

Then try the audio test again.

If still not working, run on the Pi:

```
curl -s http://100.99.80.39:8090/health
```

Should print `{"status": "ok"}`. If yes, the Pi-side audio server is fine and the issue is somewhere between the phone and the Pi via Tailscale. Send Claude the output of:

```
tailscale status
sudo ss -tlnp 'sport = :8090'
```

---

## Step 4: Test audio playback OFF home wifi (the real test, 2 minutes)

1. On your phone, **turn off wifi** (so you're on mobile data only)
2. Confirm in the notification shade that Tailscale is still connected (the key icon)
3. Open Bird Call Alert
4. Find any card with audio
5. Tap the play button
6. Audio should play exactly like it did on home wifi

**Worked:** Tailscale audio is fully operational. You can review clips from anywhere now.

**Didn't work:**
- If "no connection" — Tailscale on your phone is probably not running. Check notification shade for the key icon. Open the Tailscale app and tap Connect.
- If "site can't be reached" — possible the Pi's audio server isn't bound to all interfaces. Send Claude the output of `sudo ss -tlnp 'sport = :8090'` from the Pi.

---

## Step 5: Test history correction (new in v5.3, 2 minutes)

This tests the second v5.3 fix: relabelling cards in history.

1. Open Bird Call Alert → History → Today
2. Find a card with NO badge (or a blue ✓ if you don't have a clean one)
3. Tap the card body to expand
4. You should now see the "What is this actually?" input field. Previously this was missing in history.
5. Type any species name (test value: `test-correction`)
6. Tap Save
7. The card should auto-dismiss and the badge should be green ✓ (corrected)

**If the card had a blue ✓ before:** badge changes from blue to green.
**If no input field appears:** the v5.3 deploy didn't take effect; hard-refresh.

Optional verification: after ~2 minutes, on the Pi:

```
ssh -i ~/.ssh/eaglecam_key matt@eaglecam.local "ls -la ~/training-corpus/test-correction/ 2>/dev/null"
```

You should see one new WAV in the test-correction folder. Delete the folder afterwards:

```
ssh -i ~/.ssh/eaglecam_key matt@eaglecam.local "rm -rf ~/training-corpus/test-correction/"
```

---

## Optional Step 6: Test SSH over Tailscale (bonus, 1 minute)

While you're at it, test SSH from your Mac to the Pi via Tailscale:

```
ssh -i ~/.ssh/eaglecam_key matt@100.99.80.39
```

If this works, you can now SSH to the Pi from anywhere with Tailscale running on your Mac, not just from home. Useful for future maintenance.

---

## Rollback plan

If v5.3 audio causes any new problems:

1. Open the birdcallalert GitHub repo
2. Find the previous v5.2 commit in the history
3. View `index.html` at that commit
4. Click "Raw"
5. Save as `index_v5_2.html`
6. Edit the live `index.html` in GitHub, paste the v5.2 content back
7. Commit, wait for Netlify

No Pi changes were made in v5.3 so nothing to roll back on the Pi side.

---

## What's next after this

- **v5.3 is the audio routing fix.** Done after this evening if all goes well.
- **v5.4 = Web Push notifications** — next session's project. Real OS-level notifications.
- **Continue building corpus** — keep tapping Confirm/Correct/Dismiss on cards as they arrive. By tomorrow Common Mynah and Little Corella should both be past the 30-clip green threshold.
