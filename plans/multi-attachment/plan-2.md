# Multi-Attachment Phase 2: UI Fixes & Migration Resolution

## Overview
Three distinct issues to resolve:
1. **Spacing Issue**: "+ x others" text appears too far from filename in attachment pill
2. **Selection State**: Already-attached files not marked as ticked when re-opening file picker
3. **Migration Error**: Alembic multiple head revisions preventing database migrations

## Important: Docker Container for Migrations
**All Alembic migration commands MUST run inside the Docker container `sparkth-migrations-1`.**

Use the pattern:
```bash
docker exec sparkth-migrations-1 <alembic-command>
```

Example:
```bash
docker exec sparkth-migrations-1 alembic heads
docker exec sparkth-migrations-1 alembic merge <rev1> <rev2> -m "message"
```

To start the migrations container if needed: `make migrations`

---

## Issue 1: Fix Attachment Pill Spacing

### Context
- Component: `frontend/plugins/chat/components/attachment/Pill.tsx`
- Problem: When multiple attachments exist, the display shows "filename + x others" with excessive spacing
- Expected: "+ x others" should appear immediately after filename with minimal gap

### Tasks

#### 1.1 Inspect Pill Component Structure
- **File**: `frontend/plugins/chat/components/attachment/Pill.tsx`
- **Action**: Read the component to identify:
  - How "+ x others" text is currently styled
  - Current CSS classes and Tailwind utilities
  - Layout structure (flex, grid, etc.)
- **Deliverable**: Understand current markup and styling

#### 1.2 Identify Spacing Issue Root Cause
- **Analysis**: Look for:
  - Flexbox justify-between or space-around utilities causing spread
  - Margin/padding on the "+ x others" element
  - Width constraints on parent containers
- **Deliverable**: Document exact CSS causing excessive spacing

#### 1.3 Fix CSS/Tailwind Classes
- **Action**: Modify the Pill component to:
  - Remove any justify-between or justify-around on the container
  - Use justify-start or flex-start
  - Ensure "+ x others" has minimal margin (no left margin, or negative margin if needed)
  - Wrap filename + count in a single flex container with gap-0 or gap-1
- **File to modify**: `frontend/plugins/chat/components/attachment/Pill.tsx`
- **Deliverable**: Updated component with proper spacing

#### 1.4 Test Spacing Fix
- **Action**: Run `make frontend.build` to verify:
  - TypeScript compilation succeeds
  - No ESLint errors
  - Visual inspection: "+ x others" immediately follows filename
- **Test case**: Render Pill with 3+ attachments, verify visual spacing
- **Deliverable**: Confirmed build success and visual correctness

---

## Issue 2: Mark Selected Attachments in File Picker

### Context
- Component: `frontend/components/drive/DriveFilePicker.tsx`
- Problem: When reopening file picker, previously selected attachments have no visual indicator
- Expected: Selected files should show a checkmark or "ticked" state
- Related to: `frontend/plugins/chat/components/ChatInterface.tsx` (or equivalent container managing DriveFilePicker)

### Tasks

#### 2.1 Identify Selection State Management
- **Files to inspect**:
  - `frontend/components/drive/DriveFilePicker.tsx` (component props, state)
  - `frontend/plugins/chat/components/ChatInterface.tsx` or chat plugin container
  - Check how selected attachments are stored/passed to DriveFilePicker
- **Questions to answer**:
  - Does DriveFilePicker receive current selected attachments as a prop?
  - If not, what prop structure would be needed?
  - Where is the file selection state currently managed?
- **Deliverable**: Clear understanding of state flow

#### 2.2 Update DriveFilePicker Props Interface
- **File**: `frontend/components/drive/DriveFilePicker.tsx`
- **Action**: 
  - Add optional prop: `selectedFileIds?: number[]` or `selectedAttachments?: TextAttachment[]`
  - Document in interface what this prop contains
- **Deliverable**: Updated TypeScript interface

#### 2.3 Add Visual Indicator for Selected Files
- **File**: `frontend/components/drive/DriveFilePicker.tsx`
- **Action**:
  - In the file row rendering logic, check if `file.id` is in `selectedFileIds`
  - If selected, add a checkmark icon (lucide-react: `<Check />`)
  - Add appropriate CSS class to highlight or mark the row (e.g., `bg-blue-50`, opacity change, or border)
  - Position checkmark near the file name or in a dedicated column
- **Deliverable**: Files now show visual tick when selected

#### 2.4 Update Parent Component to Pass Selection State
- **Files to inspect & modify**:
  - Chat interface container that renders DriveFilePicker
  - Attachment state management (where selected attachments are tracked)
- **Action**:
  - Extract list of already-selected attachment IDs
  - Pass to DriveFilePicker as prop
  - Example: `<DriveFilePicker selectedFileIds={selectedAttachments.map(a => a.driveFileDbId)} ... />`
- **Deliverable**: DriveFilePicker receives selection state from parent

#### 2.5 Test Selection Indicator
- **Scenario**: 
  1. Select a file in DriveFilePicker
  2. Close the picker
  3. Reopen the picker
  4. Verify previously selected file shows a checkmark
- **Test coverage**: Add test case or manual verification
- **Deliverable**: Confirmed selection state is preserved and visible

---

## Issue 3: Resolve Alembic Multiple Head Revisions

### Context
- Error: `Multiple head revisions are present for given argument 'head'`
- Cause: Migration files were created on divergent branches without being merged
- Location: `app/migrations/versions/`
- Impact: Prevents `make migrations` from running

### Tasks

#### 3.1 Identify Divergent Migration Heads
- **Action**: Run command in Docker container:
  ```bash
  docker exec sparkth-migrations-1 alembic heads
  ```
- **Expected output**: List of revision IDs that are heads (should normally be 1)
- **Deliverable**: Know which revisions are competing heads

#### 3.2 Inspect Migration History
- **Action**: Run command in Docker container:
  ```bash
  docker exec sparkth-migrations-1 alembic history
  ```
- **Review**: Identify:
  - When did the branches diverge (which revision was the common ancestor)?
  - What changes did each branch introduce?
- **Files to inspect**: `app/migrations/versions/*.py`
  - Look at down_revision fields in each head revision
  - Trace back to common ancestor
- **Deliverable**: Clear picture of migration tree structure

#### 3.3 Create Merge Migration
- **Action**: Create a new migration that merges the divergent heads in Docker:
  ```bash
  docker exec sparkth-migrations-1 alembic merge <head1> <head2> -m "merge divergent attachment migrations"
  ```
  Replace `<head1>` and `<head2>` with the revision IDs from Task 3.1
- **Important**: Let Alembic auto-generate the merge; do NOT hand-edit it
- **Verify**: 
  - The new migration file is created in `app/migrations/versions/`
  - File should have TWO down_revision entries (a tuple of both head revisions)
  - Example format in file: `down_revision: Union[str, Sequence[str], None] = ("<head1>", "<head2>")`
- **Deliverable**: New migration file that brings branches together

#### 3.4 Apply Merged Migration
- **Action**: Run migrations via Docker:
  ```bash
  make migrations
  ```
  This starts the migrations container and applies all pending migrations
- **Expected result**: All migrations should apply successfully; no more "multiple heads" error
- **Verification**: After success, run:
  ```bash
  docker exec sparkth-migrations-1 alembic heads
  ```
  Should show only 1 head revision (not 2)
- **Deliverable**: Database migrations applied cleanly

#### 3.5 Commit Migration Resolution
- **Action**: 
  - Stage only the new merge migration file
  - Create commit with message: `chore(migrations): merge divergent migration heads`
  - Push to branch
- **Deliverable**: Clean commit history with migration resolved

---

## Execution Order

**Recommended sequence** (can be parallelized):
1. **Parallel tracks**:
   - **Track A** (Issues 1 & 2): Frontend UI fixes
     - Task 1.1 → 1.2 → 1.3 → 1.4
     - Task 2.1 → 2.2 → 2.3 → 2.4 → 2.5
   - **Track B** (Issue 3): Backend migration fix
     - Task 3.1 → 3.2 → 3.3 → 3.4 → 3.5

2. **After both tracks complete**:
   - Run full `make frontend.build` to verify no regressions
   - Run `make test` to ensure no test breakage
   - Verify UI visually in browser (spacing, selection indicators)

---

## Testing Checklist

- [ ] Pill component: spacing of "+ x others" looks correct (immediately after filename)
- [ ] DriveFilePicker: previously selected files show checkmark when reopened
- [ ] Alembic: `alembic heads` shows single revision (no multiple heads error)
- [ ] Frontend build: `make frontend.build` succeeds with 0 errors, 0 warnings
- [ ] Tests: `make test` passes (or skipped tests remain skipped)
- [ ] Manual browser test: attachment selection flow works end-to-end

---

## Notes

- **Issue 1 priority**: Low impact (cosmetic), quick fix
- **Issue 2 priority**: Medium (UX improvement), moderate complexity
- **Issue 3 priority**: High (blocker for further work), critical
- **Dependencies**: Issues 1 & 2 are independent; Issue 3 should be resolved before any new migrations
- **Rollback risk**: Low — all changes are additive or CSS-only; migration merge is safe per Alembic design
- **Docker constraint**: All Alembic commands for Issue 3 MUST run inside `sparkth-migrations-1` container using `docker exec`
- **Container lifecycle**: Container is started by `make migrations` and runs the upgrade. For interactive commands, ensure container is running or start it with `docker compose up -d migrations`

