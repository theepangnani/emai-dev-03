import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqSection {
  title: string;
  icon: keyof typeof MaterialIcons.glyphMap;
  items: FaqItem[];
}

const FAQ_SECTIONS: FaqSection[] = [
  {
    title: 'Getting Started',
    icon: 'rocket-launch',
    items: [
      {
        question: 'How do I connect my Google Classroom account?',
        answer:
          'Go to your Dashboard and click the "Connect Google Classroom" button. You\'ll be redirected to Google to sign in and grant ClassBridge permission to access your Classroom data. Once connected, your courses and assignments will sync automatically.',
      },
      {
        question: 'How do I sync my courses and assignments?',
        answer:
          'After connecting Google Classroom, your courses sync automatically. To manually refresh, click the sync button on your Dashboard or Courses page. Assignments, due dates, and class materials will be pulled from Google Classroom.',
      },
      {
        question: 'How do I link my child\'s account?',
        answer:
          'Go to the "My Kids" tab and tap "Add Child." You can create a new student profile or link an existing student by their email address. Once linked, you\'ll be able to view their courses, assignments, and progress.',
      },
    ],
  },
  {
    title: 'Study Tools',
    icon: 'auto-stories',
    items: [
      {
        question: 'How do I create a study guide from class materials?',
        answer:
          'Navigate to "Class Materials," select a course, and click "Generate Study Guide." ClassBridge uses AI to create a structured study guide from your course content. You can also upload your own files (PDFs, documents) to generate guides from.',
      },
      {
        question: 'How do I take a quiz or use flashcards?',
        answer:
          'Open any study guide and click "Take Quiz" or "Flashcards" to generate interactive study tools from that guide\'s content. Quizzes provide multiple-choice questions with instant feedback, and flashcards let you review key concepts.',
      },
      {
        question: 'How do I upload files for study guide generation?',
        answer:
          'On the "Class Materials" page, click "Upload Material." You can upload PDFs, Word documents, and other text files. ClassBridge will process the content and let you generate AI-powered study guides, quizzes, and flashcards from them.',
      },
    ],
  },
  {
    title: 'Communication',
    icon: 'chat',
    items: [
      {
        question: 'How do I send a message to a teacher or parent?',
        answer:
          'Go to the "Message" tab. Tap the compose button to start a conversation. Select the recipient from the list of connected teachers or parents, type your message, and send. You\'ll receive notifications when they reply.',
      },
      {
        question: 'How do I manage my notification preferences?',
        answer:
          'Tap the notifications icon in the header bar to view your notifications. You can mark notifications as read or dismiss them. Email notifications for important events like new messages and assignment reminders are sent automatically.',
      },
    ],
  },
  {
    title: 'Account & Settings',
    icon: 'settings',
    items: [
      {
        question: 'How do I create and track tasks?',
        answer:
          'Go to the "Task" tab. Tap the + button to create a new task with a title, description, and optional priority level. Tasks can be assigned to your children and marked as complete as they finish them.',
      },
      {
        question: 'How do I view my child\'s courses and assignments?',
        answer:
          'Go to the "My Kids" tab and tap on your child\'s card to see their courses, upcoming assignments, and tasks. You can also tap "View Courses" or "Class Materials" for a detailed view.',
      },
      {
        question: 'How do I change my password or update my profile?',
        answer:
          'Tap the profile icon in the header bar to access your profile settings. You can reset your password using the "Forgot Password" link on the login page, which sends a reset link to your email.',
      },
    ],
  },
  {
    title: 'Troubleshooting',
    icon: 'build',
    items: [
      {
        question: 'What should I do if my Google sync fails?',
        answer:
          'First, try pulling down to refresh. If it still fails, your Google authorization may have expired \u2014 reconnect Google Classroom from the web app. If the problem persists, sign out and sign back in, then reconnect.',
      },
      {
        question: 'Where can I report a bug or request a feature?',
        answer:
          'Please email us at support@classbridge.ca with a description of the issue or your feature idea. Include screenshots if possible. We review all feedback and use it to improve ClassBridge.',
      },
    ],
  },
];

export function HelpScreen() {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const toggleExpand = (key: string) => {
    setExpandedKey((prev) => (prev === key ? null : key));
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.pageSubtitle}>
        Find answers to common questions about ClassBridge
      </Text>

      {FAQ_SECTIONS.map((section, sectionIdx) => (
        <View key={section.title} style={styles.section}>
          <View style={styles.sectionHeader}>
            <MaterialIcons
              name={section.icon}
              size={20}
              color={colors.primary}
            />
            <Text style={styles.sectionTitle}>{section.title}</Text>
          </View>

          {section.items.map((item, itemIdx) => {
            const key = `${sectionIdx}-${itemIdx}`;
            const isExpanded = expandedKey === key;

            return (
              <TouchableOpacity
                key={key}
                style={styles.faqCard}
                onPress={() => toggleExpand(key)}
                activeOpacity={0.7}
              >
                <View style={styles.questionRow}>
                  <Text style={styles.questionText}>{item.question}</Text>
                  <MaterialIcons
                    name={isExpanded ? 'expand-less' : 'expand-more'}
                    size={24}
                    color={colors.textMuted}
                  />
                </View>
                {isExpanded && (
                  <Text style={styles.answerText}>{item.answer}</Text>
                )}
              </TouchableOpacity>
            );
          })}
        </View>
      ))}

      <View style={styles.contactSection}>
        <MaterialIcons name="mail" size={24} color={colors.primary} />
        <Text style={styles.contactTitle}>Still need help?</Text>
        <Text style={styles.contactText}>
          Email us at support@classbridge.ca
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  pageSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xl,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
  },
  faqCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  questionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  questionText: {
    flex: 1,
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
    lineHeight: 22,
  },
  answerText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 22,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  contactSection: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xxl,
    gap: spacing.sm,
  },
  contactTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  contactText: {
    fontSize: fontSize.sm,
    color: colors.primary,
  },
});
