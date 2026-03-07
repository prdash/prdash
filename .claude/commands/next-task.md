Read `WORK_TRACKER.md` and identify the next task that meets ALL of these criteria:
1. Status is "not started"
2. All tasks listed in its dependency column have status "completed"

If no eligible task exists, inform me and stop.

Once you've identified the next eligible task:
1. Read `PRODUCT_GUIDELINES.md` for full feature context
2. Read the task spec file at `tasks/T{NN}.md` (where NN is the zero-padded task number)
3. Load any relevant agent docs referenced in `CLAUDE.md` for the task
4. Present a summary of the task and ask me any clarifying questions to resolve ambiguities before starting implementation
5. Once I confirm, update `WORK_TRACKER.md` to mark the task as "in progress" and begin work
