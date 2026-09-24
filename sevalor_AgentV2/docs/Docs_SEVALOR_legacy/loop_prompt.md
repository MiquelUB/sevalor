---

### 3. Document `loop_prompt.md` (Loop Prompt)

```markdown
### AGENTIC LOOP EXECUTION DIRECTIVE

You are currently inside an iteration cycle of the SEVALOR audit process.

At the beginning of each turn, perform the following sequence:

1. **State Evaluation:**
   - Inspect `checklist.md` and read the last entry in `audit_log.md`.
   - Identify the immediate next pending checklist item.

2. **Context & Attachment Check:**
   - Verify if the item requires document inspection (e.g., planos, PDF exports, images) or cross-referencing with `context.md` (architectural layers: Personas, Activos, Operaciones, Economía, Información).
   - If visual verification is required, take a screenshot and save it under `evidence/`.

3. **Action Execution:**
   - Execute the browser interaction or API inspection required for the single test item.
   - For offline tests: trigger network disconnection, perform PWA action, re-enable network, and monitor Dexie/IndexedDB background sync to PostgreSQL.

4. **Record Result:**
   - Format the findings using the mandatory output schema.
   - Append the entry to `audit_log.md` and check off the item in `checklist.md`.

5. **Stop / Transition Condition:**
   - If pending tests remain: state what test will run next and invoke the next tool call.
   - If all tests are finished: compile the final tally:
     ```text
     TOTAL PRUEBAS:
     PASS:
     PASS-OBS:
     PARTIAL:
     FAIL:
     UX:
     SECURITY:
     PERFORMANCE:
     NO-VERIFIED:
     ```
     Followed by the final strategic justification for Spanish SMEs (10-30 employees).