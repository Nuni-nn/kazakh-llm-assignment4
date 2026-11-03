# Deviations from the Frozen Protocol

## Selected-200 Run A profile — 2026-11-03

The user supplied Selected_200_Prompts_Tracker_with_Gemini.xlsx and requested code
changes, with responses to be supplied later. A separate selected200 profile follows
its 200 selected prompts and Run A sheets: 200 prompts x 3 models x 1 run = 600
planned outputs. Selection is supplied by the team, not asserted to be random or
unbiased. All selected prompt rows were checked against the original dataset.
The original 500-prompt, three-run profile and its records are retained separately.

For this revised profile Gemini uses high thinking with maxOutputTokens=8192,
instead of 2048, because the original logs showed thinking consuming most of the
budget and 15 of 17 received responses ending with MAX_TOKENS. This is a disclosed
post-observation change, not the original frozen configuration. The new limit
does not guarantee every response will be complete. No old output is regenerated,
removed or automatically mixed into this revised profile. Existing tracker
responses are not yet imported. GPT sheet notes such as 'Codex; default model'
do not establish the frozen GPT-6 Astra identity and must be verified or reported
as unverified when the actual responses are imported.

The reduced single-run study cannot supply three-run variability estimates and
cannot be described as completing the original 4500-output frozen experiment.
These differences and the selection procedure must be described in the report.

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

## Manual OpenAI/Claude collection and daily Gemini batches — 2026-11-02

The study team chose manual collection for GPT-6 Astra and Claude Sonnet 5.5
because OpenAI API credits were exhausted and Claude was already planned for
manual collection. Gemini remains on the API, collected in batches as daily quota
allows. No background scheduler is installed. The default runner now selects only
Gemini; the overall model/prompt/repeat plan remains 4,500 slots.

Manual responses must use independent fresh chats and unchanged prompt text.
Record the actual model label, interface, timestamp with timezone, and settings
that were actually available. Do not assert API settings or immutable model
versions that the chat interface does not expose. Differences in system prompts,
context, token limits, tools and reasoning controls may confound model comparisons
and must be reported. No manual response has been collected by this change.

Original failed API attempts remain in the journal. A manual response for a failed
OpenAI slot is an explicitly documented collection-mode deviation, not an erased
failure. The combined export preserves the preceding API status; received API
answers cannot be overwritten through the manual importer.

The interrupted Gemini request RUN0114 attempt 1 has no recorded response.
It is marked UNKNOWN in derived exports, without inventing a provider outcome or
altering the original journal. It is excluded from automatic re-submission pending
provider-log reconciliation. Other untouched slots may proceed.

Runner maintenance stops a batch on exhausted credits/daily quota and retains
unused retry budget. Existing exhausted failures remain terminal. The initial
manifest stays unchanged; runner code revisions are logged separately after
checking that the frozen experiment files are unchanged.
