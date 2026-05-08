# Bird Call Alert - Deployment

A standalone, single-page app for the BirdNET detection pipeline. Lives at
its own URL, completely separate from Eagle Tracker. Single `index.html`
plus a manifest, no build step, no framework toolchain.

## What's in this folder

- `index.html` - the entire app (HTML + React via Babel standalone + inline CSS)
- `manifest.webmanifest` - PWA manifest so it can be added to home screen
- `icon-192.png`, `icon-512.png` - **you need to provide these** (see below)
- `DEPLOYMENT.md` - this file

## Icons (do this before deploying)

You need two PNG icons in this folder for the PWA to install nicely:

- `icon-192.png` - 192×192 pixels
- `icon-512.png` - 512×512 pixels

A simple bird silhouette on a forest-green background (`#1f6b3a`) works.
You can generate these with any tool you like. If you don't add them, the
app still works in the browser, but "Add to Home Screen" will look ugly.

## Deploying to Netlify

Same pattern as Eagle Tracker. You have two clean options:

### Option A: New Netlify site, new GitHub repo (recommended)

1. Create a new GitHub repo (e.g. `birdcallalert`)
2. Push the contents of this folder to the repo's root
3. In Netlify: "Add new site" -> "Import from GitHub" -> pick the repo
4. Build settings: leave everything blank (no build command, no publish dir,
   or set publish dir to `/`)
5. Deploy. You'll get a URL like `birdcallalert.netlify.app` (or pick a
   custom subdomain in the Netlify dashboard)

### Option B: Drag-and-drop to Netlify

If you don't want a separate repo:

1. Open Netlify dashboard, drag this folder onto the "Deploy" area
2. You'll get a generated URL immediately
3. Re-deploy by drag-and-drop whenever you change the file

Option A is what I'd recommend so you get version history and can edit
on your phone via github.com if needed.

## Testing locally before you push

```bash
cd birdcallalert
python3 -m http.server 8000
# open http://localhost:8000 in a browser
```

The Notification API works on `localhost` (it's treated as secure context),
so you can test the full flow without deploying.

## Adding to your phone home screen

Once deployed:

- **iOS Safari**: open the site, tap Share -> "Add to Home Screen"
- **Android Chrome**: open the site, tap menu -> "Install app" or "Add to Home Screen"

Once installed, it launches like a real app and notifications fire while
the app is in recent memory. (Caveat: on iOS, notifications still only
fire while the app is open or recently opened. True background push would
need a service worker and Web Push, which we discussed splitting into a
later project.)

## Configuring the species list

The target species, exclusion list, and notification list are defined
in two places:

- **`bird_detection_alert.py`** on the Pi - controls what gets posted
  to Supabase in the first place. This is the source of truth.
- **`index.html`** in this folder - controls UI presentation:
  the filter presets (`PRESETS`) and which species trigger a star/notification
  (`NOTIFY_SPECIES`).

To add a new target species:
1. Add it to `TARGET_SPECIES` in the Pi script, restart `bird-detection.service`
2. Optionally add it to a preset's species list in `index.html` and re-deploy

Both lists need to use the exact format `Common Name_Scientific name` that
BirdNET emits.

## Security note

The Supabase URL and anon key are baked into `index.html`. This is the
standard pattern for client-side Supabase apps and is OK *if* you have
Row Level Security (RLS) enabled on the `candidate_sightings` table.

Without RLS, anyone with the deployed URL can read, write, or delete
records via the API. Even with RLS, the policies need to allow only the
operations you intend (this app needs SELECT only - it never writes to
the table; the Pi script does the writing).

Quick check: in Supabase dashboard -> Database -> Tables ->
`candidate_sightings`. There should be a "RLS enabled" indicator.
If not, click the table -> "Add policy" and at minimum:

- Policy name: "Allow anonymous read"
- Allowed operation: SELECT
- Target roles: `anon`
- USING expression: `true`

And do NOT add an INSERT/UPDATE/DELETE policy for `anon`. The Pi script
should use a separate service-role key (which bypasses RLS) for writes.
That's a different change to the Pi script if you want me to set it up.
