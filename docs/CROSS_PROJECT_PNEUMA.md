# Cross-project: D&TED ↔ Pneuma Sofer (Scriptorium)

**Related product:** [Pneuma Sofer v0.11.0](https://github.com/Hermeneuticus-of-things/Scriptorium) — Scrivener-inspired book editor (GitHub repo name **Scriptorium**; product name **Pneuma Sofer**; older install name Scribner).  
**This repo:** [D&TED](https://github.com/Hermeneuticus-of-things/dted).

## Relationship

Pneuma Sofer uses **D&TED as an optional dictation / transcription engine** (alongside its own built-in whisper.cpp motor since v0.9.0). Integration is **not** a Python import and **not** MCP-to-D&TED:

| Piece | Where (Pneuma / Scriptorium) |
|-------|------------------------------|
| Spec | `docs/DTED.md` |
| Locate + spawn `DTED.exe --serviciu` or `python -m dictare_transcriere_romana --serviciu` | `lib/dted.cjs` |
| Electron IPC | `electron/dtedHandlers.cjs` |
| Editor insert / replace selection | `src/lib/useDictation.js`, `src/lib/dictation.js`, `src/components/DictationBar.jsx` |
| Wire protocol | JSON lines on stdin/stdout, **protocol 1** |

D&TED side: `--serviciu` / `dictare_transcriere_romana/serviciu.py` (see also `docs/SERVICIU.md` when present).

## Requirement: update D&TED from inside Pneuma (manual + periodic)

The owner wants Pneuma to be able to **update / upgrade its referenced D&TED motor** as D&TED improves — even when Pneuma’s previously bundled or last-used D&TED is older or not yet adapted.

### Plan (both products; docs only here)

1. **Versioned D&TED distribution** — publish a wheel and/or a Windows user-folder bundle (e.g. release asset) that Pneuma can pull without admin.
2. **Update check in Pneuma** — at **app startup** and optionally every few days in the background; query a **version manifest** (GitHub Releases for `Hermeneuticus-of-things/dted` and/or a small version JSON URL both products consult).
3. **User-folder install** — download into a per-user path; no admin; switch active path to the new build.
4. **Manual update anytime** — UI control to check/install now, not only on the periodic schedule.
5. **Fallback** — if the new D&TED fails to start or handshake protocol 1, keep / revert to the **last working** D&TED path.
6. **API compatibility** — keep `--serviciu` protocol versioned; Pneuma must refuse or prompt when `protocol` ≠ expected; D&TED must not break protocol 1 clients without a documented bump.

### Shared manifest (sketch)

Example fields: `version`, `protocol`, `win_bundle_url`, `sha256`, `min_pneuma_version`, `notes`. Hosted next to D&TED releases so both apps can read the same source of truth.

## Non-goals (this note)

- Editing application code in either repo as part of this documentation pass.
- Making D&TED the only engine in Pneuma (whisper.cpp built-in remains).
- Public cloud ASR as the update channel.

## Tracking

- D&TED roadmap: [issue #15](https://github.com/Hermeneuticus-of-things/dted/issues/15) (cross-project dependency section).
- Pneuma: `docs/DTED.md` + `docs/DEPENDENCY_UPDATES.md` in Scriptorium.

*Filed 2026-10-26 — documentation / planning only.*
