# Product Requirements Document: User Cloud Storage Destination

**Version**: 2.0
**Date**: 2026-03-17
**Author**: Sarah (Product Owner)
**Quality Score**: 92/100
**Requirements Section**: §6.95

---

## Executive Summary

ClassBridge currently stores all uploaded class materials in Google Cloud Storage (GCS) under `gs://classbridge-files`. Users have no control over where their original files are stored — they exist only within ClassBridge's infrastructure. This creates three concerns: (1) users don't own or control their uploaded documents, (2) GCS storage costs scale linearly with user growth, and (3) files are inaccessible outside of ClassBridge.

This feature allows users to **choose where their uploaded class materials are stored** — either in ClassBridge's GCS (default) or in their own personal cloud drive (Google Drive or OneDrive). When a user selects cloud drive storage, uploaded files are saved to an auto-created `ClassBridge/` folder structure in their drive, organized by course. ClassBridge retains only a reference (cloud file ID + provider) and downloads the file on-demand when needed for AI generation (study guides, quizzes, flashcards).

This gives users data ownership, reduces platform storage costs, and makes class materials accessible from anywhere — inside or outside ClassBridge.

---

## Problem Statement

**Current Situation**: All uploaded materials are stored exclusively in ClassBridge's GCS bucket. Users cannot access their original files outside of ClassBridge. If a user leaves the platform, their files are gone (unless they exported via PIPEDA data export). GCS costs grow with every user upload, and there's no way to offset this to users who already pay for their own cloud storage.

**Proposed Solution**: Add a per-user storage destination setting (GCS or personal cloud drive). When cloud drive is selected, uploaded files are saved to the user's Google Drive or OneDrive in an organized `ClassBridge/{Course Name}/` folder structure. ClassBridge stores a reference and downloads on-demand for processing. Fallback to GCS if cloud upload fails.

**Business Impact**:
- **Data ownership**: Users retain control of their original documents in their own cloud accounts
- **Cost reduction**: Offload file storage from GCS to users' existing cloud storage (most have free tiers: 15GB Google Drive, 5GB OneDrive)
- **Accessibility**: Users can access, share, or edit their class materials from Google Drive/OneDrive outside of ClassBridge
- **Platform stickiness**: Deep integration with users' cloud ecosystem increases switching cost

---

## Success Metrics

**Primary KPIs:**
- **Cloud storage adoption rate**: Target 25% of active users switch to cloud drive storage within 3 months
- **GCS storage cost reduction**: Target 15-20% reduction in GCS storage costs within 6 months
- **User retention**: Users with cloud drive connected show higher 30-day retention vs GCS-only users

**Secondary KPIs:**
- **Fallback rate**: <5% of cloud-destined uploads fall back to GCS (indicates healthy OAuth connections)
- **On-demand download latency**: <3 seconds average for fetching a file from user's cloud drive for AI generation

**Validation**: Track via `storage_destination` field on `source_files` records. GCS cost monitoring via Cloud Billing. Retention cohort analysis in admin dashboard.

---

## User Personas

### Primary: Parent (Maria)
- **Role**: Parent managing 2 children's education
- **Goals**: Keep her children's school documents organized in her personal Google Drive alongside other family files
- **Pain Points**: Uploads worksheets to ClassBridge but can't access them from Google Drive; has to maintain two copies
- **Technical Level**: Intermediate

### Secondary: Student (Alex)
- **Role**: High school student with school-provided Microsoft 365 (OneDrive)
- **Goals**: Keep all study materials in OneDrive where they're accessible from school Chromebooks and personal devices
- **Pain Points**: Uploads class notes to ClassBridge but they're not in OneDrive where the rest of schoolwork lives
- **Technical Level**: Advanced

### Tertiary: Teacher (Ms. Chen)
- **Role**: Private tutor creating course materials for multiple students
- **Goals**: Have teaching resources backed up in her own Google Drive, not just on a third-party platform
- **Pain Points**: Concerned about data portability; if she stops using ClassBridge, her uploaded materials are locked in
- **Technical Level**: Intermediate

---

## User Stories & Acceptance Criteria

### Story 1: Connect Cloud Storage for File Saving

**As a** ClassBridge user (any role)
**I want to** connect my Google Drive or OneDrive as a storage destination
**So that** my uploaded class materials are saved to my own cloud account

**Acceptance Criteria:**
- [ ] Settings/Integrations page shows supported cloud storage providers with "Connect" buttons
- [ ] Google Drive: Users authenticated via Google OAuth can connect with expanded `drive.file` scope (read/write to ClassBridge-created files only)
- [ ] Google Drive: Users authenticated via email/password see a "Connect Google Drive" button that triggers OAuth flow
- [ ] OneDrive: "Connect OneDrive" button triggers Microsoft OAuth flow with `Files.ReadWrite.AppFolder` scope
- [ ] OAuth refresh tokens stored encrypted (AES-256-GCM) in `cloud_storage_connections` table
- [ ] Access tokens auto-refresh transparently; if refresh fails, mark connection as "expired" and notify user
- [ ] Users can disconnect/revoke access from Settings page (with ConfirmModal)
- [ ] Connection status visible: connected (account email + date), disconnected, or expired

### Story 2: Set Storage Destination Preference

**As a** user with a connected cloud storage account
**I want to** choose where my uploaded files are stored
**So that** I control whether files go to ClassBridge or my personal cloud drive

**Acceptance Criteria:**
- [ ] Settings page shows "File Storage" preference: "ClassBridge (default)" or connected provider name
- [ ] Default is "ClassBridge" (GCS) for all users
- [ ] Changing the setting applies to all future uploads only — existing files stay where they are
- [ ] Upload Wizard shows current storage destination with option to override for that upload
- [ ] Storage destination indicator: small badge/label in upload wizard showing "Saving to: Google Drive" or "Saving to: ClassBridge"

### Story 3: Upload Files to User's Cloud Drive

**As a** user with cloud drive storage enabled
**I want** my uploaded class materials to be saved in my cloud drive
**So that** I can access them from Google Drive/OneDrive outside of ClassBridge

**Acceptance Criteria:**
- [ ] On upload, file is saved to user's cloud drive under `ClassBridge/{Course Name}/{filename}`
- [ ] If course has no name or is "My Materials", folder is `ClassBridge/My Materials/{filename}`
- [ ] `ClassBridge/` root folder auto-created on first cloud upload if it doesn't exist
- [ ] Course subfolders auto-created as needed
- [ ] SourceFile record stores: `storage_destination` = "google_drive" or "onedrive", `cloud_file_id`, `cloud_folder_id`
- [ ] Text extraction still happens at upload time (file is downloaded temporarily for OCR, then discarded from server)
- [ ] If cloud upload fails (quota exceeded, auth expired, network error): file saved to GCS instead, user sees notification explaining fallback
- [ ] Multi-file uploads: each file saved individually to cloud drive, same folder structure

### Story 4: On-Demand File Access for AI Generation

**As a** user who stored materials in their cloud drive
**I want** ClassBridge to fetch my files when I regenerate study materials
**So that** AI generation works the same regardless of where files are stored

**Acceptance Criteria:**
- [ ] When AI regeneration or re-processing is triggered, backend downloads file from user's cloud drive using stored `cloud_file_id`
- [ ] Download timeout: 30 seconds per file
- [ ] If download fails (file deleted, moved, or permissions changed): show clear error message with guidance
- [ ] Downloaded file is processed and immediately discarded (not persisted on server)
- [ ] Original text extraction (stored in `CourseContent.text_content`) is used for most operations — on-demand download only needed for regeneration with new parameters

### Story 5: View and Download Original Files

**As a** user viewing a course material
**I want to** download the original file regardless of where it's stored
**So that** I can access my source documents

**Acceptance Criteria:**
- [ ] "Download Original" button on Course Material Detail page works for both GCS and cloud-drive-stored files
- [ ] For cloud drive files: backend fetches from provider API and streams to user (or redirects to provider's download URL)
- [ ] For GCS files: existing download flow unchanged
- [ ] File source indicator on Course Material Detail: "Stored in: Google Drive" / "Stored in: ClassBridge"

---

## Functional Requirements

### Core Features

**Feature 1: OAuth Connection Management**
- Description: Connect/disconnect cloud storage accounts for file saving
- OAuth scopes:
  - Google Drive: `drive.file` (read/write only files created by ClassBridge app — more restrictive than `drive.readonly`, no access to user's other files)
  - OneDrive: `Files.ReadWrite.AppFolder` (read/write to app-specific folder only)
- Backend: `cloud_storage_connections` table with encrypted tokens
- Token encryption: AES-256-GCM with `CLOUD_STORAGE_ENCRYPTION_KEY` env var
- Auto-refresh on API calls; mark "expired" if refresh fails
- PIPEDA: connections included in data export and deleted on account deletion

**Feature 2: Storage Destination Setting**
- Description: Per-user preference for where uploaded files are stored
- New field: `users.file_storage_preference` — `"gcs"` (default) or `"google_drive"` or `"onedrive"`
- Settings UI: Radio/select in Settings/Integrations page
- Upload Wizard: Shows current destination with per-upload override dropdown
- Validation: Cannot select a provider that isn't connected; if provider gets disconnected, revert preference to "gcs"

**Feature 3: Cloud Drive File Upload**
- Description: Save uploaded files to user's cloud drive instead of GCS
- Flow:
  1. User uploads file via existing wizard
  2. Backend extracts text/images (normal OCR pipeline)
  3. Backend uploads original file to user's cloud drive via provider API
  4. Backend stores cloud file reference (file ID, folder ID, provider) on `SourceFile` record
  5. Original file discarded from server memory
- Folder structure: `ClassBridge/{Course Name}/{original_filename}`
- Folder creation: Auto-create `ClassBridge/` and course subfolders via API if they don't exist; cache folder IDs in `cloud_storage_folders` table to avoid repeated lookups
- Fallback: If cloud upload fails → save to GCS → create notification for user
- Concurrency: Cloud upload runs in parallel with AI generation (don't block AI pipeline)

**Feature 4: On-Demand File Download**
- Description: Fetch files from user's cloud drive when needed
- Trigger: Regeneration, re-download original, re-processing
- Backend: `GET /api/source-files/{id}/download` checks `storage_destination` and fetches from appropriate source
- Timeout: 30 seconds per file
- Error states: File deleted (404), permissions changed (403), token expired (401) — each with specific user-facing message
- Caching: No server-side caching of downloaded files (stream-through only)

**Feature 5: Settings/Integrations Page**
- Description: Unified page for cloud connections and storage preference
- Route: `/settings/integrations` (new page, linked from sidebar under existing Settings)
- Sections:
  1. "Cloud Storage" — connect/disconnect providers with status
  2. "File Storage Preference" — choose default storage destination
- Admin view: Admin dashboard shows aggregate stats (% users on GCS vs cloud drive)

### Out of Scope (MVP)
- Dropbox integration (Phase 2)
- Migrating existing GCS files to cloud drive (existing files stay in GCS)
- Two-way sync (editing files in cloud drive doesn't update ClassBridge)
- Shared/team drives (personal drives only)
- Cloud drive storage quota monitoring
- Folder customization (user can't change the `ClassBridge/` folder structure)

---

## Technical Constraints

### Performance
- Cloud file upload (save to drive): <5 seconds for files under 20MB
- On-demand download from cloud: <3 seconds average, 30-second timeout
- Folder listing/creation: <2 seconds (cached folder IDs after first lookup)
- Upload pipeline: Cloud save runs in parallel with text extraction — no added latency to user-facing flow

### Security
- OAuth tokens encrypted at rest (AES-256-GCM) with rotatable key
- Google Drive: `drive.file` scope — ClassBridge can only access files IT created, not the user's other files
- OneDrive: `Files.ReadWrite.AppFolder` — restricted to ClassBridge app folder
- Backend-only cloud API calls — no provider tokens exposed to frontend
- PIPEDA compliance: Cloud connections included in data export; deleted on account deletion
- File content never persisted on server when using cloud storage (stream-through processing)

### Integration
- **Google Drive API v3**: `files.create`, `files.get`, `files.list` (within app folder)
- **Microsoft Graph API**: DriveItem create, get, list (within app folder)
- **Existing upload pipeline**: `process_file()`, `create_material_hierarchy()` — unchanged; cloud save happens after text extraction
- **Existing GCS pipeline**: Unchanged; continues to work for users on default "ClassBridge" storage
- **Existing Google OAuth**: Incrementally add `drive.file` scope for Google-authenticated users

### Technology Stack
- Backend: FastAPI endpoints, `google-api-python-client` for Drive, `msal` + `httpx` for Microsoft Graph
- Frontend: Settings page components, upload wizard storage indicator
- Database: New `cloud_storage_connections` table, new columns on `source_files`, new `cloud_storage_folders` cache table
- Mobile: React Native (Expo) — `expo-auth-session` for OAuth, same Settings/upload UI adapted

---

## MVP Scope & Phasing

### Phase 1: MVP — Google Drive + OneDrive Storage Destination
- OAuth connection management (connect/disconnect per provider)
- Settings/Integrations page with storage preference
- Upload wizard storage destination indicator + per-upload override
- Auto-created `ClassBridge/{Course}/` folder structure in user's drive
- Fallback to GCS on cloud upload failure + user notification
- On-demand file download for regeneration and original file access
- Web + mobile (Expo)
- Admin stats: storage destination breakdown

**MVP Definition**: A user can connect Google Drive or OneDrive, set it as their storage destination, and have all future uploads saved to their personal cloud drive with organized folder structure — while ClassBridge retains the ability to process files for AI generation on-demand.

### Phase 2: Enhancements
- Dropbox integration (third provider)
- Optional migration of existing GCS files to connected cloud drive
- Cloud drive storage quota indicator in Settings
- Folder customization (let user choose base folder name)
- "Open in Google Drive / OneDrive" button on Course Material Detail page

### Future Considerations
- Two-way sync (changes in cloud drive reflected in ClassBridge)
- Auto-import: Watch ClassBridge folder for new files added via cloud drive
- Shared/team drive support
- Cloud drive analytics in admin dashboard

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Google OAuth `drive.file` scope verification | Medium | High | `drive.file` is a restricted scope — may need verification. Start early; reuse existing OAuth app. |
| Microsoft Azure AD app registration | Medium | Medium | Register early; test with personal + school Microsoft accounts. |
| User deletes/moves file from cloud drive | High | Medium | On-demand download fails gracefully with clear error. Original text extraction is already stored in DB — most operations don't need the file. |
| Cloud drive quota exceeded | Medium | Medium | Fallback to GCS + notification. User still gets full functionality. |
| On-demand download latency | Low | Low | Most operations use stored `text_content`. On-demand only needed for regeneration with new focus prompt. |
| Token expiry during upload | Low | Medium | Auto-refresh before upload; fallback to GCS if refresh fails. |

---

## Dependencies & Blockers

**Dependencies:**
- Google Cloud Console: Add `drive.file` scope to existing OAuth consent screen; may trigger re-verification
- Microsoft Azure AD: Register new OAuth application for OneDrive
- `CLOUD_STORAGE_ENCRYPTION_KEY` env var provisioned in Cloud Run
- Frontend: Settings page infrastructure (may be new, or extend existing profile page)

**Known Blockers:**
- Google verification for `drive.file` scope may take 2-4 weeks — start process immediately
- Mobile OAuth requires `expo-auth-session` setup for both providers

---

## Appendix

### Glossary
- **Storage Destination**: Where a user's uploaded original files are persisted — either GCS (ClassBridge-managed) or a personal cloud drive
- **Cloud File ID**: The provider-specific unique identifier for a file stored in the user's cloud drive (e.g., Google Drive file ID)
- **Fallback**: When cloud drive upload fails, the system automatically saves to GCS instead and notifies the user
- **On-Demand Download**: Fetching a file from the user's cloud drive when ClassBridge needs it for processing (e.g., AI regeneration)

### Database Schema

```sql
-- Cloud storage connections (OAuth tokens)
CREATE TABLE cloud_storage_connections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,  -- 'google_drive', 'onedrive', 'dropbox'
    encrypted_refresh_token TEXT NOT NULL,
    account_email VARCHAR(255),
    connected_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, provider)
);

-- Cached folder IDs for ClassBridge folder structure in user's drive
CREATE TABLE cloud_storage_folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    folder_name VARCHAR(255) NOT NULL,
    cloud_folder_id VARCHAR(255) NOT NULL,
    parent_folder_id VARCHAR(255),  -- cloud ID of parent folder
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider, course_id)
);

-- Add storage fields to source_files
ALTER TABLE source_files ADD COLUMN storage_destination VARCHAR(20) DEFAULT 'gcs';
ALTER TABLE source_files ADD COLUMN cloud_file_id VARCHAR(255);
ALTER TABLE source_files ADD COLUMN cloud_provider VARCHAR(20);
ALTER TABLE source_files ADD COLUMN cloud_folder_id VARCHAR(255);

-- Add storage preference to users
ALTER TABLE users ADD COLUMN file_storage_preference VARCHAR(20) DEFAULT 'gcs';
```

### File Upload Flow Comparison

```
CURRENT (GCS):
User uploads file → Backend extracts text → File saved to GCS → SourceFile record (gcs_path) → AI generation

NEW (Cloud Drive):
User uploads file → Backend extracts text → File saved to user's cloud drive → SourceFile record (cloud_file_id) → AI generation
                                           ↘ (if cloud fails) → File saved to GCS (fallback) → Notification to user
```

---

*This PRD was created through interactive requirements gathering with quality scoring (92/100) to ensure comprehensive coverage of business, functional, UX, and technical dimensions.*
