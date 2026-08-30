# v5.432 Timeout Cleanup + Project Design Restore

## Theme 5-minute timeout

- Backend hard deadline remains 300 seconds.
- Timeout marks the job FAILED immediately, then exposes a cleanup lifecycle:
  `running -> complete`.
- Backend completion is confirmed only after the owning execution stack has unwound and AgentStudio Theme worker processes are gone.
- Job snapshots expose `backend_execution_active`, `backend_analysis_ended`, `backend_cleanup_completed`, `backend_terminated_at`, and worker counts.
- The Theme import UI keeps polling a timeout failure until Backend cleanup completion is confirmed.
- Scheduler shows `Backend 종료 처리 중` or `Backend 종료 확인됨` for UI Theme jobs.

## Existing project restore

- Loading a registered project automatically reads the project-local design checkpoint.
- Restores interview context, target Workflow, Architecture, DB plan, finalized DDL, build stage, and runtime workflow state.
- Project-load autosave is blocked while restoration is in progress so a transient empty render cannot overwrite the previous checkpoint.
- If the checkpoint was saved just before DB finalization, the generated `backend/migrations/001_initial_schema.sql` is used to hydrate the restored DB plan.
- A project with restored design state opens directly on the Target Workflow view.
