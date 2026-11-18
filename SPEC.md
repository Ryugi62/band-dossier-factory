# SPEC: reproducible evidence scripts (docs/model-spend, docs/ui)

kind: analysis

## Purpose (목적)
Let a reader re-derive two claims of this repository from the clone instead of trusting them: the model spend of the four seats, and the ten UI screenshots.

## Success conditions (성공 조건)
- Given `docs/model-spend/usage.jsonl` (usage fields only), When `python3 -m unittest docs/model-spend/test_aggregate.py` runs, Then total tokens are 287,781,523 and the estimate is USD 96.94, in the all-records and the room-window pass alike.
- Given Docker, Chromium and the organizer's mock web, When `python3 docs/ui/capture.py` runs, Then it writes the five states at 375 and 1280 px (ten PNG files) with no hand editing.

## Non-goals (비목표)
Reading the Claude Code session logs from this repository (they stay on the operator's machine; `extract.py` documents how the usage fields were pulled). Changing any `stage-N/` folder.
