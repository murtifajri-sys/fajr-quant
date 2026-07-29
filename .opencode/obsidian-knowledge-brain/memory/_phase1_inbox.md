---
cold_start:
  total_annotations: 0
  sessions_observed: 0
  threshold: 20
  mode: cold_start
---

# Phase 1 Inbox

Raw annotation stream for the current session.
Add `[DECISION:]` and `[ERROR:]` lines here, or let the Agent extract them at session end.

<!-- Initial bootstrap — no annotations yet. -->

[ERROR: type=telegram-digest-stale-recs | resolution=chain send_daily_digest after run_recommendations_batch instead of fixed countdown=15m | project: fajr-quant]
[ERROR: type=screener-stale-data | resolution=add run_daily_screener to daily pipeline chain before send_daily_digest | project: fajr-quant]
[ERROR: type=edit-import-indent | resolution=import lines landed inside function body; validated with ast.parse before restart | project: fajr-quant]
[ERROR: type=test-invocation-import | resolution=run backend tests with python -m pytest from /app so app package is on sys.path | project: Fajr-Quant]
[ERROR: type=apply-patch-invalid-hunk | resolution=ensure every added-file content line is prefixed with plus | project: fajr-quant]
[ERROR: type=python-command-missing | resolution=use python3 for local backend py_compile validation | project: fajr-quant]
[ERROR: type=frontend-build-cache-permission | resolution=validate Next build from /tmp copy excluding repo-owned .next-app cache | project: fajr-quant]
[ERROR: type=rsync-group-preserve | resolution=copy temp frontend build with rsync -rlt instead of archive mode | project: fajr-quant]
[ERROR: type=validation-command-mixed-language | resolution=run py_compile only on Python files and validate TSX with tsc/eslint | project: fajr-quant]
[ERROR: type=git-ssh-host-key-missing | resolution=add github.com to known_hosts with ssh-keyscan then retry git push | project: fajr-quant]
[ERROR: type=tool-orchestration-syntax | resolution=split combined validation into simple exec calls | project: fajr-quant]
[ERROR: type=git-metadata-unavailable | resolution=validate new markdown directly because mounted .git metadata is inaccessible | project: fajr-quant]
[ERROR: type=python-command-missing | resolution=use python3 for local backend py_compile validation | project: fajr-quant]
[ERROR: type=python-command-missing | resolution=use python3 for local backend test and compile validation | project: fajr-quant]
[ERROR: type=frontend-build-cache-permission | resolution=validate Next build from /tmp copy excluding repo-owned .next-app cache | project: fajr-quant]
[ERROR: type=screener-run-timeout | resolution=proxy custom screener run through Next API route with longer server-side timeout | project: fajr-quant]
[ERROR: type=frontend-build-cache-permission | resolution=validate Next build from /tmp copy excluding repo-owned .next-app cache | project: fajr-quant]
[ERROR: type=bow-setup-overextended | resolution=only label BOW when price is inside or near value zone; route far-above-zone cases to wait_value_area anti-chasing | project: fajr-quant]
[ERROR: type=entry-signal-lag | resolution=add armed breakout setup state so waiting-confirmation tickers expose actionable trigger levels before confirmed Siap Entry | project: fajr-quant]
[ERROR: type=ai-analysis-timeout | resolution=proxy screener AI analysis through Next API route with longer server-side timeout | project: fajr-quant]
[ERROR: type=telegram-message-too-long | resolution=split daily digest into multiple Telegram messages below Bot API limit | project: fajr-quant]
[ERROR: type=test-invocation-import | resolution=run backend tests from backend directory so app package is on sys.path | project: fajr-quant]
