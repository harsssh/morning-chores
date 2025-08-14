# Morning Chores (朝活) - Git-based Attendance Tracking System

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Project Overview
This is a Git-based attendance tracking system for daily morning activities. Users record daily participation through git commits, and the system automatically generates visualizations and statistics. The system consists of bash scripts for check-ins and Python scripts for data aggregation.

## Working Effectively

### Initial Setup and Validation
- Clone the repository and ensure you are in the git root directory
- Test basic functionality:
  - `python3 scripts/aggregate.py` -- processes git history, takes ~0.1 seconds. NEVER CANCEL.
  - `bin/check-in --help` -- shows usage information
  - `bin/check-in --no-push -m "test message"` -- record test check-in without pushing

### Core Operations
- **Record daily check-in**: `bin/check-in -m "your message"`
  - Automatically uses JST timezone and current date
  - Creates git commit with structured metadata
  - Pushes to remote repository by default
- **Record backdated check-in**: `bin/check-in -d 2025-01-15 -m "forgot yesterday"`
- **Process attendance data**: `python3 scripts/aggregate.py`
  - Scans entire git history for check-in commits
  - Generates CSV data files in `data/` directory  
  - Creates heatmap visualization in `assets/heatmap.svg`
  - Takes ~0.1 seconds. NEVER CANCEL.

### Dependencies and Requirements
- Python 3.11+ (requires `zoneinfo` module)
- Bash shell
- Git (for version control and data storage)
- No external Python packages required - uses only standard library

### Build and Test Process
- **No traditional build process** - this is a data processing system
- **Main validation**: `python3 scripts/aggregate.py && ls -la data/ assets/`
- **Check-in test**: `bin/check-in --no-push -m "test" && git log -1 --oneline`
- Both operations complete in under 1 second. NEVER CANCEL.

## Validation Scenarios

### Complete End-to-End Scenario
Always run this complete scenario after making changes:

1. **Record a check-in**: `bin/check-in --no-push -m "validation test"`
2. **Process the data**: `python3 scripts/aggregate.py`
3. **Verify outputs**: 
   - `cat data/attendance.csv` -- should show new entry
   - `ls -la assets/heatmap.svg` -- should exist and be recent
   - `cat data/per_user.json` -- should show user statistics
4. **Check for warnings**: Duplicate check-ins generate warnings but do not fail

### GitHub Actions Workflow
- Workflow file: `.github/workflows/build.yml`
- Triggers on push to main branch
- Runs `python3 scripts/aggregate.py`
- Commits generated files back to repository
- Takes ~30 seconds total. NEVER CANCEL. Set timeout to 2+ minutes.

## Key Files and Directories

### Scripts and Executables
- `bin/check-in` -- Bash script for recording daily check-ins
  - Creates structured git commits with JST timestamps
  - Handles date specification and push options
  - Usage: `bin/check-in [-m NOTE] [-d YYYY-MM-DD] [--no-push]`

### Data Processing
- `scripts/aggregate.py` -- Python script that processes git history
  - Scans for commits with "check-in" subject or "Check-In-Date" trailer
  - Handles duplicate detection and deduplication
  - Generates multiple output formats (CSV, JSON, SVG)

### Generated Files
- `data/attendance.csv` -- Normalized attendance records
- `data/daily_counts.json` -- Daily participation counts
- `data/per_user.json` -- Per-user participation statistics
- `data/duplicates.csv` -- Log of duplicate check-ins detected
- `assets/heatmap.svg` -- GitHub-style contribution heatmap
- `docs/index.html` -- Web dashboard (static HTML)

### Configuration
- `.github/workflows/build.yml` -- GitHub Actions workflow
- No additional configuration files required

## Common Tasks and Troubleshooting

### Making Code Changes
- Always test with: `python3 scripts/aggregate.py` after modifying the aggregation logic
- Always test with: `bin/check-in --no-push -m "test"` after modifying the check-in script
- **Critical**: The system stores data in git commits, so be careful not to break commit parsing logic

### Data Validation
- Check for duplicates: `cat data/duplicates.csv`
- Verify user mapping: `cat data/per_user.json`
- Inspect recent check-ins: `git log --oneline --grep="check-in" -10`

### GitHub Actions Debugging
- Workflow runs `python3 -u scripts/aggregate.py` with unbuffered output
- Commits are made by github-actions[bot] user
- Only commits changes in `data/` and `assets/` directories

## Common Command Outputs

### Repository Structure
```
ls -la
total 40
drwxr-xr-x 9 runner docker 4096 .
drwxr-xr-x 3 runner docker 4096 ..
drwxr-xr-x 7 runner docker 4096 .git
drwxr-xr-x 3 runner docker 4096 .github
-rw-r--r-- 1 runner docker  445 README.md
drwxr-xr-x 2 runner docker 4096 assets
drwxr-xr-x 2 runner docker 4096 bin
drwxr-xr-x 2 runner docker 4096 data
drwxr-xr-x 2 runner docker 4096 docs
drwxr-xr-x 2 runner docker 4096 scripts
```

### Python Version Check
```
python3 --version
Python 3.12.3
```

### Sample Check-in Usage
```
bin/check-in -m "今日も頑張った"
[main a1b2c3d] check-in 2025-08-15
チェックイン完了: check-in 2025-08-15
```

### Sample Aggregation Output
```
python3 scripts/aggregate.py
::warning::Duplicate check-in 2025-08-15 user (a1b2c3d)
```

## Important Notes
- **Time zone**: All dates are handled in JST (Asia/Tokyo)
- **Commit structure**: Check-ins create commits with "Check-In-Date: YYYY-MM-DD" trailer
- **Duplicate handling**: System automatically deduplicates by preferring earliest commit
- **No external dependencies**: Uses only Python standard library
- **Fast operations**: Both check-in and aggregation complete in under 1 second
- **Git-centric**: All data is stored as git commits, no database required