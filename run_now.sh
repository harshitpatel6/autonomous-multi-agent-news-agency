#!/bin/bash
# Force-run the email digest pipeline right now, regardless of the last-sent guard
# or the launchd schedule. Use this any time you want tonight's (or any night's)
# newsletter immediately instead of waiting for the next scheduled check.
#
# Usage: ./run_now.sh
cd "$(dirname "$0")" || exit 1
./venv/bin/python3 main.py --force
