# Cleaner

Cleaner is a Windows-oriented module that **lists** potential cleanup candidates only.
It does not delete anything.

## What it checks

- Cache/temp/log folders with notable size
- Possible uninstall leftovers in AppData/Program Files/ProgramData
- Large directory anomalies (size threshold)
- Basic game-like folder detection (to avoid aggressive assumptions)

## How it avoids false positives

- Reads installed app list from Windows uninstall registry keys
- Reads portable app signatures from optional `--portable-root` paths
- Excludes matched installed/portable names from residue candidates where possible

## Usage

```bat
python Cleaner\cleaner.py
python Cleaner\cleaner.py --top 100 --min-large-mb 2048
python Cleaner\cleaner.py --portable-root D:\PortableApps --portable-root E:\Tools
python Cleaner\cleaner.py --json
```

## Notes

- This module is **report-only**. You decide what to delete manually.
- Run inside `.venv` through `kit.py` launcher for project consistency.


Default portable root includes: `C:\Users\<YourUser>\Repos\Applications`
