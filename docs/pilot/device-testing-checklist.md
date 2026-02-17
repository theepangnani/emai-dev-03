# Mobile Device Testing Checklist

Issue: #375 — Mobile MVP: Device testing (iOS + Android)

## Pre-Testing Setup

- [ ] ClassBridge development build installed on at least 1 iOS device
- [ ] ClassBridge development build installed on at least 1 Android device
- [ ] Production API is healthy: `curl -s https://www.classbridge.ca/health`
- [ ] Test parent account credentials ready
- [ ] Test data in place (children, courses, assignments, messages, notifications)

---

## iOS Physical Device Testing

### Login Screen

- [ ] App launches to login screen without crash
- [ ] ClassBridge branding displays correctly
- [ ] Email field accepts keyboard input, `@` key accessible
- [ ] Password field masks characters
- [ ] "Show password" toggle works (eye icon)
- [ ] Successful login with valid parent credentials
- [ ] Error message on invalid credentials
- [ ] Error message on network failure
- [ ] Loading spinner shows during login

### Dashboard (Home Tab)

- [ ] Greeting shows correct time-of-day (Good morning/afternoon/evening)
- [ ] User's first name appears in greeting
- [ ] Overdue count card displays correctly (red when > 0)
- [ ] Due Today count card displays correctly (amber when > 0)
- [ ] Messages count card displays correctly (blue when > 0, tappable)
- [ ] Children cards display with correct names, initials, grade levels
- [ ] Tapping child card navigates to Child Overview
- [ ] Pull-to-refresh works (data reloads)
- [ ] SafeArea: content does not overlap with notch/Dynamic Island/status bar

### Child Overview

- [ ] Back button returns to Dashboard
- [ ] Child name in header bar
- [ ] Quick stats row shows Courses, Assignments, Tasks counts
- [ ] Courses section lists courses with names, subjects, teacher names
- [ ] Google Classroom sync icon shows for synced courses
- [ ] Assignments sorted by due date (overdue first)
- [ ] Due date labels: "Overdue" (red), "Due today" (amber), date for future
- [ ] Tasks section: pending tasks show unchecked circles
- [ ] Task toggle: tapping checkbox marks task complete (optimistic update)
- [ ] Completed tasks show strikethrough text
- [ ] Pull-to-refresh works

### Calendar Tab

- [ ] Monthly grid renders correctly
- [ ] Current date highlighted with border
- [ ] Month navigation (left/right arrows) works
- [ ] Tapping month title returns to current month
- [ ] Days with items show colored dots (blue = normal, red = overdue, yellow = busy)
- [ ] Tapping a day shows detail list below calendar
- [ ] Assignment items show blue indicator, tasks show green
- [ ] "Nothing scheduled" shown for empty days
- [ ] Pull-to-refresh works

### Messages Tab

- [ ] Conversations list loads with teacher names, last message preview
- [ ] Unread conversations highlighted with blue background
- [ ] Unread badge count shows on Messages tab icon
- [ ] Time formatting correct (today: time, yesterday: "Yesterday", older: date)
- [ ] Tapping conversation opens Chat screen
- [ ] Chat: messages display in bubbles (blue = sent, white = received)
- [ ] Chat: date headers separate messages by day
- [ ] Chat: typing and sending a reply works
- [ ] Chat: sent message appears immediately (optimistic update)
- [ ] Chat: keyboard does not overlap input bar (KeyboardAvoidingView)
- [ ] Chat: marking conversation as read clears unread badge
- [ ] Pull-to-refresh on conversations list

### Notifications Tab

- [ ] Notifications list loads with icons, titles, body text, timestamps
- [ ] Unread notifications highlighted with blue background
- [ ] Unread dot indicator visible
- [ ] "Mark all read" button appears when unread > 0
- [ ] Tapping notification marks it as read
- [ ] "Mark all read" clears all unread indicators
- [ ] Time formatting correct ("Just now", "5m ago", "2h ago", "3d ago", date)
- [ ] Unread count badge on Notifications tab icon updates
- [ ] Pull-to-refresh works
- [ ] Empty state: "No notifications" message shown when none exist

### Profile Tab

- [ ] User avatar with initials displays
- [ ] Full name, email, role displayed correctly
- [ ] Unread notifications and messages counts shown
- [ ] Account section: email, role, Google connection status
- [ ] App section: version "1.0.0 (Pilot)", web app URL
- [ ] Web app note card visible
- [ ] "Sign Out" button shows confirmation dialog
- [ ] Confirming sign out returns to Login screen
- [ ] Canceling sign out stays on Profile

### Cross-Cutting iOS Concerns

- [ ] SafeAreaProvider: content respects top notch and bottom home indicator
- [ ] No content cut off at bottom behind home indicator
- [ ] Scroll behavior smooth on all scrollable screens
- [ ] Status bar text readable
- [ ] App does not crash on backgrounding and foregrounding
- [ ] Token persistence: closing and reopening app stays logged in
- [ ] 401 handling: expired token triggers logout (back to login screen)

---

## Android Physical Device Testing

Repeat ALL items from the iOS section above, plus these Android-specific checks:

### Android-Specific

- [ ] Edge-to-edge rendering works (`edgeToEdgeEnabled: true`)
- [ ] Status bar color/style appropriate
- [ ] Hardware back button on Login screen closes app (not crash)
- [ ] Hardware back button in child screens navigates back
- [ ] Hardware back button in Chat returns to Messages list
- [ ] Keyboard behavior: content adjusts when keyboard opens
- [ ] No content overlap with navigation bar at bottom
- [ ] APK installs from download link without issues
- [ ] Predictive back gesture disabled (`predictiveBackGestureEnabled: false`)

---

## Cross-Platform Verification

- [ ] Create a message on web, verify it appears on mobile
- [ ] Reply to a message on mobile, verify it appears on web
- [ ] Toggle a task on mobile, verify status on web
- [ ] Create a new assignment on web, pull-to-refresh on mobile — appears in dashboard and calendar
- [ ] Unread badge counts consistent between web and mobile
- [ ] Data created by one platform visible on the other within 30 seconds (polling interval)

---

## Network and Edge Cases

- [ ] App shows error state when API is unreachable
- [ ] App recovers gracefully when network returns (pull to refresh)
- [ ] Login with no network shows appropriate error
- [ ] Large data sets: dashboard with 5+ children, 50+ assignments — no performance issues
- [ ] Rapid tab switching does not cause crashes
- [ ] Opening app from background after 10+ minutes — data refreshes

---

## OTA Update Verification (after EAS Update configured)

- [ ] Publish a test update: `eas update --channel production --message "Test update"`
- [ ] Close and reopen app on both iOS and Android
- [ ] Verify the update is applied (visible change in UI)
- [ ] Confirm update does not require reinstallation

---

## Sign-Off

| Platform | Tester | Date | Pass/Fail | Notes |
|----------|--------|------|-----------|-------|
| iOS      |        |      |           |       |
| Android  |        |      |           |       |

Tested against production API: `https://www.classbridge.ca`
