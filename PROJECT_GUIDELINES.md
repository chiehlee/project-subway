# Project Development Guidelines

This document contains the base guidelines for developing Project Subway. All AI assistants and future development sessions should follow these guidelines.

---

## About This Document

This file serves as the **primary reference** for anyone (human or AI) working on this project. Review this before each development session to maintain consistency and quality.

**Important**: The user may periodically ask you to "write to guidelines" - this means updating this file with new rules, reminders, or context that should be remembered for future sessions.

## Related Files

### worklogs/ subfolder
Located at `prompts/worklogs/`, this subfolder records the history of AI interactions with this project. Each worklog entry documents what was done, decisions made, and the context of changes.

**Important**: The user may periodically ask you to "write to worklog" - this means creating a new dated entry in the worklogs/ folder summarizing the current session's work.

---

## Project Context

### Basic Information
- **Project Name**: Project Subway
- **Project Path**: `/Users/chieh/Library/CloudStorage/Dropbox/subway/project-subway`
- **Owner**: Chieh (Developer, Restaurant Owner, and sole stakeholder)
- **Purpose**: Operational management application for Chieh's Subway restaurant - streamlining invoice management, transaction tracking, analytics, and reporting
- **Key Technologies**: Python 3.13+, Poetry, MkDocs Material, pandas, opencv-python
- **Project Type**: One-person project - no formal MVP, stakeholders, or phased rollouts

### Important Project Characteristics
- **Developer = Owner = Customer**: Chieh owns the restaurant and is building for himself
- **No MVP concept**: Can build and iterate based on immediate needs without formal phases
- **Agile by necessity**: Requirements and validation come from actual store operations
- **Documentation focus**: Technical and functional requirements, not corporate planning artifacts

### Progress Tracking
- Progress is tracked in the `progress/` folder with three subfolders: `backlog/`, `in-progress/`, and `done/`
- Tasks are organized by week using the naming convention: `W1.md`, `W2.md`, etc.
- Week 1 (W1) = 2026/02/02~2026/02/08, Week 2 (W2) = 2026/02/09~2026/02/15, and so on

---

## Task Management Workflow

This project follows a structured task management process. **Always follow this workflow:**

### 1. Planning Phase
When the user describes what they want to do:
- **Translate** the request into a detailed, executable task
- **Create** a task entry in `progress/backlog/W[N].md` with:
  - Task number (format: #0001, #0002, incrementing)
  - Clear title and description
  - Sub-tasks broken down into actionable steps
  - Rationale explaining why this is needed
  - Acceptance criteria (checkboxes for verification)
  - Date added and priority level

**Task Template:**
```markdown
## Task #XXXX: [Task Title]

### [Brief description]
**Date Added**: YYYY-MM-DD
**Priority**: [Low/Medium/High]

**Description**:
[Detailed explanation of what needs to be done]

**Sub-tasks**:
1. [Actionable step 1]
2. [Actionable step 2]
...

**Rationale**:
- Why this task is important
- What problem it solves

**Acceptance Criteria**:
- ✅ [Specific outcome 1]
- ✅ [Specific outcome 2]
```

### 2. Execution Phase
When the user says "run task #XXXX":
1. **Move** the task from `backlog/` to `in-progress/` (add "Date Started")
2. **Execute** all sub-tasks systematically
3. **Implement** changes and verify against acceptance criteria

### 3. Completion Phase
After completing the task:
1. **Move** the task from `in-progress/` to `done/` 
2. **Add** completion details:
   - Date Completed
   - "What Was Done" section documenting actual changes
   - Mark all sub-tasks with ✅
   - Mark all acceptance criteria with ✅

### Example Reference
See Task #0001 through Task #0004 in `progress/done/W1.md` for complete examples of this workflow.

---

## Git Workflow

### Commit Messages
**When starting a task:**
- Create a commit when beginning work on a task
- Format: `task#0001: [brief description of what you're starting]`
- Example: `task#0001: start documentation consolidation`

**When completing a task:**
- Create a commit when the task is done
- Format: `task#0001: [brief description of what was accomplished]`
- Example: `task#0001: consolidate documentation into README.md`

**Commit message guidelines:**
- Start with task number: `task#0001: `
- Use lowercase for description
- Be concise but clear
- Describe what was done, not how

### Branching Strategy
**Current (One-person development):**
- Work directly on `main` branch
- Commit frequently with task-tagged messages
- No need for feature branches yet

**Future (When needed):**
- May introduce feature branches: `feature/task-0001-description`
- Will merge via PR when collaboration begins
- For now, keep it simple

---

## Guidelines for AI Assistance

### General Principles
- Treat this as a real business project - the code will run in production
- Focus on practical, working solutions over theoretical perfection
- Keep documentation technical and functional, not aspirational
- Remember: developer = owner = customer, so can iterate quickly

### Code Style
- Follow Python 3.13+ best practices
- Use Poetry for dependency management
- Write clear, maintainable code
- Document complex logic with comments

### Documentation
- Keep documentation focused on functional/technical requirements
- Avoid corporate planning artifacts (MVP phases, stakeholder sections)
- MkDocs Material is used for documentation site
- Simple and clear language throughout

### Communication
- Use simple and clear language
- Maintain consistent terminology throughout the project
- Be concise but thorough
- Focus on actionable information

---

## Important Reminders

- This is a **one-person project** - no need for enterprise-level processes
- **Documentation first** - specify before implementing
- **Task-driven development** - always work within the task tracking system
- **Commit frequently** - use task-tagged commit messages
- **Iterate based on needs** - no formal MVP or phased rollouts

---

## Reference Documents
- See `prompts/worklogs/` for historical AI interaction records
- See `progress/` for task tracking and status
- See `docs/` for technical and functional requirements
