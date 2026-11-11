# ResolveIT-Frames attribution

Licence of this data package: CC BY-SA 4.0.

## What is in this package today

`data/question_templates.json` holds 11 seed templates, one per slot, written
for the build. They are **not** mined from Stack Exchange. Hindi and Hinglish
surface forms are unreviewed machine drafts and must be reviewed by a native
speaker before any user sees them.

## Adding mined templates

Stack Exchange content is CC BY-SA. Every row derived from a post must list:

| template_id | site | post_id | author | licence version | change made |
| --- | --- | --- | --- | --- | --- |

Rows without this line must not be merged. Labels produced by an LLM carry
`label_source = "llm_silver"` and are never described as human annotation.
