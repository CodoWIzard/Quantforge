#!/usr/bin/env bash
# Refresh the QuantForge progress board so the due-date countdown stays live.
# Silent on success; prints only on failure so a broken refresh is visible.
set -uo pipefail

cd /root/projects/quantforge || { echo "board refresh: repo missing"; exit 1; }

out=$(.venv/bin/python services/discord-bots/progress_board.py post 2>&1)
rc=$?

if [ $rc -ne 0 ] || ! grep -qE 'HTTP 2[0-9]{2}' <<<"$out"; then
    echo "QuantForge board refresh FAILED (rc=$rc)"
    echo "$out"
    exit 1
fi
exit 0
