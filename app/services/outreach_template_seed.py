import logging
from sqlalchemy.orm import Session
from app.models.parent_contact import OutreachTemplate

logger = logging.getLogger(__name__)

SEED_TEMPLATES = [
    {
        "name": "Initial Outreach",
        "subject": "Discover ClassBridge \u2014 The Smartest Way to Support Your Child\u2019s Learning",
        "template_type": "email",
        "variables": ["full_name", "child_name", "classbridge_url"],
        "body_text": """Hi {{full_name}},

We wanted to introduce you to ClassBridge \u2014 an AI-powered platform that helps parents like you stay on top of your child\u2019s education.

ClassBridge connects directly with Google Classroom to give you real-time visibility into {{child_name}}\u2019s assignments, grades, and progress. Our AI study tools generate personalized study guides, practice quizzes, and flashcards from actual course materials.

Key features:
\u2022 Real-time Google Classroom integration
\u2022 AI-generated study guides and quizzes
\u2022 Parent dashboard with assignment tracking
\u2022 Direct teacher communication

Learn more at {{classbridge_url}}

Best regards,
The ClassBridge Team""",
        "body_html": """<h2 style="color:#1e293b;margin:0 0 16px 0;">Stay Connected to Your Child\u2019s Education</h2>
<p style="color:#334155;font-size:15px;line-height:1.6;">Hi {{full_name}},</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">We wanted to introduce you to <strong>ClassBridge</strong> \u2014 an AI-powered platform that helps parents like you stay on top of your child\u2019s education.</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">ClassBridge connects directly with Google Classroom to give you real-time visibility into {{child_name}}\u2019s assignments, grades, and progress. Our AI study tools generate personalized study guides, practice quizzes, and flashcards from actual course materials.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">\u2713</strong> Real-time Google Classroom integration</td></tr>
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">\u2713</strong> AI-generated study guides and quizzes</td></tr>
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">\u2713</strong> Parent dashboard with assignment tracking</td></tr>
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">\u2713</strong> Direct teacher communication</td></tr>
</table>
<p style="text-align:center;margin:32px 0;">
<a href="{{classbridge_url}}" style="background:#4f46e5;color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Learn More</a>
</p>
<p style="color:#64748b;font-size:13px;margin-top:24px;">Best regards,<br>The ClassBridge Team</p>""",
    },
    {
        "name": "Follow-Up #1 (3 days)",
        "subject": "Did you get a chance to check out ClassBridge, {{full_name}}?",
        "template_type": "email",
        "variables": ["full_name", "child_name", "classbridge_url"],
        "body_text": """Hi {{full_name}},

Just a quick follow-up \u2014 did you get a chance to explore ClassBridge?

We know how busy parents are, so we built ClassBridge to save you time. In just a few minutes, you can see exactly what {{child_name}} is working on in school and get AI-powered study tools to help them succeed.

Join our waitlist to get early access: {{classbridge_url}}/waitlist

Best,
The ClassBridge Team""",
        "body_html": """<h2 style="color:#1e293b;margin:0 0 16px 0;">Quick Follow-Up</h2>
<p style="color:#334155;font-size:15px;line-height:1.6;">Hi {{full_name}},</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">Just a quick follow-up \u2014 did you get a chance to explore <strong>ClassBridge</strong>?</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">We know how busy parents are, so we built ClassBridge to save you time. In just a few minutes, you can see exactly what {{child_name}} is working on in school and get AI-powered study tools to help them succeed.</p>
<p style="text-align:center;margin:32px 0;">
<a href="{{classbridge_url}}/waitlist" style="background:#4f46e5;color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Join the Waitlist</a>
</p>
<p style="color:#64748b;font-size:13px;">Best,<br>The ClassBridge Team</p>""",
    },
    {
        "name": "Follow-Up #2 (7 days)",
        "subject": "How ClassBridge Helps Parents Like You Stay On Top of School",
        "template_type": "email",
        "variables": ["full_name", "classbridge_url"],
        "body_text": """Hi {{full_name}},

Parents using ClassBridge tell us the same thing: "I finally know what\u2019s going on at school."

Here\u2019s what makes ClassBridge different:

\u2022 AI Study Guides \u2014 Upload any school document and get a personalized study guide in seconds
\u2022 Practice Quizzes \u2014 AI generates quizzes from actual course materials at Easy, Medium, or Hard levels
\u2022 Assignment Tracking \u2014 See all upcoming deadlines and grades in one dashboard
\u2022 Teacher Communication \u2014 Message teachers directly through the platform

Get started for free: {{classbridge_url}}/waitlist

Cheers,
The ClassBridge Team""",
        "body_html": """<h2 style="color:#1e293b;margin:0 0 16px 0;">What Makes ClassBridge Different</h2>
<p style="color:#334155;font-size:15px;line-height:1.6;">Hi {{full_name}},</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">Parents using ClassBridge tell us the same thing: <em>"I finally know what\u2019s going on at school."</em></p>
<p style="color:#334155;font-size:15px;line-height:1.6;">Here\u2019s what makes ClassBridge different:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
<tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;"><strong>&#128218; AI Study Guides</strong> \u2014 Upload any school document and get a personalized study guide in seconds</td></tr>
<tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;"><strong>&#128221; Practice Quizzes</strong> \u2014 AI generates quizzes at Easy, Medium, or Hard levels</td></tr>
<tr><td style="padding:10px 0;border-bottom:1px solid #f1f5f9;"><strong>&#128202; Assignment Tracking</strong> \u2014 See all upcoming deadlines and grades in one place</td></tr>
<tr><td style="padding:10px 0;"><strong>&#128172; Teacher Communication</strong> \u2014 Message teachers directly through the platform</td></tr>
</table>
<p style="text-align:center;margin:32px 0;">
<a href="{{classbridge_url}}/waitlist" style="background:#4f46e5;color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Get Started Free</a>
</p>
<p style="color:#64748b;font-size:13px;">Cheers,<br>The ClassBridge Team</p>""",
    },
    {
        "name": "Follow-Up #3 (14 days)",
        "subject": "Last chance \u2014 ClassBridge pilot spots are filling up",
        "template_type": "email",
        "variables": ["full_name", "child_name", "classbridge_url"],
        "body_text": """Hi {{full_name}},

This is our last email \u2014 we don\u2019t want to be a nuisance!

We\u2019re currently running a limited pilot program for ClassBridge, and spots are filling up. As an early adopter, you\u2019ll get:

\u2022 Free access during the pilot period
\u2022 Direct input on features we build next
\u2022 Priority support from our team

If ClassBridge sounds like it could help you stay connected to {{child_name}}\u2019s education, we\u2019d love to have you.

Claim your spot: {{classbridge_url}}/waitlist

All the best,
The ClassBridge Team""",
        "body_html": """<h2 style="color:#1e293b;margin:0 0 16px 0;">Last Chance \u2014 Pilot Spots Filling Up</h2>
<p style="color:#334155;font-size:15px;line-height:1.6;">Hi {{full_name}},</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">This is our last email \u2014 we don\u2019t want to be a nuisance!</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">We\u2019re currently running a <strong>limited pilot program</strong> for ClassBridge, and spots are filling up. As an early adopter, you\u2019ll get:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">&#127873;</strong> Free access during the pilot period</td></tr>
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">&#128161;</strong> Direct input on features we build next</td></tr>
<tr><td style="padding:8px 0;"><strong style="color:#4f46e5;">&#128640;</strong> Priority support from our team</td></tr>
</table>
<p style="color:#334155;font-size:15px;line-height:1.6;">If ClassBridge sounds like it could help you stay connected to {{child_name}}\u2019s education, we\u2019d love to have you.</p>
<p style="text-align:center;margin:32px 0;">
<a href="{{classbridge_url}}/waitlist" style="background:#dc2626;color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Claim Your Spot</a>
</p>
<p style="color:#64748b;font-size:13px;">All the best,<br>The ClassBridge Team</p>""",
    },
    {
        "name": "Pilot Invite",
        "subject": "You\u2019re Invited \u2014 Join the ClassBridge Pilot Program",
        "template_type": "email",
        "variables": ["full_name", "child_name", "classbridge_url", "invite_token"],
        "body_text": """Hi {{full_name}},

Great news \u2014 you\u2019ve been selected for the ClassBridge pilot program!

ClassBridge is an AI-powered education platform that connects with Google Classroom to help you track {{child_name}}\u2019s progress and provide personalized study tools.

As a pilot member, you\u2019ll have full access to all features including:
\u2022 AI study guides and practice quizzes
\u2022 Real-time assignment and grade tracking
\u2022 Teacher messaging
\u2022 Parent dashboard

Click below to create your account:
{{classbridge_url}}/register?token={{invite_token}}

Welcome aboard!
The ClassBridge Team""",
        "body_html": """<h2 style="color:#1e293b;margin:0 0 16px 0;">&#127881; You\u2019re Invited!</h2>
<p style="color:#334155;font-size:15px;line-height:1.6;">Hi {{full_name}},</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">Great news \u2014 you\u2019ve been selected for the <strong>ClassBridge pilot program</strong>!</p>
<p style="color:#334155;font-size:15px;line-height:1.6;">ClassBridge is an AI-powered education platform that connects with Google Classroom to help you track {{child_name}}\u2019s progress and provide personalized study tools.</p>
<div style="background:#f0f9ff;border-radius:12px;padding:20px;margin:24px 0;">
<p style="color:#1e293b;font-weight:600;margin:0 0 12px 0;">As a pilot member, you get full access to:</p>
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:6px 0;">\u2705 AI study guides and practice quizzes</td></tr>
<tr><td style="padding:6px 0;">\u2705 Real-time assignment and grade tracking</td></tr>
<tr><td style="padding:6px 0;">\u2705 Teacher messaging</td></tr>
<tr><td style="padding:6px 0;">\u2705 Parent dashboard</td></tr>
</table>
</div>
<p style="text-align:center;margin:32px 0;">
<a href="{{classbridge_url}}/register?token={{invite_token}}" style="background:#4f46e5;color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Accept Invitation</a>
</p>
<p style="color:#64748b;font-size:13px;">Welcome aboard!<br>The ClassBridge Team</p>""",
    },
]


def seed_outreach_templates(db: Session) -> None:
    """Seed default outreach templates if table is empty."""
    if db.query(OutreachTemplate).count() > 0:
        return

    for tmpl_data in SEED_TEMPLATES:
        template = OutreachTemplate(
            name=tmpl_data["name"],
            subject=tmpl_data["subject"],
            body_html=tmpl_data["body_html"],
            body_text=tmpl_data["body_text"],
            template_type=tmpl_data["template_type"],
            variables=tmpl_data["variables"],
            is_active=True,
        )
        db.add(template)

    db.commit()
    logger.info("Seeded %d outreach templates", len(SEED_TEMPLATES))
