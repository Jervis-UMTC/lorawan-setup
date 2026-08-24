---
name: asd-ste100
description: "Use when technical English must be rewritten for low ambiguity. Apply Simplified Technical English principles for manuals, instructions, prompts, errors, and operational documentation. Do not use for creative or marketing text."
version: 0.4.0
---

# Simplified Technical English (ASD-STE100)

Use this skill to make technical text easier for humans and agents to parse.

## Use this skill when

- Instructions can be misunderstood.
- Technical manuals need clearer steps.
- Prompts or tool descriptions need precise wording.
- Logs, errors, and operational messages need simpler language.

Do not use this skill for creative writing or marketing content.

## Modes

### Strict
Use for:
- Procedures.
- Commands.
- Error messages.
- Agent instructions.
- Safety documentation.

Rules:
- Use active voice.
- Use one instruction per sentence.
- Keep instructions short.
- Avoid ambiguous words.
- Keep required technical terms.
- Do not remove conditions or warnings.

### STE-flavored
Use for:
- READMEs.
- Documentation.
- Explanations.

Apply the structure rules but keep necessary technical vocabulary.

## Rewrite rules

1. Use active voice.

Example:

Bad:
"The configuration file is modified by the operator."

Good:
"The operator modifies the configuration file."

2. Write one action per sentence.

Bad:
"Open the file, edit the value, and restart the service."

Good:
"Open the file. Edit the value. Restart the service."

3. Avoid long sentences.

Keep instructions below 20 words when possible.

4. Avoid unclear wording.

Replace vague words with specific actions.

5. Avoid unnecessary noun forms.

Bad:
"Perform a verification of the gateway connection."

Good:
"Verify the gateway connection."

6. Keep technical terms when they are required.

Example:

Keep:
- LoRaWAN
- ChirpStack
- MQTT
- PostgreSQL
- Docker

Define uncommon terms before using them.

## Scan checklist

Check for:

- Different names for the same object.
- Too many qualifiers.
- Marketing words.
- Long sentences.
- Hidden actions inside nouns.
- Ambiguous instructions.

## Output behavior

Default output is only the rewritten text.

If the user requests explanation, provide:

- The violated rule.
- The original text.
- The rewritten text.

Preserve all technical meaning. Do not add facts that were not provided.
