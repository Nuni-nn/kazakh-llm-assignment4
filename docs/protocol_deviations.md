# Deviations from the Frozen Protocol

## Judge configuration replacement — 2026-11-02

The user supplied a replacement `config/generation_settings.json` after reporting
that the Protocol Freeze had been uploaded. The replacement changes the Judge
from Claude Opus 5.5 (adaptive thinking, medium effort) to Gemini 3.6 Flash
(high thinking level), with a 4,096-token output limit and tools disabled.
The tested-model identity remains hidden from the Judge.

Reason for the Judge replacement: not yet provided by the study team.
The team must supply the reason in the final report; this entry does not amend
the already uploaded Protocol Freeze or establish a Moodle upload timestamp.

Gemini is also a tested model, so possible self-evaluation bias must be reported
as a limitation and assessed through human validation. No Judge calls have been
made by the scripts prepared in this workspace.

The supplied file uses protocol label `A4_FINAL_SIMPLE` and a simplified schema.
The generation scripts translate that schema internally without changing the
supplied file. The tested models, generation settings, 500 prompts, three repeats
and 4,500 planned outputs remain as specified. Retry and word-count rules remain
in `docs/retry_policy.md` and `scripts/word_count.py`.
