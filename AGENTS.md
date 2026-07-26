# Fajr-Quant — Agent Instructions

> **Knowledge triggers（强制 / MUST）**: This project uses Obsidian Knowledge
> Brain v4.0. You MUST execute the following at the specified moments.
>
> **Pre** — Before writing new library imports or system calls in a file.
> (Sync once per file; skip if atoms.json mtime unchanged since last sync.
> If the keyword index doesn't exist — project not bootstrapped — skip this
> entire Pre section and proceed.)
>   1. **Sync**: Read `~/.obsidian-knowledge-brain/atoms.json`. Safe-merge
>      into `_global_atoms` section of your keyword index (locate it under
>      your platform's agent directory: `.opencode/obsidian-knowledge-brain/rules/`,
>      `.claude/rules/`, `.cursor/rules/`, or equivalent). Before editing the index, copy to `.bak`.
>   2. **Grep**: Search the keyword index for keywords matching your code.
>   3. **Load**: For matched atoms where `phase: pre`, open the file at
>      `pointer`, read the specified line range. If pointer lines don't match
>      the topic → fall back to loading the entire file.
>
> **During** — When stuck on the same error >2 attempts:
>   Grep the keyword index for error keywords. Load `phase: during` atoms.
>
> **Post** — After resolving any error, BEFORE writing the permanent fix:
>   1. **Load**: Grep for `phase: post` atoms matching the error.
>   2. **Record**: Immediately append a one-line stub to your platform's
>      `memory/_phase1_inbox.md` (under your agent directory):
>      `[ERROR: type=<type> | resolution=<fix> | project: <slug>]`
>      This is the final step of every error fix. NOT deferred to session end.
>
> **Consequence**: Skipping any MUST step and hitting a documented pitfall →
> `[ERROR: type=missed-atom | atom_id=<id>]`. Missing error stub →
> `[ERROR: type=missed-record | error_type=<type>]`. No exceptions.

Project context and rules for AI assistants working on Fajr-Quant.

## Approval Prefix Rules

Saat meminta approval runtime, agent MUST mengusulkan `prefix_rule` yang umum,
stabil, dan cukup sempit untuk dipakai ulang lintas sesi. Hindari rule yang
terlalu spesifik ke endpoint, `task_id`, query string, atau command shell
gabungan bila ada versi prefix yang lebih umum dan aman.

Contoh prefix yang diprioritaskan untuk project ini:
- `["curl", "-sS", "http://localhost:8000/api/v1/tasks"]`
- `["curl", "-sS", "http://localhost:8000/openapi.json"]`
- `["docker", "compose", "logs"]`
- `["docker", "compose", "ps"]`

## Broker Flow Daily Follow-up

Setelah coverage broker flow `30` hari sudah aman/penuh, revisi scheduler harian:
- Jangan lagi bergantung pada slot tetap `19:00 WIB` dan `19:30 WIB` untuk
  maintenance normal.
- Ubah menjadi urutan dependensi: `daily data load` selesai dulu, lalu satu kali
  fetch/update broker flow harian yang dibutuhkan, lalu `daily screener`.
- Backfill/retry tambahan hanya dipakai jika coverage turun atau fetch harian
  gagal, bukan sebagai dua jadwal rutin tetap.
