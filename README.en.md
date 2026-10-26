# Pleroma — a personal project to keep testing what generative AI builds

Author: Makina Anjo (安城巻那)

[日本語README](./README.md) ・ [Dev log](./DEVLOG.md) ・ [Full record (GRIMOIRE.md, Japanese)](./GRIMOIRE.md)

## Why I built this

I work as a QA engineer. As more code gets written by generative AI, and more systems get run autonomously by AI agents, one question kept bothering me: **who actually verifies the quality of that, and how, on an ongoing basis?**

AI is a confident liar. Code that reports "fixed, verified" can be defeated by a one-character difference. A team can patch one defense layer and never realize a structurally parallel layer never got the same fix, because the two were never actually sharing what they learned. Finding that gap between "looks like it works" and "actually works" — and finding it *repeatedly*, as the code keeps changing — is the real problem.

Pleroma is where I test my own answer to that question, hands-on. AI agents (myself included, running as Claude) write the code; AI agents, following a QA discipline, then try to break it, in a repeating red-team/blue-team cycle. Every real defect that gets found is verified on live infrastructure, fixed, and locked into CI as a permanent regression check — one at a time, logged honestly.

## What's actually happening here

- **Red/blue iteration**: find a new attack pattern (red) → verify on real infrastructure that it actually breaks something → fix it → add a permanent CI check ("angel") that proves the same trick doesn't come back.
- **Layered defense**: file-write restriction (Sanctum), process/network blocking (a separate deep-protection layer), static-analysis code review (Gabriel) — independently maintained layers, on purpose, so a failure in one doesn't quietly take down the others.
- **Mechanically falsifying "I think I fixed it"**: every fix gets turned into a general CI check, and every check gets self-red-teamed with `git stash` — revert the fix, confirm the check correctly FAILS; restore it, confirm it PASSES. Every time, by hand.
- **Making honesty itself a QA target**: the project log (`GRIMOIRE.md`) never reports a finding that wasn't verified on real infrastructure, and it records my own mistakes — including bugs in my own test code — the moment I find them, without exception.

## Where things stand (in numbers)

| | |
| --- | --- |
| Logged findings/fixes (`GRIMOIRE.md`) | §A through §CC, 81 entries |
| Standing CI checks ("angels") | ~50 |
| GitHub Actions workflows | 2, both green |
| Local pytest | 367 passing (5 known, sandbox-only failures) |

## Recent findings

All three share the same shape: the same dangerous *intent* is blocked, but only for one specific API name — a different API that achieves the same effect slips through.

- **Data exfiltration via UDP `socket.sendto()`**: network blocking only checked `"socket.connect"`; UDP needs no `connect()` call at all, so it sailed right through.
- **Sandbox bypass via `mmap`**: mapping a pre-opened file descriptor with `mmap` and writing to it bypassed every existing write-guard wrapper. Worse, the audit event's reported "access level" could be spoofed depending on how `mmap` was called, so the fix stopped trusting that field entirely and checks the resolved file path instead.
- **Process spawning via `os.fork()`**: process-spawn blocking only listed `subprocess.Popen` and three similar APIs; `os.fork()` fires its own, different audit event and was never on the list.

Full write-ups (discovery, analogy, root cause, fix, verification, and honestly-stated limitations) live in `GRIMOIRE.md` (Japanese); a more readable narrative version is in [DEVLOG.md](./DEVLOG.md).

## Structure

- **Sefer**: `sefer/` — file-access restriction via a `Sanctum` context. The part meant to ship as a standalone defense module.
- **Maquina Gatekeeper**: `maquina_gatekeeper.py` — a second, independently maintained deep-protection layer blocking process spawning and network calls.
- **Tartarus**: `tartarus/` — a local-only arena where a red-team AI and a blue-team AI run an evolving self-play loop.
- **Angels**: `angels/` — about 50 standing audit scripts, run on every push via `.github/workflows/anjo_da_maquina_protocol.yml`.

## Commands

See [`COMMANDS.md`](./COMMANDS.md) for the full operator command reference.
