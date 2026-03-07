"""Preview all email templates in a browser with sample data.

Renders every HTML template from app/templates/ with realistic placeholder
values and opens a single index page in the default browser where you can
click through each template.

Usage:
    python -m scripts.preview_email_templates
    python -m scripts.preview_email_templates --output-dir /tmp/email-previews
"""
import os
import sys
import webbrowser
import argparse
import tempfile

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "templates",
)

# Sample data for each template (keyed by filename)
SAMPLE_DATA = {
    "welcome.html": {
        "user_name": "Priya Sharma",
        "app_url": "https://www.classbridge.ca",
    },
    "email_verification.html": {
        "user_name": "Priya Sharma",
        "verify_url": "https://www.classbridge.ca/verify-email?token=sample-token-abc123",
    },
    "email_verified_welcome.html": {
        "user_name": "Priya Sharma",
        "app_url": "https://www.classbridge.ca",
    },
    "password_reset.html": {
        "user_name": "Priya Sharma",
        "reset_url": "https://www.classbridge.ca/reset-password?token=sample-reset-token-xyz",
    },
    "assignment_reminder.html": {
        "parent_name": "Priya Sharma",
        "student_name": "Aiden Sharma",
        "assignment_title": "Photosynthesis Quiz",
        "course_name": "Science 8",
        "due_date": "March 10, 2026",
        "days_until_due": "2",
        "app_url": "https://www.classbridge.ca",
    },
    "task_reminder.html": {
        "user_name": "Priya Sharma",
        "task_title": "Review Aiden's science project outline",
        "task_description": "Help Aiden choose a biome for his ecosystem diorama and gather materials.",
        "due_date": "March 12, 2026",
        "days_until_due": "5",
        "app_url": "https://www.classbridge.ca",
    },
    "message_notification.html": {
        "recipient_name": "Priya Sharma",
        "sender_name": "Sarah Chen",
        "subject": "Aiden's progress in Science",
        "message_preview": "Hi Priya, just wanted to let you know Aiden did great on his cell lab report -- 92/100!",
        "app_url": "https://www.classbridge.ca",
        "conversation_url": "https://www.classbridge.ca/messages",
    },
    "parent_invite.html": {
        "inviter_name": "Aiden Sharma",
        "student_name": "Aiden Sharma",
        "invite_url": "https://www.classbridge.ca/accept-invite?token=sample-invite-token",
        "app_url": "https://www.classbridge.ca",
    },
    "teacher_invite.html": {
        "inviter_name": "Priya Sharma",
        "teacher_name": "Sarah Chen",
        "student_name": "Aiden Sharma",
        "invite_url": "https://www.classbridge.ca/accept-invite?token=sample-invite-token",
        "app_url": "https://www.classbridge.ca",
    },
    "teacher_invite_shadow.html": {
        "inviter_name": "Priya Sharma",
        "teacher_name": "Sarah Chen",
        "student_name": "Aiden Sharma",
        "invite_url": "https://www.classbridge.ca/accept-invite?token=sample-invite-token",
        "app_url": "https://www.classbridge.ca",
    },
    "teacher_linked_notification.html": {
        "teacher_name": "Sarah Chen",
        "parent_name": "Priya Sharma",
        "student_name": "Aiden Sharma",
        "app_url": "https://www.classbridge.ca",
    },
    "teacher_course_invite.html": {
        "inviter_name": "Admin",
        "teacher_name": "Sarah Chen",
        "course_name": "Science 8",
        "invite_url": "https://www.classbridge.ca/accept-invite?token=sample-invite-token",
        "app_url": "https://www.classbridge.ca",
    },
    "student_course_invite.html": {
        "inviter_name": "Sarah Chen",
        "student_name": "Aiden Sharma",
        "course_name": "Science 8",
        "invite_url": "https://www.classbridge.ca/accept-invite?token=sample-invite-token",
        "app_url": "https://www.classbridge.ca",
    },
    "admin_broadcast.html": {
        "subject": "System Maintenance Scheduled",
        "content": "ClassBridge will be undergoing scheduled maintenance on Saturday, March 15 from 2:00 AM to 4:00 AM EST. The platform will be temporarily unavailable during this time.",
        "app_url": "https://www.classbridge.ca",
    },
    "waitlist_confirmation.html": {
        "user_name": "Jane Doe",
        "app_url": "https://www.classbridge.ca",
    },
    "waitlist_approved.html": {
        "user_name": "Jane Doe",
        "invite_url": "https://www.classbridge.ca/register?token=sample-waitlist-token",
        "app_url": "https://www.classbridge.ca",
    },
    "waitlist_declined.html": {
        "user_name": "Jane Doe",
        "app_url": "https://www.classbridge.ca",
    },
    "waitlist_reminder.html": {
        "user_name": "Jane Doe",
        "invite_url": "https://www.classbridge.ca/register?token=sample-waitlist-token",
        "app_url": "https://www.classbridge.ca",
    },
    "waitlist_admin_notification.html": {
        "user_name": "Jane Doe",
        "user_email": "jane.doe@example.com",
        "user_role": "parent",
        "waitlist_count": "42",
        "admin_url": "https://www.classbridge.ca/admin/waitlist",
        "app_url": "https://www.classbridge.ca",
    },
}


def render_template(template_path: str, data: dict) -> str:
    """Read template and replace {{key}} placeholders with sample data."""
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    for key, value in data.items():
        html = html.replace("{{" + key + "}}", value)
    # Highlight any unreplaced placeholders in red
    import re
    html = re.sub(
        r"\{\{(\w+)\}\}",
        r'<span style="background:red;color:white;padding:2px 6px;border-radius:4px;font-weight:bold">MISSING: \1</span>',
        html,
    )
    return html


def build_index(templates: dict[str, str], output_dir: str) -> str:
    """Build an index HTML page linking to all rendered templates."""
    items = []
    for name, html in sorted(templates.items()):
        preview_path = os.path.join(output_dir, name)
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)
        label = name.replace(".html", "").replace("_", " ").title()
        items.append(f'<li style="margin:8px 0;"><a href="{name}" target="_blank" '
                     f'style="color:#4f46e5;font-size:16px;">{label}</a> '
                     f'<span style="color:#999;font-size:13px;">({name})</span></li>')

    index_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>ClassBridge Email Template Preview</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f5f7fa; }}
    h1 {{ color: #1a1a2e; }}
    .count {{ color: #4f46e5; font-weight: 600; }}
    ul {{ list-style: none; padding: 0; }}
    .note {{ background: #fff3cd; border: 1px solid #ffc107; padding: 12px 16px; border-radius: 8px; margin: 16px 0; font-size: 14px; color: #856404; }}
  </style>
</head>
<body>
  <h1>ClassBridge Email Template Preview</h1>
  <p><span class="count">{len(templates)}</span> templates rendered with sample data.</p>
  <div class="note">
    Any <span style="background:red;color:white;padding:2px 6px;border-radius:4px;font-size:12px;">MISSING: key</span>
    markers in a template indicate placeholders that need sample data added to the preview script.
  </div>
  <ul>
    {"".join(items)}
  </ul>
  <hr style="border:none;border-top:1px solid #ddd;margin:32px 0;">
  <p style="color:#999;font-size:13px;">Generated by <code>scripts/preview_email_templates.py</code></p>
</body>
</html>"""

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    return index_path


def main():
    parser = argparse.ArgumentParser(description="Preview ClassBridge email templates in a browser.")
    parser.add_argument("--output-dir", help="Directory to write rendered HTML files (default: temp dir)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open the browser")
    args = parser.parse_args()

    output_dir = args.output_dir or tempfile.mkdtemp(prefix="classbridge-emails-")
    os.makedirs(output_dir, exist_ok=True)

    # Discover all templates
    template_files = sorted(f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".html"))
    if not template_files:
        print(f"No templates found in {TEMPLATE_DIR}")
        sys.exit(1)

    rendered = {}
    for filename in template_files:
        filepath = os.path.join(TEMPLATE_DIR, filename)
        data = SAMPLE_DATA.get(filename, {})
        rendered[filename] = render_template(filepath, data)

    index_path = build_index(rendered, output_dir)

    print(f"Rendered {len(rendered)} templates to: {output_dir}")
    print()
    for name in sorted(rendered.keys()):
        label = name.replace(".html", "").replace("_", " ").title()
        missing = "{{" in rendered[name]  # Check for unreplaced after our sub
        status = " [MISSING PLACEHOLDERS]" if missing else ""
        print(f"  {label}{status}")
    print()
    print(f"Index: {index_path}")

    if not args.no_open:
        webbrowser.open(f"file:///{index_path.replace(os.sep, '/')}")
        print("Opened in browser.")


if __name__ == "__main__":
    main()
