# HR-64: 90 m and 49 m Recording Lists — Phase 1 Review

Built October 20, 2026 by `tools/build-band-catalog.py` from the core and band-edge sheets of the two candidate workbooks in `data/bands/`. These lists are staged in `data/bands/` and are not yet connected to the receiver. `tools/test-band-catalogs.cjs` passes, and the existing 60 m and seasonal-noise tests still pass unchanged.

## Totals

| | 90 m | 49 m |
|---|---:|---:|
| Rows read (core + band edge) | 141 (137 + 4) | 350 (282 + 68) |
| **Tunable** | **125** (121 core, 4 edge) | **261** (215 core, 46 edge) |
| Held: compilation or multi-station file | 10 | 5 |
| Held: outside 1960–1989 | 0 | 76 (20 before 1960, 56 after 1989) |
| Held: second copy of the same recording | 6 | 8 |
| Dial positions with recordings | 60 | 119 |
| Busiest frequency | 3325 kHz (7 recordings) | 6155 kHz (9 recordings) |
| Tunable recordings by decade | 1960s 1, 1970s 52, 1980s 72 | 1960s 3, 1970s 87, 1980s 171 |
| Countries / areas (as labeled) | 31 | 57 |
| Dial range | 3150–3500 kHz | 5850–6350 kHz |

With the existing 323 tunable 60 m recordings, the three bands total **709**.

Most common countries among tunable recordings:

- **90 m:** Ecuador 16, Brazil 15, Papua New Guinea 14, Venezuela 13, Peru 8, Mozambique 5, Guatemala 5.
- **49 m:** Colombia 31, Peru 30, Brazil 20, Costa Rica 11, Bolivia 11, Mexico 10, Argentina 10, Venezuela 10.

## Copies of the same recording

Where the spreadsheet says two rows are the same recording, one copy is kept: a working link first, then the longest copy, then the stronger date and time evidence. The other copy is held, and the kept record notes where else it is posted. Rows marked "possible only" or "possibly the same" are kept as separate recordings.

| Band | Kept | Held | Station, frequency |
|---|---|---|---|
| 90 m | 90M-0050 | 90M-0051 | GBS Guyana, 3290 kHz. The full 13:43 recording is kept; 0051 is a 32-second excerpt of it. |
| 90 m | 90M-0054 | 90M-0052 | Action Radio Guyana, 3290 kHz (same file, two uploads). 90M-0053, by a different recordist, stays tunable. |
| 90 m | 90M-0077 | 90M-0076 | Radio Bougainville, 3322.5 kHz. 0076's link failed on October 16. |
| 90 m | 90M-0101 | 90M-0102 | Radio Éxitos (HIRL), 3365 kHz. The cleaned MP3 is kept over the uncleaned M4A. |
| 90 m | 90M-0121 | 90M-0120 | Radio Rabaul, 3385 kHz |
| 90 m | 90M-0122 | 90M-0123 | Radio Rabaul, 3385 kHz |
| 49 m | 49M-0042 | 49M-0041 | BBC World Service, 5975 kHz |
| 49 m | 49M-0058 | 49M-0059 | Radio Tashkent, 5985 kHz |
| 49 m | 49M-0168 | 49M-0169 | HCJB DX Partyline, 6095 kHz |
| 49 m | 49M-0170 | 49M-0171 | HCJB 45th anniversary, 6095 kHz |
| 49 m | 49M-0220 | 49M-0221 | Voice of Biafra, 6145 kHz |
| 49 m | 49M-0293 | 49M-0294 | Radio Liberación (SRRN), 5929.3 kHz |
| 49 m | 49M-0301 | 49M-0302, 49M-0303 | Radio Difusora Nacional de Nicaragua, 5945 kHz |

## Held compilations and multi-station files

- **90 m:** 90M-0002, 0007, 0014, 0018, 0021, 0028, 0089, 0105, 0132, 0135. This includes the five-station Brazilian file from 1989-05-10 and the Rhodesia tape that is also held on 60 m.
- **49 m:** 49M-0049, 0143, 0161, 0246, 0247. Two of these give segment timestamps and could be cued later.

The full list of the 76 out-of-era 49 m rows is in `band-49m.json` (review reason `outside_era`).

## Frequency handling

- **The dial steps in 0.1 kHz**, so 11 labels with two decimals were rounded to the nearest step. For example, 6218.02 became 6218.0 and 6280.07 became 6280.1. Some of the 11 are held as out of era anyway, such as the two 1991 Radio Juanjuí rows at 6261.12 and 6261.13. The printed label is kept unchanged for the reveal.
- **49M-0319** ("ID said 6,220 (QSL for 6,230)") is placed at 6220 kHz.
- **Written forms such as** `3,290 khz`, `3.290 MHz`, `5.975 MHz` and `3.322.5 MHz` were converted to kHz.

## For your attention

- **Low-confidence rows that stay tunable:**
  - 90M-0034, unidentified ("ID sounding like R. Populares")
  - 90M-0134, ZBC name versus a "mid-late 1970s" date
  - 49M-0079, frequency possibly from the QSL card
  - 49M-0291 and 49M-0348, unidentified
  - 49M-0307, ship in international waters
- **No country for the map.** These recordings are tunable, but the reveal map will say "Transmitter country not established":
  - 49M-0026, 0288, 0321, 0326 (clandestine)
  - 49M-0293 and 49M-0301 (country "Not stated", Nicaragua named only as the target)
  - 49M-0307 (international waters)
  - 90M-0034 (unidentified)
- **Rights:** 117 of 125 tunable 90 m rows and about 240 of 261 tunable 49 m rows give no rights statement. That's the same position as 60 m, so the receiver stays private.

## Files

- `data/bands/band-90m.json`, `data/bands/band-49m.json`: staged catalogs in the receiver's record format. Fields added for the new bands: `band`, `sortKey`, `scope`, `recordingType`, `confidence`, `rights`, `transmitterLocality` and `mapKey`, which stays empty until phase 5.
- `data/bands/band-catalog-review.json`: machine-readable lists of merges, rounding and flags.
- `tools/build-band-catalog.py`: rebuilds everything above from the workbooks.
- `tools/test-band-catalogs.cjs`: counts, dial ranges, fixed order, reachability of every frequency, and an unchanged 60 m catalog.
