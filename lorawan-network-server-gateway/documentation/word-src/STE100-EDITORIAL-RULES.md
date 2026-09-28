# Clear-language rules for the LoRaWAN Operator Manual

Source: https://github.com/danyuchn/asd-ste100-skill (`SKILL.md` and `references/writing-rules.md`). This project uses the principles of the linked skill. It does **not** claim formal ASD-STE100 certification or reproduce ASD's restricted approved-word dictionary.

## Author each procedure in strict mode

1. Use one clear verb per action. Prefer **check** for a comparison, **select** for a UI choice, and **record** for evidence.
2. Give one instruction per sentence. Put complex ordered actions in numbered steps.
3. Use the active voice and simple present, past, or imperative forms.
4. Aim for at most 20 words per instruction sentence. Keep descriptive sentences within 25 words where possible.
5. Start a safety instruction with the condition or command. Never hide **Do not**, **Stop**, or the authorization boundary inside a long sentence.
6. Define a necessary technical term once. Keep actual UI labels, commands, device IDs, paths, frequencies, configuration keys, and security boundaries unchanged.
7. Tell the operator exactly **where** to act: Windows PowerShell, Gateway-01 BusyBox, cloud ChirpStack, or a server shell.
8. Separate an action from its expected output, a PASS criterion, and what to do if the check fails.
9. Do not imply a screenshot or a saved configuration proves that a new sensor, cloud uplink, or research measurement succeeded.

## Use STE-flavored mode for explanations

Use plain, short sentences while preserving the system's exact roles and dependencies. Avoid marketing language, long noun clusters, ambiguous pronouns, hidden assumptions, and unnecessary synonyms.

## Preserve meaning and layout during edits

- Never simplify a line of Bash, PowerShell, SQL, UCI, configuration, JSON, a measured value, or a research pass criterion by changing its literal contents.
- Preserve a stop condition, recovery boundary, approval requirement, exception, or exact version even if the sentence becomes longer.
- Keep full-page genuine screenshots next to the corresponding actions. Do not invent a result or reveal passwords, AppKeys, private keys, or tokens.
- Preserve image geometry, section headings, code blocks, and table values. Render every Word page before publication.
- Do not activate or manipulate the user's desktop browser to make a screenshot. Use isolated background captures.

## Current revision

The STE editorial pass revised **101 prose/instruction paragraphs** across Chapters 1–6. It preserved all **41 embedded visuals**, the 492-paragraph structure, and code blocks. The tracked changes are in `ste-edits-ch1-3.json`, `ste-edits-ch4-5.json`, `ste-edits-ch6.json`, and `ste-edits-supplement.json`. Rebuild from `.before-ste100-language-review-20260922.docx` and the pinned canonical SHA-256 in `build_ste100_manual.mjs`. The inline-style restorer requires `python-docx==1.2.0`, installed into an isolated `word-src/.docx-tools` directory when it runs. Remove that temporary dependency directory after the revision. `build_ste100_manual.mjs` applies them to the pre-revision Word version through OfficeCLI. `restore_ste100_inline_styles.py` retains emphasis through the rewrite. `STE100-TECHNICAL-DIFF-REVIEW.json` records the audit of required numeric and technology terms.

The editorial pass is a readability improvement, not a claim that every word matches the official ASD-STE100 dictionary. Existing first-build photo/screenshot gaps remain in `FULL-SETUP-SCREEN-COVERAGE-AUDIT.md`.
