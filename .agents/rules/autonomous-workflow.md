# Rule: Autonomous Execution Post-Plan Approval

## Context
Standard operating procedure for handling tasks, feature requests, and refactoring within this workspace.

## Workflow

1. Plan Submission:
   - When given a task or requirement, the agent must formulate a clear implementation plan detailing what will be done, how it will be executed, which files will be created or modified, and how changes will be verified.
   - The agent waits for user review and approval before making modifications.

2. Full Autonomy Post-Approval:
   - Once the user reviews and approves the plan, the agent must execute all implementation and verification steps autonomously from start to finish.
   - The agent must not pause to ask for trivial confirmations or break execution into unnecessary manual checkpoints.
   - Only stop if a blocking technical issue, unexpected error, or ambiguous architectural conflict arises that cannot be resolved automatically.

3. Verification and Reporting:
   - After executing, run the test suite to verify correctness.
   - Deliver a concise summary of completed changes.
