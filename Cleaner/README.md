# Cleaner

Cleaner is a Windows-oriented module that **lists** potential cleanup candidates only.
It does not delete anything.

## What it checks

- Cache/temp/log folders with notable size
- Possible uninstall leftovers in AppData/Program Files/ProgramData
- Large directory anomalies (size threshold)
- Basic game-like folder detection (to avoid aggressive assumptions)
- Risk scoring (`score` + `risk_level`) with age-aware weighting
- Incremental snapshot diff (`added / removed / changed`) between runs

## How it avoids false positives

- Reads installed app list from Windows uninstall registry keys
- Builds installed signatures from `DisplayName`, `Publisher`, `InstallLocation`, `UninstallString`, `DisplayIcon`
- Extracts executable/script stems from uninstall/display command paths (e.g. `.exe/.msi/.bat/.cmd/.ps1`) to improve matching
- Reads portable app signatures from optional `--portable-root` paths
- Excludes matched installed/portable signatures from residue candidates where possible

## Usage

```bat
python Cleaner\cleaner.py
python Cleaner\cleaner.py --top 100 --min-large-mb 2048
python Cleaner\cleaner.py --portable-root D:\PortableApps --portable-root E:\Tools
python Cleaner\cleaner.py --snapshot-path cleaner_snapshot.json
python Cleaner\cleaner.py --size-delta-threshold-mb 100 --diff-top 20
python Cleaner\cleaner.py --json
```

## Notes

- This module is **report-only**. You decide what to delete manually.
- Run inside `.venv` through `kit.py` launcher for project consistency.
- Snapshot diff is enabled by default and writes to `cleaner_snapshot.json` (in current working directory).


Default portable root includes: `C:\Users\<YourUser>\Repo\Applications`
