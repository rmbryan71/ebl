# AI-assisted development workflow

## Goals
- Use AI to speed up development while keeping code quality and security high.
- Maintain human ownership of decisions, reviews, and releases.

## Planning preferences
- Spend extra time on problem definition, scope, and decomposition during planning.
- Present decisions one at a time with pros/cons and recommendations that prioritize simplicity and stability.
- Note that small, one-step fixes do not require plans; decide when complexity warrants a plan.

## When to use AI
- Brainstorming approaches, edge cases, and testing ideas.
- Drafting code changes with clear acceptance criteria.
- Summarizing findings or refactoring for clarity.

## When not to use AI
- For secrets, private keys, or sensitive data.
- For making final decisions without human review.

## Prompting practices
- Provide specific context, desired behavior, and constraints.
- Ask for tests, risks, and alternatives when relevant.
- Prefer small, focused changes over sweeping edits.

## Review and validation
- Treat AI output like a junior developer draft.
- Verify correctness, security, and style before merging.
- Run tests or spot-check critical paths.

## Commit preferences
- Prompt for a commit before executing multi-step plans.
- Prompt for a commit immediately after plans execute.

## Data handling
- Redact or anonymize sensitive data before sharing.
- Avoid pasting full datasets unless required and approved.

## Documentation
- Record AI contributions in PR notes or commit messages when helpful.
- Capture key decisions and assumptions in docs or issues.

## Ownership and accountability
- Human reviewers are responsible for final code quality.
- Do not defer on-call or security decisions to AI output.
