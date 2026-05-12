-- Bird Call Alert: manual_label consolidation
-- Run in Supabase SQL Editor. All operations are PATCH on existing rows.
-- Safe to re-run (idempotent: applies WHERE clauses scoped to specific old values).
--
-- IMPORTANT: this only touches metadata->>manual_label. It does NOT
-- touch species_guess (BirdNET's label) or any other fields. The Pi
-- promote-poll will re-evaluate the corpus folder names based on the
-- new normalized manual_label values - but we also do an explicit
-- folder merge on the Pi (separate script).

-- ─── 1. Verify current state (run this FIRST, before applying changes) ───
-- Should show how many rows have each problematic manual_label variant.
select metadata->>'manual_label' as label, count(*)
from candidate_sightings
where metadata->>'manual_label' in (
  'Common Mynah', 'Common mynah',
  'Sulphur crested cockatoo', 'Sulphur Crested cockatoo',
  'Noisy miner',
  'Brown thornbill',
  'Little raven',
  'Laughing kookaburra',
  'Masked lapwing',
  'Mistletoe bird',
  'Australian Wood duck',
  'European blackbird',
  'Corella',
  'Raven',
  'Wattlebird',
  'Dog', 'Dog on deck'
)
group by 1
order by 2 desc;

-- ─── 2. Apply normalizations ────────────────────────────────────────
-- Each statement is an UPDATE that rewrites metadata.manual_label for
-- matching rows. We use jsonb_set so we only touch that one key,
-- preserving any other metadata (confirmed, reviewed_at, clip_filename, etc).

-- Common Mynah variants -> Common Myna (matches BirdNET)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Common Myna"')
where metadata->>'manual_label' in ('Common Mynah', 'Common mynah');

-- Sulphur-crested Cockatoo variants -> Sulphur-crested Cockatoo (matches BirdNET, note the dash and lowercase c)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Sulphur-crested Cockatoo"')
where metadata->>'manual_label' in ('Sulphur crested cockatoo', 'Sulphur Crested cockatoo');

-- Case fixes (just capitalization)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Noisy Miner"')
where metadata->>'manual_label' = 'Noisy miner';

update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Brown Thornbill"')
where metadata->>'manual_label' = 'Brown thornbill';

update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Little Raven"')
where metadata->>'manual_label' = 'Little raven';

update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Laughing Kookaburra"')
where metadata->>'manual_label' = 'Laughing kookaburra';

update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Masked Lapwing"')
where metadata->>'manual_label' = 'Masked lapwing';

-- Mistletoebird typo (was "Mistletoe bird" with space)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Mistletoebird"')
where metadata->>'manual_label' = 'Mistletoe bird';

-- Australian Wood Duck capitalization
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Australian Wood Duck"')
where metadata->>'manual_label' = 'Australian Wood duck';

-- European blackbird is actually Eurasian Blackbird in BirdNET
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Eurasian Blackbird"')
where metadata->>'manual_label' = 'European blackbird';

-- Corella (generic) -> Little Corella (most likely species in your area)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Little Corella"')
where metadata->>'manual_label' = 'Corella';

-- Wattlebird (generic) -> Little Wattlebird (your call from Q4)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Little Wattlebird"')
where metadata->>'manual_label' = 'Wattlebird';

-- Raven (generic) -> Little Raven (your call from Q2)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Little Raven"')
where metadata->>'manual_label' = 'Raven';

-- Dog / Dog on deck -> Not Bird (your call from Q3, keeping Cricket separate)
update candidate_sightings
set metadata = jsonb_set(metadata, '{manual_label}', '"Not Bird"')
where metadata->>'manual_label' in ('Dog', 'Dog on deck');

-- ─── 3. Also clear the _v5_2_corpus_done sentinel for any of these rows ───
-- This forces the Pi to re-evaluate and copy clips to the new folders
-- on the next promote-poll cycle.
update candidate_sightings
set metadata = metadata - '_v5_2_corpus_done'
where metadata->>'manual_label' in (
  'Common Myna',
  'Sulphur-crested Cockatoo',
  'Noisy Miner',
  'Brown Thornbill',
  'Little Raven',
  'Laughing Kookaburra',
  'Masked Lapwing',
  'Mistletoebird',
  'Australian Wood Duck',
  'Eurasian Blackbird',
  'Little Corella',
  'Little Wattlebird',
  'Not Bird'
);

-- ─── 4. Verify after applying ────────────────────────────────────────
-- Should show NO rows with the old problematic spellings, and clean
-- consolidated counts under the canonical names.
select metadata->>'manual_label' as label, count(*) as rows
from candidate_sightings
where metadata->>'manual_label' is not null
  and metadata->>'manual_label' != ''
group by 1
order by 2 desc;
