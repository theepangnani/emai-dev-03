### 6.85 Upload Wizard Class Selection Fix (Phase 2) - IMPLEMENTED

Fixed upload material wizard losing class selection and resetting on prop changes. Added child context display and switching for parent users.

**GitHub:** #1616, #1625 (PRs #1501, #1540, #1543, #1544, #1624)

**Implementation:**
- Prevent wizard from resetting when parent component re-renders on step 2
- Class selection now persists and is applied to uploaded material
- Class selector always visible and mandatory
- Test mocks updated for coursesApi
- Modal header shows selected child's name for parent users
- Child switcher dropdown when parent has multiple children (classes update on switch)

### 6.86 Collapsible Dashboard Panels and Simplified View (Phase 2) - IMPLEMENTED

Dashboard panels (Tasks Overview, Recent Activity) are collapsible; simplified view collapses them by default.

**GitHub:** #1617 (PRs #1507, #1509, #1511, #1512, #1514, #1542, #1559)

**Implementation:**
- Tasks Overview and Recent Activity panels have collapsible headers
- Simplified view mode: both panels collapsed by default, expandable on demand
- Full view mode: both panels expanded by default, collapsible on demand
- Clicking a child tab in Simplified mode switches to Full and expands both panels
- Panel collapsed state is controlled by ParentDashboard (parent-owned state, not internal component state)
- Activities limited to 5 items with "View All" link
- Child cards on My Kids page: uniform size, three-dots menu (Edit/Remove)
- Student dashboard: collapsible panels, updated quick actions, calendar on tasks page
- Existing users force-reset to simplified view mode

### 6.87 Parent Activity Feed Filtering (Phase 2) - IMPLEMENTED

Parent Recent Activity filtered to show only study guides and messages.

**GitHub:** #1618 (PRs #1516)

**Implementation:**
- `GET /api/activity/recent` filters to study_guide and message types for parents
- Empty Recent Activity section hidden in simplified view
- Child filter properly excludes unrelated children's activity

### 6.88 Create Class Wizard Polish (Phase 2) - IMPLEMENTED

Refined the Create Class wizard UX with multi-step flow and improved component interactions.

**GitHub:** #1619 (PRs #1578, #1580, #1583, #1585, #1587, #1589)

**Implementation:**
- Parent Create Class: 3-step wizard (class details → teacher → students)
- Ported redesigned modal to CoursesPage
- SearchableSelect: sticky "Create New" action at top of dropdown
- Wizard modal: removed unnecessary scrollbars, added min-height to teacher step
- Step 3: inline Add Child form, then replaced with full Add Child modal
- Child selection: replaced checkboxes with MultiSearchableSelect

### 6.89 Dashboard Quick Actions Reorganization (Phase 2) - IMPLEMENTED

Reorganized and expanded quick action buttons on parent/student dashboards.

**GitHub:** #1620 (PRs #1590, #1567, #1595)

**Implementation:**
- Added: Quiz History, Add Child, Export Data, Reset Password, Create Class
- Removed: duplicate Upload Material, Add Action (+) button from child selector
- Reordered actions for better discoverability
- Task count badge on Tasks Overview panel header
- **View Class Material** quick action button added to My Kids page (📄 icon → `/course-materials`) (#1931, PR #1932)

### 6.90 MyKidsPage Final Polish (Phase 2) - IMPLEMENTED

Final polish for the redesigned My Kids page layout and navigation.

**GitHub:** #1622, #1626 (PRs #1612, #1613, #1614)

**Implementation:**
- School name displayed below student name in child selector tabs
- View button navigates to course material detail page (not list)
- Panel headers use shared SectionPanel component for consistency

---

### 6.91 Source Files Quick Navigation Button - PLANNED

Add a "Source Files" button in the document tab action bar (next to Upload/Replace Document) so users can quickly discover and navigate to source files without scrolling.

**GitHub:** #1639

**Acceptance Criteria:**
- [ ] Button visible next to Upload/Replace Document when source files exist
- [ ] Clicking scrolls to and expands the Source Files section

**Status:** PLANNED

---

### 6.92 Activity History Page (Phase 2) - IMPLEMENTED

Dedicated `/activity` page for parents to view full paginated activity history with filtering.

**GitHub:** #1547 (closed), #1683 (PR ✅ merged)

**Acceptance Criteria:**
- [x] "View All" link in Recent Activity panel navigates to `/activity`
- [x] Activity History page shows all activity types
- [x] Child filter chips (same as dashboard)
- [x] Activity type filter
- [x] Pagination (load more)
- [x] Responsive design
- [x] Back navigation to dashboard

**Status:** IMPLEMENTED

### 6.93 GCS File Storage Migration - COMPLETE

Migrate source file and image blobs from PostgreSQL (`LargeBinary`) to Google Cloud Storage to reduce DB size, improve download performance, and lower storage costs (~8-9x cheaper than Cloud SQL per GB).

**GitHub:** #1643 (issue), #1689 (migration PR ✅ merged), #1690 (backfill issue), #1691 (backfill PR ✅ merged), #1697 (column drop ✅ merged), #1704 (test fixes ✅ merged)

**Infrastructure:**
- GCS bucket `gs://classbridge-files` created (us-central1, uniform access)
- Cloud Run service account granted `storage.objectAdmin` on bucket
- `GCS_BUCKET_NAME=classbridge-files` and `USE_GCS=true` set on Cloud Run `classbridge` service

**Acceptance Criteria:**
- [x] `SourceFile` and `ContentImage` models gain nullable `gcs_path` column
- [x] New `gcs_service.py` with upload/download/delete helpers
- [x] Upload routes write to GCS when `USE_GCS=true`; store `gcs_path`, skip `file_data` blob
- [x] Download routes: filesystem → GCS → DB blob fallback chain
- [x] Delete routes clean up GCS objects
- [x] DB migrations for new columns
- [x] Backfill script `scripts/backfill_blobs_to_gcs.py` — idempotent, `--dry-run` support, handles all MIME types (#1691)
- [x] Run backfill script in production — 9 SourceFiles + 9 ContentImages migrated, 0 failed (2026-03-14)
- [x] Drop `file_data` / `image_data` columns (#1697/#1704 ✅ deployed 2026-03-14)

**Status:** COMPLETE — all blobs migrated to GCS; `file_data`/`image_data` columns dropped from DB

---

### 6.94 Scroll-to-Top Button on Course Material Detail Page - COMPLETE

A floating scroll-to-top button on the Course Material Detail page (`/course-materials/:id`) so users can quickly return to the top after scrolling through long content (study guides, documents, quizzes, etc.).

**GitHub:** #1686 (issue), #1687 (initial PR ✅ merged), #1692 (fix: IntersectionObserver approach ✅ merged)

**Acceptance Criteria:**
- [x] Floating circular button appears at bottom-left of viewport after scrolling down
- [x] Button does not appear on initial page load (before any scroll)
- [x] Clicking the button smoothly scrolls the user back to the top
- [x] Button is visible on all tabs (Guide, Quiz, Flashcards, Mind Map, Videos, Briefing, Document)
- [x] Button does not conflict with Chat/Notes FABs (positioned bottom-left, FABs are bottom-right)
- [x] Uses IntersectionObserver on a sentinel element (robust — works regardless of scroll container)

**Status:** COMPLETE

---

### 6.95 SpeedDialFAB Batch 4 Feature Parity (#1761) - COMPLETE

Port chatbot batch 4 features (streaming SSE, search result limits, chat commands) to the SpeedDialFAB component to maintain parity with the standalone chatbot panel.

**GitHub:** #1761 (closed), PR #1762 (merged 2026-03-14)

**Acceptance Criteria:**
- [x] SpeedDialFAB supports streaming SSE responses
- [x] SpeedDialFAB shows search result limits and counts
- [x] SpeedDialFAB intercepts `/clear` and `/reset` commands

**Status:** COMPLETE

---

### 6.96 course_content_id Navigation from Tasks Page (#1763) - COMPLETE

CLASS MATERIAL linked resources on the Tasks page were not navigable. Add click-through navigation using `course_content_id` so users can jump from a task's linked class material directly to the course material detail page.

**GitHub:** #1763 (closed), PR #1766 (merged 2026-03-14)

**Acceptance Criteria:**
- [x] CLASS MATERIAL chip on Tasks page is clickable
- [x] Clicking navigates to `/course-materials/:course_content_id`
- [x] Works for all linked resource types (study guides, quizzes, flashcards)

**Status:** COMPLETE

---

### 6.97 Scroll-to-Top Button on StudyGuidePage (#1767) - COMPLETE

Add a floating scroll-to-top button on the dedicated StudyGuidePage (`/study/guide/:id`), matching the existing scroll-to-top button on the Course Material Detail page (§6.94).

**GitHub:** #1767 (closed), PR #1770 (merged 2026-03-14)

**Acceptance Criteria:**
- [x] Floating circular button appears after scrolling down on StudyGuidePage
- [x] Clicking smoothly scrolls back to top
- [x] Consistent styling with §6.94 scroll-to-top button

**Status:** COMPLETE

---

### 6.98 Master/Sub Class Material Hierarchy for Multi-Document Uploads (#1740)

When a user uploads multiple documents (with or without pasted text content), the system creates a **master Class Material** and one **sub Class Material per attachment**, forming a parent-child hierarchy. This enables users to work with large source documents by generating study tools on demand per sub-material rather than failing on oversized combined content.

**Motivation:** Large uploaded documents can exceed AI context limits, making it impossible to generate a single comprehensive study guide. By splitting into master + sub-materials, users can generate study guides per section/file on demand.

**Related:** #993 (multi-document support — separate concept, stays open), #1594 (hierarchical study guides)

#### Rules

1. **Master + Sub Creation on Multi-File Upload**
   - Create 1 master Class Material + 1 sub Class Material per attachment (e.g., 3 files → 3 subs)
   - Maximum **10 files** per upload — reject with validation error if user selects more than 10

2. **Master Material Content (with pasted text)**
   - Master holds the pasted text content and is a valid Class Material eligible for study guide generation
   - Master title is **auto-derived from pasted text content** — user can modify afterward

3. **Master Material (no pasted text)**
   - First uploaded document becomes the master Class Material
   - Remaining documents become sub-materials

4. **Study Guide Auto-Generation at Upload Time**
   - If study guide generation is requested (Step 2 of wizard), generation is **only triggered for the master**
   - Sub-materials do not auto-generate at upload time

5. **Linked Materials Panel — Master View**
   - All tabs (Original Document, Study Guide, Quiz, Flashcards) show a **collapsible "Linked Materials" panel at the top**
   - Lists all sub-materials as clickable links
   - Clicking navigates to that material's detail page; supports back-and-forth navigation

6. **On-Demand Generation for All Materials**
   - After upload, any material (master or sub) can generate study guides, quizzes, flashcards on demand
   - No restrictions on sub-material generation — business as usual

7. **Linked Materials Panel — Sub-Material View**
   - All tabs show the same collapsible "Linked Materials" panel at the top
   - Lists master + all sibling sub-materials as clickable links

#### Sub-Material Naming

Auto-named with suffix pattern: `"Master Title — Part 1"`, `"Master Title — Part 2"`, etc. User can edit the name later.

#### Data Model

```sql
ALTER TABLE course_contents ADD COLUMN parent_content_id INTEGER REFERENCES course_contents(id);
ALTER TABLE course_contents ADD COLUMN is_master BOOLEAN DEFAULT FALSE;
ALTER TABLE course_contents ADD COLUMN material_group_id INTEGER;
```

Self-referencing FK: `parent_content_id` on `course_contents` (master has NULL, subs point to master). `material_group_id` groups master + subs for efficient querying.

#### UI Changes

**Upload Wizard (Step 1 / Step 2):**
- When multiple files detected: show info message explaining master/sub structure
- Master title input applies to master material
- Sub-materials auto-named with suffix (editable later)

**Course Material Detail Page — All Tabs:**
- Collapsible "Linked Materials" panel at the top of every tab
- Master view: lists sub-materials with links
- Sub view: lists master + all sibling subs with links
- Clicking a link navigates to that material; back/forth navigation supported

#### Acceptance Criteria

- [x] Uploading 3 files + pasted text → 1 master (pasted text) + 3 sub-materials
- [x] Uploading 3 files without pasted text → 1 master (first file) + 2 sub-materials
- [x] User can select master document from file list during multi-file upload (#2051)
- **Rule 3a (User-selected master):** In the upload wizard Step 2, users can click any file in the "Materials that will be created" preview to designate it as master. Default remains first file. Files are reordered before upload so the selected master is first in the array.
- [x] More than 10 files → validation error, upload rejected
- [x] Auto study guide generation at upload only triggers for master
- [x] Master detail page: all tabs show collapsible "Linked Materials" panel at top with sub-material links
- [x] Sub detail page: all tabs show collapsible "Linked Materials" panel at top with master + sibling links
- [x] On-demand study guide/quiz/flashcard generation works for all materials (master and sub)
- [x] Sub-materials auto-named as "Master Title — Part N", editable by user
- [x] DB migration: `parent_content_id`, `is_master`, `material_group_id` added in `main.py` startup

**GitHub:** #1740

**Status:** IMPLEMENTED

### 6.99 Multi-Document Management for Existing Materials (#993)

Extend the material hierarchy (§6.98) to support **post-creation management** of attached files. Users can add more files to an existing material, reorder sub-materials, and delete individual sub-materials.

**Motivation:** After initial multi-file upload, users need to attach additional documents (e.g., an answer key added later), reorganize sub-materials, or remove files that were uploaded by mistake.

**Related:** §6.98 (#1740 — master/sub hierarchy, already implemented), #991 (multi-file upload, closed)

#### 6.99.1 Add Files to Existing Material

- **Endpoint:** `POST /api/course-contents/{content_id}/add-files`
- Accepts up to 10 files per request
- If target is a standalone material (no hierarchy): promote to master, create subs for new files
- If target is a master material: create new subs linked to the existing group
- If target is a sub-material: add files to the parent master's group
- Extracts text from each new file, appends to master's combined text
- Creates SourceFile records for each new file (GCS storage)
- Updates `source_files_count` on response

#### 6.99.2 Reorder Sub-Materials

- **Endpoint:** `PUT /api/course-contents/{content_id}/reorder-subs`
- Accepts `{ sub_ids: [int] }` — ordered list of sub-material IDs
- Updates `display_order` on each sub-material
- Only master material owner or course member can reorder

#### 6.99.3 Delete Sub-Material

- **Endpoint:** `DELETE /api/course-contents/{content_id}/sub-materials/{sub_id}`
- Deletes the sub-material, its SourceFile(s), ContentImage(s), and GCS files
- Updates master's combined `text_content` (removes deleted file's text)
- If last sub deleted, demote master back to standalone material
- Archives linked study guides on the deleted sub

#### 6.99.4 Frontend — Add More Files

- "Add More Files" button in DocumentTab actions bar (visible on master or standalone materials)
- Opens file picker (same accepted types as upload wizard)
- Shows upload progress
- Refreshes SourceFilesSection and linked materials after upload

#### 6.99.5 Frontend — Reorder Sub-Materials

- Drag-and-drop or up/down arrow buttons in LinkedMaterialsPanel
- Persists order via reorder endpoint
- Visual feedback during reorder

#### 6.99.6 Frontend — Delete Sub-Material

- Delete button (trash icon) on each sub-material in LinkedMaterialsPanel
- Confirmation dialog before deletion
- Refreshes panel after deletion

#### Acceptance Criteria

- [x] "Add More Files" button visible on master and standalone materials
- [x] Adding files to standalone material promotes it to master with hierarchy
- [x] Adding files to master creates new subs in existing group
- [x] Sub-materials can be reordered via display_order
- [x] Individual sub-materials can be deleted with confirmation
- [x] Deleting last sub demotes master to standalone
- [x] Master text_content updated when subs added/removed
- [x] All file operations use GCS storage in production
- [x] Backend tests cover all 3 new endpoints
- [x] Frontend build and lint pass

**GitHub:** #993

**Status:** IMPLEMENTED

### 6.100 Sub-Study Guide Generation from Text Selection (#1594)

Generate **child study guides** (study guides, quizzes, flashcards) from selected text within an existing study guide. The child guide is contextually linked to its source, enabling deeper topic exploration.

**Motivation:** Students reviewing a study guide often need to drill deeper into a specific section — more practice questions on one topic, flashcards for key terms, or a deeper explanation. This feature lets them select text, right-click, and instantly generate focused sub-guides.

**Related:** §6.98 (material hierarchy), #993 (multi-document management)

#### 6.100.1 Wire Up TextSelectionContextMenu in StudyGuidePage

- `TextSelectionContextMenu` already has "Generate Study Guide" and "Generate Sample Test" items — currently NOT used in StudyGuidePage
- Wire up the right-click context menu alongside the existing `SelectionTooltip` (which stays as-is, "Add to Notes" only)
- Right-click "Generate Study Guide" or "Generate Sample Test" opens the type selection modal
- Keep `SelectionTooltip` unchanged (single "Add to Notes" button)

#### 6.100.2 Generate Sub-Guide Modal

- Triggered by context menu "Generate Study Guide" or "Generate Sample Test"
- Modal displays the selected text as context preview (truncated to ~200 chars)
- Three type cards to choose from:
  - **Study Guide** — deeper explanation of the selected topic
  - **Quiz** — practice questions from the selected content
  - **Flashcards** — key terms and definitions from the selection
- Optional "Focus prompt" input (e.g., "make it harder", "explain for grade 4")
- "Generate" button (disabled when AI limit reached)
- Shows AI credit info: "Uses 1 AI credit. X remaining."
- Designed with /frontend-design skill — distinctive, polished UI

#### 6.100.3 Backend — Sub-Guide Generation

- **Data model:** Add `relationship_type` (VARCHAR(20), DEFAULT 'version') and `generation_context` (Text) columns
  - Reuse existing `parent_guide_id` for BOTH version chains and sub-guide hierarchy
  - `relationship_type`: `"version"` (regeneration, existing behavior) or `"sub_guide"` (topic child)
  - `generation_context`: the selected text that triggered generation
- **Endpoint:** `POST /api/study/guides/{guide_id}/generate-child`
  - Input: `{ topic: string, guide_type: string, custom_prompt?: string }`
  - AI prompt: parent guide content (truncated intelligently) + selected text as focus
  - Inherits `course_id`, `course_content_id` from parent
  - Sets `parent_guide_id` = source guide, `relationship_type` = "sub_guide"
  - Sets `generation_context` = selected text
  - Returns `StudyGuideResponse`
- **Endpoint:** `GET /api/study/guides/{guide_id}/children` — list sub-guides (where `parent_guide_id = id AND relationship_type = 'sub_guide'`)
- **Migration:** `ALTER TABLE study_guides ADD COLUMN relationship_type ...` and `generation_context` in `main.py`
- Existing version chain behavior unchanged (defaults to `relationship_type = 'version'`)

#### 6.100.4 Sub-Guide Navigation & Display

- **Child guide page:** "Generated from: [Parent Title]" breadcrumb link at top for back-navigation
- **Sub-Guide badge:** When viewing a sub-guide on StudyGuidePage, display a green "Sub-Guide" badge pill next to the title to clearly distinguish it from parent guides
- **Parent guide page:** "Sub-Guides (N)" expandable section showing all child guides with links
- **Course material detail page:**
  - "Sub-Guides (N)" banner links to the parent study guide page
  - `findRootGuide()` helper ensures the root/parent guide is always displayed in the study guide tab, preventing sub-guides from replacing the parent on reload
  - Ephemeral "Sub-guide ready!" notification auto-dismisses after 3 seconds when the persistent "Sub-Guides" banner is visible (prevents duplicate banners)
- **Class materials list page:** "Has Sub-Guides" badge shown on material cards that have associated sub-guides

#### Deferred to v2

- ~~SelectionTooltip redesign (add generate button alongside "Add to Notes")~~ → Replaced: "Generate Study Material" button replaced with "Ask Chat Bot" (#2554)
- Breadcrumb navigation for multi-level hierarchies (3+ levels deep)
- Full tree hierarchy endpoint (`/tree`)

#### Acceptance Criteria

- [x] Right-click on selected text in study guide shows context menu with generate options
- [x] Type selection modal opens with Study Guide / Quiz / Flashcards cards
- [x] Selected text displayed as context preview in modal
- [x] Can generate a child study guide from selected text
- [x] Child guide's `parent_guide_id` set to source guide, `relationship_type = 'sub_guide'`
- [x] Child guide page shows "Generated from: [Parent Title]" link
- [x] `GET /guides/{id}/children` returns sub-guides
- [x] Existing version chain behavior unchanged (`relationship_type = 'version'`)
- [x] DB migration adds `relationship_type` and `generation_context` columns
- [x] AI uses parent content as context (truncated intelligently)
- [x] AI credit check and decrement works
- [x] Backend tests cover generate-child and list-children endpoints
- [x] Frontend tests cover context menu, modal, and navigation
- [x] Build and lint pass
- [x] Sub-guide badge displayed on StudyGuidePage title when viewing a sub-guide
- [x] Root guide preferred over sub-guide when displaying study guide tab on CourseMaterialDetailPage
- [x] "Has Sub-Guides" badge shown on class materials list for materials with sub-guides
- [x] Duplicate sub-guide banners prevented (ephemeral notification auto-dismissed)
- [x] Sub-guide detection handles null `relationship_type` correctly

**GitHub:** #1594

**Status:** IMPLEMENTED (v1 navigation complete; v2 items deferred)

### 6.95 User Cloud Storage Destination (Phase 2) - PLANNED

Allow users to choose where their uploaded class materials are stored — either in ClassBridge's GCS (default) or in their personal cloud drive (Google Drive, OneDrive). When cloud drive storage is selected, uploaded files are saved to an auto-created `ClassBridge/{Course Name}/` folder structure in the user's drive. ClassBridge retains only a reference and downloads on-demand when needed for AI regeneration.

**Motivation:** Data ownership (users keep their files), GCS cost reduction (offload storage to user accounts), and file accessibility outside ClassBridge.

**PRD:** [docs/cloud-storage-integration-prd.md](../docs/cloud-storage-integration-prd.md)

**MVP Scope:** Google Drive + OneDrive. Dropbox deferred to Phase 2 enhancement.

#### Core Behaviors

1. **Storage destination preference**: Per-user setting in Settings/Integrations — "ClassBridge" (GCS, default) or a connected cloud provider. Upload wizard shows destination badge with per-upload override option.
2. **OAuth connections**: Google Drive (`drive.file` scope — only ClassBridge-created files), OneDrive (`Files.ReadWrite.AppFolder`). Encrypted token storage (AES-256-GCM). Auto-refresh.
3. **Cloud upload flow**: After text extraction, original file uploaded to user's cloud drive under `ClassBridge/{Course Name}/{filename}`. Folder structure auto-created. If cloud upload fails (quota, auth, network) → fallback to GCS + user notification.
4. **On-demand download**: When AI regeneration or original file download is triggered, backend fetches file from user's cloud drive. 30-second timeout. Clear error messages for deleted/moved/permission-changed files.
5. **Existing files stay**: Switching storage preference only affects new uploads. No automatic migration of existing GCS files (optional migration deferred to Phase 2 enhancement).
6. **All roles**: Available to Parent, Student, Teacher — not gated by subscription tier.

#### Data Model

- `cloud_storage_connections` — user OAuth tokens per provider (encrypted)
- `cloud_storage_folders` — cached folder IDs for ClassBridge folder structure in user's drive
- `source_files` new columns: `storage_destination`, `cloud_file_id`, `cloud_provider`, `cloud_folder_id`
- `users` new column: `file_storage_preference` (default: `'gcs'`)

#### API Endpoints

- `POST /api/cloud-storage/connect/{provider}` — initiate OAuth, store tokens
- `DELETE /api/cloud-storage/disconnect/{provider}` — revoke and delete
- `GET /api/cloud-storage/connections` — list user's connections
- `PATCH /api/users/me/storage-preference` — update preference
- `GET /api/source-files/{id}/download` — extended to support cloud-stored files

#### Frontend

- New page: `/settings/integrations` — cloud connections + storage preference
- Upload wizard: storage destination badge + per-upload override dropdown
- Course Material Detail: "Stored in: Google Drive / ClassBridge" indicator
- Mobile: expo-auth-session OAuth, adapted Settings screen

#### Out of Scope (MVP)

- Dropbox integration
- Migration of existing GCS files to cloud drive
- Two-way sync (cloud drive edits reflected in ClassBridge)
- Shared/team drives
- Cloud drive quota monitoring

#### Sub-tasks

- [ ] OAuth connection management — backend (#1865)
- [ ] Settings/Integrations page — frontend + backend (#1866)
- [ ] Upload to user's cloud drive — backend + frontend (#1867)
- [ ] On-demand file download from cloud drive (#1868)
- [ ] Cloud storage folder cache and auto-creation (#1869)
- [ ] Mobile cloud storage OAuth + Settings (#1870)
- [ ] Backend + frontend tests (#1871)

**GitHub Issues:** #1865-#1871

### 6.96 Cloud File Import for Study Materials (Phase 2) - PLANNED

Allow users to import files directly from their connected Google Drive or OneDrive into the Upload Material Wizard, eliminating the download-then-reupload friction. Files are browsed and selected inline via a tabbed file picker in Step 1 of the wizard, then processed through the same AI generation pipeline.

**Motivation:** Users organize schoolwork in cloud storage — downloading files just to re-upload them to ClassBridge is unnecessary friction, especially on mobile.

**Depends on:** §6.95 (OAuth connection infrastructure shared)

**MVP Scope:** Google Drive + OneDrive. Dropbox deferred.

#### Core Behaviors

1. **Tabbed file picker in Upload Wizard Step 1**: Tabs — "Upload" | "Google Drive" | "OneDrive". Cloud tabs show file browser for connected providers; unconnected providers show inline "Connect" CTA for discoverability.
2. **Full folder browsing + multi-select**: Navigate folder tree with breadcrumbs (compact: truncate middle segments at depth > 3). Files show name, size, modified date, type icon. Multi-select with checkboxes (up to 10 files). Unsupported/oversized files grayed out with tooltip.
3. **Search**: Filter files by name within current folder (client-side); deep search via provider API.
4. **Server-side download**: Backend downloads selected files from provider API (tokens never exposed to frontend). Files processed through existing `process_file()` pipeline — same text extraction, AI generation, material hierarchy.
5. **SourceFile tracking**: Records store `source_type = "google_drive"` or `"onedrive"` with `cloud_file_id` for analytics and re-download.
6. **Error handling**: Partial success — if some files fail to download, skip them, process remaining, show which succeeded/failed. 30-second timeout per file.
7. **No mixed sources**: User cannot mix local and cloud files in same upload session. Switching source tabs clears selection with confirmation.
8. **Mobile**: Source selector dropdown (< 480px) instead of tabs. Stack-based folder navigation (slide in/out) instead of breadcrumbs.

#### OAuth Scope Expansion

§6.95 connections use write-only scopes (`drive.file`, `Files.ReadWrite.AppFolder`). Cloud import needs additional read scopes:
- Google Drive: `drive.readonly` (read all user files for browsing)
- OneDrive: `Files.Read` (read all user files for browsing)
- Incremental consent: if user already connected for §6.95, prompt for additional scope on first browse attempt

#### API Endpoints

- `GET /api/cloud-storage/{provider}/files?folder_id=&search=` — list files/folders with metadata and breadcrumb
- `POST /api/cloud-storage/{provider}/import` — download selected files and process through upload pipeline

#### Frontend

- `UploadWizardStep1.tsx` — add source tabs
- New `CloudFileBrowser.tsx` — folder browser with breadcrumbs, file list, multi-select, search
- New `CloudConnectPrompt.tsx` — inline OAuth CTA for unconnected providers
- Mobile: dropdown source selector + stack navigation

#### Out of Scope (MVP)

- Dropbox (Phase 2 enhancement)
- Shared/team drives (personal drives only)
- File preview before import
- "Import all from folder" bulk action
- Recent/favorite files quick-access

#### Sub-tasks

- [ ] Cloud file browser UI component (#1872)
- [ ] Cloud file listing backend API (#1873)
- [ ] Server-side cloud file download & processing (#1874)
- [ ] Upload wizard cloud import UX — connect flow, loading, errors (#1875)
- [ ] OAuth scope expansion for read access (#1876)
- [ ] Backend + frontend tests (#1877)

**GitHub Issues:** #1872-#1877

### 6.101 Railway Deployment for clazzbridge.com (Infrastructure) - PLANNED

Set up Railway as a fully deployed mirror environment serving **clazzbridge.com**, auto-synced from the production repository (`theepangnani/emai-dev-03` on GCP Cloud Run → classbridge.ca).

**Motivation:** Provide a separate, independently deployed instance of ClassBridge at clazzbridge.com for demo, staging, and non-school-board use cases. Production remains on GCP Cloud Run (classbridge.ca) for FIPPA/MFIPPA compliance required by Ontario school boards. Railway provides a cost-effective ($5/mo) alternative deployment with its own database and infrastructure.

**Architecture:**
```
theepangnani/emai-dev-03 (production repo)
  ├── GCP Cloud Run → classbridge.ca (production)
  └── GitHub Actions sync ──▶ theepangnani/emai-railway (mirror repo)
                                  └── Railway auto-deploy → clazzbridge.com
```

**Previous context:** Railway was evaluated in #759 — account created (Hobby Plan $5/mo), PostgreSQL provisioned, app deployed and login verified at `emai-class-bridge-production.up.railway.app`. Migration was abandoned (#769-#774, #971 closed as stale) due to Canadian data residency concerns. This requirement re-scopes Railway as a parallel deployment at clazzbridge.com, not a replacement for GCP production.

#### Phase 1: Repository & Sync Infrastructure

- **Mirror repo**: Create `theepangnani/emai-railway` (private, not a GitHub fork). Contains production code plus Railway-specific config (`railway.toml`). Default branch: `main`.
- **Auto-sync workflow**: GitHub Actions in `emai-dev-03` triggers on push to `master`, force-pushes to `emai-railway:main`. Uses PAT or deploy key stored as `RAILWAY_REPO_TOKEN` secret. Manual `workflow_dispatch` trigger for re-sync.

#### Phase 2: Railway Service Setup

- **Railway project**: Reuse or recreate the existing Railway project. Connect `emai-railway` repo, deploy branch `main`, enable Check Suites.
- **PostgreSQL**: Railway PostgreSQL plugin — `DATABASE_URL` auto-injected via internal networking.
- **Deployment config** (`railway.toml`):
  ```toml
  [build]
  builder = "DOCKERFILE"
  dockerfilePath = "Dockerfile"

  [deploy]
  healthcheckPath = "/api/health"
  healthcheckTimeout = 300
  restartPolicyType = "ON_FAILURE"
  restartPolicyMaxRetries = 5
  ```
- **Environment variables**: `ENVIRONMENT=production`, `FRONTEND_URL=https://www.clazzbridge.com`, `CANONICAL_DOMAIN=www.clazzbridge.com`, `GOOGLE_REDIRECT_URI=https://www.clazzbridge.com/api/google/callback`, `USE_GCS=false`. New `SECRET_KEY` (never reuse production). Shared API keys (OpenAI, Anthropic, SendGrid).

#### Phase 3: Domain & OAuth

- **DNS**: Point `clazzbridge.com` and `www.clazzbridge.com` to Railway (CNAME/A records). Railway auto-provisions SSL via Let's Encrypt.
- **Google OAuth**: Add `https://clazzbridge.com`, `https://www.clazzbridge.com`, and Railway default URL to Google Cloud Console authorized origins and redirect URIs.

#### Phase 4: Storage & Data

- **File storage**: Set `USE_GCS=false` — app falls back to local storage. Attach Railway persistent volume for upload persistence across redeployments. S3-compatible storage (Cloudflare R2/Backblaze B2) deferred to later enhancement.
- **Database seed**: App `create_all()` auto-creates tables on first deploy. Startup migrations in `main.py` handle ALTER TABLE operations. Create admin user for testing. No production data copied.

#### Phase 5: Verification & Documentation

- Full smoke test of all core features (auth, OAuth, Google Classroom, AI tools, messaging, file uploads, parent/admin features).
- Document architecture, sync workflow, operational runbook, and differences from GCP production.

#### Key Differences from Production (GCP)

| Aspect | Production (GCP) | Railway |
|--------|-------------------|---------|
| URL | classbridge.ca | clazzbridge.com |
| Hosting | GCP Cloud Run | Railway |
| Database | Cloud SQL PostgreSQL | Railway PostgreSQL |
| File storage | GCS (`classbridge-files`) | Local + Railway volume |
| CI/CD | `deploy.yml` on master push | Auto-deploy on `emai-railway:main` push |
| Data residency | GCP Toronto (planned) | US (Railway) |
| Compliance | FIPPA/MFIPPA ready | Not for school board use |
| Cost | ~$20-30/mo | ~$5/mo |

#### Sub-tasks

- [ ] Create mirror repo `emai-railway` (#1879)
- [ ] GitHub Actions auto-sync workflow (#1880)
- [ ] Configure Railway project, service, PostgreSQL (#1881)
- [ ] Configure environment variables and secrets (#1882)
- [ ] Add `railway.toml` deployment config (#1883)
- [ ] Configure clazzbridge.com DNS → Railway (#1884)
- [ ] Add Railway URLs to Google OAuth console (#1885)
- [ ] Configure file storage for Railway (#1886)
- [ ] Seed Railway PostgreSQL (#1887)
- [ ] Smoke test all core features (#1888)
- [ ] Document Railway setup and architecture (#1889)

**GitHub Issues:** #1878 (epic), #1879-#1889

**Status:** PLANNED

---

### 6.102 Pre-Launch Survey System (#1890) - COMPLETE

Collect structured feedback from parents, students, and teachers via a public pre-launch survey. Role-specific question sets cover platform expectations, feature priorities, and willingness to pay. Admin dashboard provides analytics, filtering, and CSV export.

**GitHub:** #1890 (epic), #1891-#1895

**Sub-tasks:**
- [x] §6.102.1 Survey question design — Parent (10 questions), Student (8), Teacher (9) question sets (#1891)
- [x] §6.102.2 Backend: survey models, public API routes, admin analytics/export endpoints (#1892)
- [x] §6.102.3 Frontend: public survey page at `/survey` with role selection, progress bar, emoji likert scale, waitlist CTA (#1893)
- [x] §6.102.4 Frontend: admin survey results dashboard at `/admin/survey` with Recharts charts, filters, CSV export (#1894)
- [x] §6.102.5 Survey link on landing page and Help page CTA
- [x] §6.102.6 Admin sidebar "Survey Results" navigation link
- [x] §6.102.7 Fix: matrix likert buttons show emoji when selected (#1915)
- [x] §6.102.8 Fix: generate session_id at submit time to prevent 409 conflicts (#1920)
- [x] §6.102.9 Fix: persist survey progress in sessionStorage to survive browser refresh and mobile tab switch (#1927)
- [x] §6.102.10 Feat: admin in-app + email notifications on survey completion via SURVEY_COMPLETED notification type (#1928)
- [x] §6.102.11 Fix: bot protection — honeypot field + minimum completion time for survey (#1934)
- [x] §6.102.12 Feat: app-wide bot protection for all public forms — register, login, forgot-password, waitlist (#1935)

**Key Implementation Details:**
- **Models:** `SurveyResponse`, `SurveyAnswer` (`app/models/survey.py`)
- **Question definitions:** Static in code (`app/services/survey_questions.py`)
- **Public API:** `GET /api/survey/questions/{role}`, `POST /api/survey` (rate-limited 5/hour)
- **Admin API:** Analytics, responses list, response detail, CSV export (all admin-only, rate-limited)
- **Question types:** `single_select`, `multi_select`, `likert` (1-5 with emoji indicators), `likert_matrix`, `free_text`
- **PR:** #1895 (main implementation) + follow-up fixes

**Status:** COMPLETE

### 6.103 Help Knowledge Base Expansion & Chatbot Search Parity (#1779, #1778, #1908) - IMPLEMENTED

**Added:** 2026-03-18 | **Implemented:** 2026-03-19 | **PR:** #1918

Comprehensive audit revealed significant gaps in FAQ/help coverage and chatbot search routing. Multiple features exist in the app but have zero or minimal help documentation, making them undiscoverable via the chatbot.

**GitHub:** #1779 (FAQ expansion), #1778 (intent classifier keywords), #1908 (orphaned HelpArticle model)

**Sub-tasks:**
- [x] §6.103.1 Add 27 new FAQ entries to `faq.yaml` covering: Wallet, Survey, Activity History, Parent AI Tools, Parent Briefing Notes, Source Files, Briefing Tab, Calendar Import details, Data Export walkthrough, Study Hub guide
- [x] §6.103.2 Add missing feature entries to `features.yaml` for: Wallet, Survey management, Activity History, Parent Briefing Notes, Source Files
- [x] §6.103.3 Add missing page entries to `pages.yaml` for: Wallet, Survey, Activity History, Parent AI Tools, Parent Briefing Notes
- [x] §6.103.4 Add missing TOPIC_KEYWORDS to `intent_classifier.py`: wallet, survey, activity, export, theme, my kids, courses, tasks, briefing, source files, mind map
- [x] §6.103.5 Add suggestion chips on no-results in chatbot help route
- [x] §6.103.6 Seed `data/faq/seed.json` with 6 critical new entries to match faq.yaml coverage

**Key Files:**
- `app/data/help_knowledge/faq.yaml`
- `app/data/help_knowledge/features.yaml`
- `app/data/help_knowledge/pages.yaml`
- `app/services/intent_classifier.py`
- `app/api/routes/help.py`
- `data/faq/seed.json`

**Status:** IMPLEMENTED

### 6.104 Comprehensive Performance Optimization (#1954-#1967) - IMPLEMENTED

**Added:** 2026-03-20 | **Implemented:** 2026-03-20 | **PR:** #1968

Systematic performance audit identified and fixed 14 issues across the full application stack. Changes span backend N+1 query elimination, database indexing, connection pooling, frontend network resilience, and API batching.

**GitHub:** #1954-#1967 (individual issues), #1968 (integration PR)

**Sub-tasks:**
- [x] §6.104.1 Backend N+1 query elimination — eager loading (selectinload) added to tasks.py, assignments.py, courses.py, grades.py, course_contents.py, study.py, parent.py (#1954-#1959, #1967)
- [x] §6.104.2 Database indexes — 16 new indexes across 11 models (User.role, User.is_active, Teacher.user_id, CalendarFeed.user_id, StudentAssignment.status, etc.) + ALTER TABLE migrations (#1961)
- [x] §6.104.3 PostgreSQL connection pooling — pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800 (#1962)
- [x] §6.104.4 Token blacklist in-memory cache — LRU cache with 60s TTL eliminates per-request DB query (#1964)
- [x] §6.104.5 Parent dashboard pagination — tasks capped at 20, conversations at 10, with eager loading (#1965)
- [x] §6.104.6 Batch enrollment status API — new POST /api/courses/enrollment-status/batch replaces N individual calls (#1966)
- [x] §6.104.7 Frontend Axios timeout — 30s default + 120s for AI/upload operations across 6 API files (#1960)
- [x] §6.104.8 Visibility-aware polling — new usePageVisible hook pauses NotificationBell, MessagesPage, useAIUsage polling when tab hidden (#1963)
- [x] §6.104.9 Requirements update — Section 10.0 Performance Standards added to requirements/technical.md

**Key Files:**
- `app/api/routes/tasks.py`, `assignments.py`, `courses.py`, `grades.py`, `course_contents.py`, `study.py`, `parent.py`
- `app/models/` — 11 model files with new indexes
- `app/db/database.py` — connection pooling config
- `app/api/deps.py` — token blacklist cache
- `frontend/src/api/client.ts` — Axios timeout
- `frontend/src/hooks/usePageVisible.ts` — visibility hook
- `frontend/src/api/courses.ts` — batch enrollment API
- `main.py` — 16 CREATE INDEX migrations
- `requirements/technical.md` — Section 10.0

**Status:** IMPLEMENTED

---

### 6.105 Consolidated Study Material Navigation (#1969)

**Problem:** Study materials (quizzes, flashcards, study guides) have dedicated standalone pages at `/study/quiz/:id`, `/study/flashcards/:id`, `/study/guide/:id`, but the class materials page at `/course-materials/:id` already has tabs for all these types (`?tab=quiz|flashcards|guide|mindmap|videos|briefing`). Navigation is fragmented across 16+ files, with some going to standalone pages and others to class material tabs.

**Solution:** Consolidate all study material navigation to the class materials page tabs. When a study guide has a `course_content_id`, always navigate to `/course-materials/{course_content_id}?tab=<type>`. Dedicated pages remain accessible from class materials tabs via "Full Page" button, with back navigation returning to the class materials page.

**Requirements:**
- [x] §6.105.1 QuizPage and FlashcardsPage redirect to `/course-materials/{course_content_id}?tab=quiz|flashcards` when `course_content_id` exists (matching existing StudyGuidePage behavior from #1837)
- [x] §6.105.2 All navigation points across dashboards, components, and pages use `/course-materials/{course_content_id}?tab=<type>` when `course_content_id` is available
- [x] §6.105.3 Legacy fallback preserved for guides without `course_content_id` (standalone pages still work)
- [x] §6.105.4 Route definitions in App.tsx kept for `/study/quiz/:id`, `/study/flashcards/:id`, `/study/guide/:id` as redirect endpoints
- [x] §6.105.5 "Full Page" button in QuizTab, FlashcardsTab, StudyGuideTab opens dedicated page with `fromMaterial` state to bypass redirect
- [x] §6.105.6 Back navigation from dedicated pages returns to class materials page with correct tab activated

**Tab mapping:**
| guide_type | Tab parameter |
|------------|---------------|
| quiz | `?tab=quiz` |
| flashcards | `?tab=flashcards` |
| study_guide | `?tab=guide` |
| mind_map | `?tab=mindmap` |

**Status:** IMPLEMENTED

---

### 6.106 Study Guide Strategy Pattern — Document Type & Persona-Based Generation (Phase 2) - IMPLEMENTED

**Epic:** #1972 | **Source:** ClassBridge_StudyGuide_Requirements.docx v1.0 | **Review deadline:** April 14, 2026

When generating a study guide, the system determines what kind of document was uploaded and what the student is preparing for. This context shapes the AI output structure, tone, and focus strategy — the primary mechanism by which ClassBridge delivers differentiated value over generic AI platforms.

#### 6.106.1 Document Type Classification (#1973)

**Supported document types:**

| Document Type | Examples |
|---|---|
| Teacher Notes / Handout | Lecture slides, class notes, printed handouts, annotated worksheets |
| Course Syllabus | Unit overview, course outline, curriculum map, topic schedule |
| Past Exam / Test | Prior year exam, returned test with marks, completed quiz |
| Practice / Mock Exam | Sample questions, review sheet, prep quiz, unseen practice paper |
| Project Brief | Assignment rubric, project guidelines, inquiry task, performance task |
| Lab / Experiment | Lab procedure, experiment report template, data collection sheet |
| Textbook Excerpt | Chapter section, reference reading, supplementary material |
| Custom | Free-form label entered by the user |

**Data model:** `document_type` (VARCHAR(30)) and `study_goal` (VARCHAR(30)) + `study_goal_text` (VARCHAR(200)) on `course_contents`; `parent_summary` (TEXT) and `curriculum_codes` (TEXT/JSON) on `study_guides`.

**Sub-tasks:**
- [x] Data model, enums, schemas, and migration (#1973)
- [x] Prompt template map / strategy service (#1974)
- [x] Document type auto-detection service (#1975)
- [x] Parent summary dual output generation (#1976)
- [x] Ontario curriculum mapping service (#1977)
- [x] Cross-document intelligence service (#1978)
- [x] API route updates (#1979)
- [x] Frontend: document type selector UI (#1980)
- [x] Frontend: study goal selector UI (#1981)
- [x] Frontend: parent summary display (#1982)
- [x] Backend tests (#1983)
- [x] Frontend tests (#1984)

#### 6.106.2 Study Goal Selection (#1973)

**Preset dropdown options:** Upcoming Test/Quiz, Final Exam, Assignment/Project Submission, Lab Preparation/Report, General Review/Consolidation, In-class Discussion/Presentation, Parent Review (parent-facing summary mode)

**Free-form focus field:** Optional secondary input (max 200 chars) appended to AI system prompt as `focus_area` variable. Placeholder: *"Anything specific to focus on? (e.g., Chapter 4 only, quadratic equations, the water cycle)"*

#### 6.106.3 AI Output Structure by Document Type (#1974)

| Document Type | Study Guide Output Shape |
|---|---|
| Teacher Notes | Summary → Key Concepts → Likely Exam Topics → Practice Questions |
| Course Syllabus | Unit Breakdown → Study Priority Order → Weightings → Timeline Checklist |
| Past Exam | Gap Analysis → Topics Likely Missed → Targeted Drill Questions → Concept Explanations |
| Mock / Practice Exam | Answer Walkthrough → Concept Behind Each Question → Common Mistake Flags |
| Project Brief | Rubric Decoder → Step-by-Step Plan → Success Criteria Checklist → Timeline |
| Lab / Experiment | Pre-Lab Prep → Hypothesis Framing → Key Variables → Report Scaffold |
| Textbook Excerpt | Chapter Summary → Key Terms → Concept Map → Review Questions |

#### 6.106.4 Auto-Detection (#1975)

On upload, attempt classification using document metadata and first-pass AI inference (Claude Haiku, ~$0.001/call). Surface as pre-selected default for user to confirm or override. Falls back to "Custom" on low confidence.

#### 6.106.5 Parent Summary — Dual Output (#1976)

All study guide generations produce two outputs: `studentGuide` and `parentSummary`. Parent summary uses simplified language with 3 actionable support items. Example: *"Haashini is preparing for a Grade 8 science lab on cell division. Here are 3 ways you can support her tonight."*

#### 6.106.6 Curriculum Anchoring — Ontario Curriculum Mapping (#1977)

Post-generation step: secondary AI call maps key concepts to Ontario curriculum expectation codes (e.g., MTH1W-B2.3 — Strand B: Number). Requires student grade and subject context. **Priority 1 differentiator** — no generic AI platform can generate this without the student's grade and school context.

#### 6.106.7 Cross-Document Intelligence (#1978)

Detect relationships between uploaded documents over time using keyword frequency analysis. Example: *"You uploaded Chapter 5 notes last week and this practice test today. The test covers 3 topics you have not yet reviewed."* Requires persistent upload history per student. **Priority 2 differentiator.**

#### 6.106.8 Differentiators vs Generic AI Platforms

| Generic AI Knows | ClassBridge Knows |
|---|---|
| Document content only | Document + student's grade, school, teacher name, enrolled subjects |
| No curriculum awareness | Ontario curriculum expectations mapped per grade and subject |
| No history | Cross-document intelligence across all uploads this term |
| Single output format | Output shaped separately for Student, Parent, and Teacher views |
| No follow-through | Linked to Smart Daily Briefing and Parent-Child Study Link features |

**Key files:**
- `app/services/study_guide_strategy.py` — Prompt template map + strategy service
- `app/services/document_classifier.py` — Auto-detection service
- `app/services/parent_summary.py` — Parent summary generation
- `app/services/curriculum_mapping.py` — Ontario curriculum annotation
- `app/services/cross_document.py` — Cross-document intelligence
- `frontend/src/components/DocumentTypeSelector.tsx` — Document type chip selector
- `frontend/src/components/StudyGoalSelector.tsx` — Study goal dropdown + focus field
- `frontend/src/components/ParentSummaryCard.tsx` — Parent summary display card

### 6.107 Study Streak & XP Point System (Phase 2) — September 2026 Retention Bundle

Gamification system that rewards study consistency (not performance) through XP points, study streaks, achievement badges, and level progression. Primary daily-return mechanism for students.

**GitHub Epic:** #1997

**Source:** StudyGuide Requirements v3 — Section 9

**Design Principles:**
- Effort over outcomes: XP awarded for actions, never for correctness or grades
- Consistency over intensity: daily engagement earns more than a single long session
- Non-monetary: XP separate from wallet/subscription system. Cosmetic rewards only
- Privacy by default: XP totals never visible to teachers. Leaderboards opt-in only
- Age-appropriate: no competitive pressure, no public shaming, no punitive loss

**XP Actions:**

| Action | XP | Daily Cap |
|--------|-----|-----------|
| Upload a document | 10 | 30 |
| Upload from LMS (GC/Brightspace) | 15 | 30 |
| Generate a study guide | 20 | 40 |
| Generate flashcard deck | 15 | 15 |
| Complete flashcard review | 10 | 30 |
| Ask a question in AI Chat | 5 | 20 |
| Complete Study With Me session | 15 | 30 |
| Mark flashcard as 'Got it' | 1 | 20 |
| Daily login streak bonus | 5 | 5 |
| End-of-week review | 25 | 25 |
| Complete quiz (any score) | 15 | 30 |
| Score higher than previous attempt | 10 | 10 |

**Streak System:**
- Streak day = at least one action worth 10+ XP on a calendar day (student's local timezone)
- Multipliers: 1.0× (1-6d), 1.25× (7-13d), 1.5× (14-29d), 1.75× (30-59d), 2.0× (60+d)
- 1 freeze token per calendar month (auto-applied morning after missed day)
- Streak recovery: earn 2× daily average within 24 hours (max 1 per 30 days)
- School calendar aware: streaks don't break on holidays; summer pause Jul 1 – Aug 31

**Levels:**

| Level | Title | XP Required | Unlock |
|-------|-------|-------------|--------|
| 1 | Curious Learner | 0 | Default |
| 2 | Note Taker | 200 | Custom profile badge |
| 3 | Study Starter | 500 | Flashcard theme skin |
| 4 | Focused Scholar | 1,000 | Streak Freeze bonus token |
| 5 | Deep Diver | 2,000 | Priority AI guide generation |
| 6 | Guide Master | 3,500 | Custom study guide cover |
| 7 | Exam Champion | 5,500 | End-of-term certificate PDF |
| 8 | ClassBridge Elite | 8,000 | Profile gold border + badge |

**Achievement Badges:** 14 badges (First Upload, First Study Guide, 7-Day Streak, 30-Day Streak, Flashcard Fanatic, LMS Linker, Exam Ready, Quiz Improver, Night Owl, Early Bird, All-Rounder, Parent Partnership, Sub-Guide Explorer, End-of-Term Scholar)

**Brownie Points:** Parent (50 XP/week per child) and Teacher (30 XP/week per student) manual awards with audit log.

**Data Model:**
- `xp_ledger` — append-only event log
- `xp_summary` — materialized view (total_xp, level, streak, freeze_tokens)
- `badges` — student badge awards
- `streak_log` — daily streak tracking with holiday flag
- `holiday_dates` — school board calendar for streak awareness

**Anti-Gaming:** Time-on-task validation, 60-second dedup window, rapid upload flags, quiz repeat caps.

**XP Summary API Contract (`GET /api/xp/summary`):**

| Field | Type | Description |
|-------|------|-------------|
| user_id | int | Student user ID |
| total_xp | int | Lifetime XP earned |
| level | int | Current level (1-8) |
| level_title | string | Display title for current level |
| streak_days | int | Current consecutive streak days |
| xp_in_level | int | XP earned within current level band |
| xp_for_next_level | int | Total XP width of current level band |
| today_xp | int | XP earned today |
| today_max_xp | int | Daily XP cap |
| weekly_xp | int | XP earned in last 7 days |
| recent_badges | BadgeResponse[] | Last 3 earned badges (id, name, description, icon, earned_at) |

**Sub-tasks:**
- [x] XP data model (#2000)
- [x] XP earning service (#2001)
- [x] Streak engine (#2002)
- [x] XP levels & titles (#2003)
- [x] Achievement badges (#2004)
- [x] Brownie points (#2005)
- [x] XP dashboard UI (#2006)
- [x] XP history log (#2007)
- [x] Parent XP visibility (#2008)
- [x] Anti-gaming rules (#2009)
- [x] source_type column (#2010)
- [x] Holiday dates table (#2024)

### 6.108 Assessment Countdown Widget (Phase 2) — September 2026 Retention Bundle

Detect upcoming assessments from uploaded documents and display countdown widgets on dashboards. Creates urgency and daily return triggers.

**GitHub Epic:** #1998

**Source:** StudyGuide Requirements v3 — Section 8, Feature #5

**Requirements:**
- Parse uploaded documents for date references and exam keywords
- Use document_type detection (past_exam, mock_exam) and Google Classroom due dates as sources
- Display countdown cards: "Math quiz in 3 days — last study session was 5 days ago. Tap to review."
- Tapping countdown opens the linked study guide directly
- Show on both student and parent dashboards

**Data Model:**

| Table: detected_events | | |
|---|---|---|
| id | Integer PK | |
| student_id | FK → users.id | |
| course_id | FK → courses.id (nullable) | |
| event_type | String(30) | test, exam, quiz, assignment, lab |
| event_title | String(200) | |
| event_date | Date | |
| source | String(30) | document_parse, google_classroom |

**Sub-tasks:**
- [x] Assessment date detection (#2011)
- [x] detected_events table and API (#2012)
- [x] Countdown widget UI (#2013)

### 6.109 Multilingual Parent Summaries (Phase 2) — September 2026 Retention Bundle

Auto-translate parent-facing study guide summaries and digest emails into the parent's preferred language. Key differentiator for GTA market (YRDSB, TDSB procurement).

**GitHub Epic:** #1999

**Source:** StudyGuide Requirements v3 — Section 8, Feature #7

**Supported Languages (Launch):** English, French, Tamil, Mandarin (Simplified), Punjabi, Urdu

**Requirements:**
- Language preference set once in parent profile (Account Settings page, accessible from dashboard More dropdown); applied to all summaries and digest emails
- Translation via Claude API post-generation pass; cached per guide per language
- On-demand generation (not pre-emptive) to control costs
- Consider gating behind premium tier

**Sub-tasks:**
- [x] Language preference in user profile (#2014)
- [x] Multilingual translation via Claude API (#2015)
- [x] Multilingual digest email support (#2016)

### 6.110 Personal Study History Timeline (Phase 2)

Visual timeline showing every document uploaded, guide generated, and topic studied per semester. Students see their own effort over time.

**GitHub Issue:** #2017

**Source:** StudyGuide Requirements v3 — Section 8, Feature #8

**Requirements:**
- Filterable by subject, document type, and date range
- Each timeline entry links to the original guide
- Milestone markers at streak achievements and exam events
- Accessible from student profile/dashboard

**Sub-tasks:**
- [x] Backend: activity timeline API endpoint
- [x] Frontend: vertical timeline component with filters

### 6.111 End-of-Term Report Card (Phase 2) - IMPLEMENTED

Auto-generated semester summary for student and parent: subjects studied, documents uploaded, guides created, streaks, most-reviewed topics.

**GitHub Issue:** #2018

**Source:** StudyGuide Requirements v3 — Section 8, Feature #10

**Requirements:**
- Delivered as shareable PDF and in-app card
- Includes next-term CTA: "Ready to start strong in Semester 2?"
- Generated at end of each semester
- Data from XP ledger, upload history, study guide counts

### 6.112 "Is My Child On Track?" Signal (Phase 2) - IMPLEMENTED

Effort-based signal comparing study activity vs upcoming assessments. Displayed on parent dashboard.

**GitHub Issue:** #2020

**Source:** StudyGuide Requirements v3 — Section 8, Feature #12

**Signal Conditions:**

| Signal | Condition |
|--------|-----------|
| Green | Studying consistently relative to detected upcoming assessments |
| Yellow | Last study session 4+ days ago with assessment within 7 days |
| Red | No study activity in 7+ days with assessment within 5 days |

**Important:** Signal is always about effort, never performance. This avoids grade anxiety and is appropriate for school board procurement conversations.

**Dependencies:** detected_events (#2012), streak_log (#2002)

### 6.113 Study With Me (Pomodoro) Sessions (Phase 2) - IMPLEMENTED

25-minute timed study session tied to a specific subject. AI recap at end. Session completion awards XP.

**GitHub Issue:** #2021

**Source:** StudyGuide Requirements v3 — Section 8, Feature #13

**Requirements:**
- Timer UI with subject selection
- Min. 20 continuous minutes for XP credit (15 XP, daily cap 30 XP)
- AI recap: "You studied quadratic equations for 25 minutes. Here are 3 things to remember."
- Weekly session total visible on parent dashboard

### 6.114 Study Guide Contextual Q&A (Phase 2) - IMPLEMENTED

Context-aware chatbot Q&A when users are viewing a study guide. The existing Help Chatbot automatically switches to "study tutor" mode, using the study guide content as context to answer questions. Users can save responses as new study guides or course materials.

**GitHub Epic:** #2056
**Sub-issues:** #2057 (backend streaming), #2058 (save endpoints), #2059 (wallet debit), #2060 (frontend chatbot), #2061 (page integration), #2062 (tests), #2063 (docs)
**Chatbot Redesign:** #2548 (PR), #2538 (header/panel), #2539 (suggestion chips), #2540 (input/error), #2561 (diagram citation)
**Ask Chat Bot Flow:** #2554 (PR #2574) — replaced "Generate Study Material" with chatbot injection

**Architecture:** Same chatbot UI, smart routing. Frontend sends `study_guide_id` in the existing `/help/chat/stream` request. Backend detects the ID and routes to study Q&A path instead of help RAG pipeline.

**Cost Model:**

| Aspect | Decision |
|--------|----------|
| AI Model | Haiku (`claude-haiku-4-5-20251001`) — fast, cheap |
| Credit cost | 0.25 credits per question |
| Rate limit | 20 questions/hour (separate from help chatbot's 30/hr) |
| Context budget | ~8000 tokens input (6000 guide + 2000 source doc) |
| Est. cost/question | ~$0.001–$0.003 |

**Study Q&A System Prompt:**
- Role: Study tutor for ClassBridge
- Context: Full study guide content (truncated to 24,000 chars) + source document excerpt (8,000 chars) if available
- Rules: Answer ONLY based on provided material; use markdown + LaTeX for math; 2–4 paragraphs max; provide answers when generating practice questions

**Frontend Behavior:**
- When on study guide page (full page or Guide tab): chatbot header changes to "Ask about: {guide title}"
- Suggestion chips switch to study-specific: "Summarize key concepts", "Explain the main ideas", "Give me practice questions", "What are the important terms?", "Quiz me on this topic"
- Per-guide conversation history (separate sessionStorage key per guide ID)
- Credit display in header: "0.25 credits/question"
- Reverts to normal help mode when navigating away from study guide

**Text Selection → Chatbot Injection (#2554):**
- SelectionTooltip "Generate Study Material" button replaced with "Ask Chat Bot"
- TextSelectionContextMenu "Generate Study Guide" / "Generate Sample Test" replaced with single "Ask Chat Bot"
- Both entry points open the chatbot, inject the selected text as a question, and auto-submit
- When no text is selected, chatbot opens with BAU suggestion chips (no change)
- "Generate study guide" added as a Study Q&A suggestion chip action row
- "Add to Notes" button unchanged on both tooltip and context menu

**Save Actions on Assistant Messages (study_qa mode only):**
1. **Save as Study Guide** — Creates sub-guide (`relationship_type="sub_guide"`, `parent_guide_id` = current guide). No AI credits consumed.
2. **Save as Class Material** — Creates `CourseContent` with `text_content` in same course. Only available when guide has `course_id`. No AI credits consumed.

**Chatbot UI Redesign (PR #2548, #2561):**
- Redesigned header with guide title, session ID display, and credit cost indicator
- Suggestion chips replaced with vertical action rows (inline SVG icons)
- Input bar redesigned with cleaner error states and focus ring CSS variables
- Medium-viewport breakpoint (400px chatbot panel) for responsive layout
- Keyboard focus-visible styles on all interactive elements (action rows, close/clear buttons)
- Source image descriptions passed to chatbot context for diagram citation (#2532)
- Access check widened to match course material trust circle (#2535)
- Dead code cleanup: removed GenerateSubGuideModal after Ask Chat Bot refactor (#2564, #2568)
- Race condition fix: pendingQuestion useEffect chain and FABContext re-render optimization (#2567, #2569, #2578)

### 6.115 Streaming Study Guide Generation — ChatGPT-like UX (Phase 1) - COMPLETE

Real-time streaming of study guide generation using Server-Sent Events (SSE), replacing the synchronous spinner-and-wait UX with token-by-token content rendering.

**GitHub Epic:** #2120
**Sub-issues:** #2121 (AI streaming service), #2122 (SSE endpoint), #2123 (frontend hook), #2124 (StreamingMarkdown component), #2125 (wiring), #2126 (tests)
**Fix:** #2210 (dashboard upload navigation to streaming view)

**Triggers:**
- [x] Initial generation — user uploads class material and clicks "Generate Study Guide"
- [x] Regeneration — user clicks "Regenerate" on an existing guide
- [x] Sub-guide generation — user selects text and generates a child guide
- [x] Dashboard upload — user uploads from dashboard, navigated to detail page with auto-generation

**Technical Architecture:**
- **Protocol:** Server-Sent Events (SSE) via `POST /api/study/generate-stream`
- **Backend:** `generate_study_guide_stream()` async generator in `ai_service.py`, uses Anthropic `client.messages.stream()`
- **Frontend:** `useStudyGuideStream` hook with `fetch()` + `ReadableStream`, 80ms render throttling
- **Component:** `StreamingMarkdown` — progressive markdown renderer with blinking cursor, auto-scroll, "Generating..." badge

**SSE Event Protocol:**

| Event | Data | When |
|-------|------|------|
| `start` | `{guide_id}` | Stream begins, DB record created |
| `chunk` | `{text}` | Each content chunk from AI |
| `done` | `StudyGuideResponse` | Complete, saved to DB, credits debited |
| `error` | `{message}` | On failure |

**Performance Mitigations:**
- [x] Render throttling: 80ms flush interval (~50 re-renders vs ~4000 per-token)
- [x] LaTeX disabled during streaming (prevents parse errors from incomplete blocks), re-enabled on completion
- [x] DB session released before streaming, reopened after completion (prevents connection pool exhaustion)

**Cost Impact:** $0 additional — Anthropic streaming and non-streaming priced identically. No new frontend dependencies.

**Requirements:**
- [x] User navigated to Study Guide tab immediately on generate
- [x] Content streams token-by-token with blinking cursor indicator
- [x] Markdown renders progressively (headings, lists, bold appear as they stream)
- [x] On completion, guide saved to DB and AI usage debited
- [x] Regeneration and sub-guide generation use streaming
- [x] Dashboard upload navigates to detail page with auto-streaming
- [x] Quiz, flashcards, mind map remain synchronous (streaming not applicable to structured JSON)

**API Changes:**

| Endpoint | Change |
|----------|--------|
| `POST /api/help/chat/stream` | Add `study_guide_id` to request; branch to study Q&A when present |
| `POST /api/help/chat` | Same branch for non-streaming |
| `POST /api/study/guides/{id}/qa/save-as-guide` | **NEW** — Save response as sub-guide |
| `POST /api/study/guides/{id}/qa/save-as-material` | **NEW** — Save response as course material |

**Schema Changes:**
- `HelpChatRequest`: add `study_guide_id: int | None`
- `HelpChatResponse`: add `mode: str` ("help" | "study_qa"), `credits_used: float | None`, `input_tokens`, `output_tokens`, `estimated_cost_usd`
- New: `SaveQAAsGuideRequest`, `SaveQAAsMaterialRequest`

**Backend Service:** `app/services/study_qa_service.py`
- `StudyQAService` class with Haiku model, 20/hr rate limiting, context truncation
- `stream_answer()` async generator for SSE
- `_check_rate_limit()` per-user enforcement

**Access Control:** Guide owner, users guide is shared with, or parent of guide owner

**Key Files:**
- Backend: `app/services/study_qa_service.py`, `app/services/ai_usage.py`, `app/schemas/help.py`, `app/api/routes/help.py`, `app/api/routes/study.py`
- Frontend: `useHelpChat.ts`, `SpeedDialFAB.tsx`, `ChatMessage.tsx`, `SuggestionChips.tsx`, `FABContext.tsx`, `StudyGuidePage.tsx`, `CourseMaterialDetailPage.tsx`

