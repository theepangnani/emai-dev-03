import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Linking,
} from 'react-native';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

interface ChipAction {
  label: string;
  webPath: string;
}

interface MaterialTypeSuggestionChipsProps {
  documentType?: string;
  contentId?: string;
  baseUrl?: string;
}

const CHIP_SETS: Record<string, ChipAction[]> = {
  teacher_notes: [
    { label: 'Generate Worksheets', webPath: '/worksheets/generate' },
    { label: 'Create Sample Test', webPath: '/quiz/generate' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
    { label: 'High Level Summary', webPath: '/study-guide/generate?template=high_level_summary' },
    { label: 'Full Study Guide', webPath: '/study-guide/generate' },
  ],
  course_syllabus: [
    { label: 'Generate Worksheets', webPath: '/worksheets/generate' },
    { label: 'Create Sample Test', webPath: '/quiz/generate' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
    { label: 'High Level Summary', webPath: '/study-guide/generate?template=high_level_summary' },
    { label: 'Full Study Guide', webPath: '/study-guide/generate' },
  ],
  worksheet: [
    { label: 'Generate More Worksheets', webPath: '/worksheets/generate' },
    { label: 'Generate Answer Key', webPath: '/worksheets/answer-key' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
  past_exam: [
    { label: 'Create Practice Test', webPath: '/quiz/generate' },
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
    { label: 'Weak Area Analysis', webPath: '/analytics/weak-area' },
  ],
  mock_exam: [
    { label: 'Create Practice Test', webPath: '/quiz/generate' },
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
    { label: 'Weak Area Analysis', webPath: '/analytics/weak-area' },
  ],
  student_test: [
    { label: 'Create Practice Test', webPath: '/quiz/generate' },
    { label: 'Weak Area Analysis', webPath: '/analytics/weak-area' },
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
  quiz_paper: [
    { label: 'Create Practice Test', webPath: '/quiz/generate' },
    { label: 'Weak Area Analysis', webPath: '/analytics/weak-area' },
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
  lab_experiment: [
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Generate Worksheets', webPath: '/worksheets/generate' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
  textbook_excerpt: [
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Generate Worksheets', webPath: '/worksheets/generate' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
  project_brief: [
    { label: 'Create Study Guide', webPath: '/study-guide/generate' },
    { label: 'Create Quiz', webPath: '/quiz/generate' },
    { label: 'Create Flashcards', webPath: '/flashcards/generate' },
  ],
};

const DEFAULT_CHIPS: ChipAction[] = [
  { label: 'Create Study Guide', webPath: '/study-guide/generate' },
  { label: 'Create Quiz', webPath: '/quiz/generate' },
  { label: 'Create Flashcards', webPath: '/flashcards/generate' },
];

const WEB_BASE = 'https://www.classbridge.ca';

export function MaterialTypeSuggestionChips({
  documentType,
  contentId,
  baseUrl = WEB_BASE,
}: MaterialTypeSuggestionChipsProps) {
  const chips = documentType
    ? CHIP_SETS[documentType] ?? DEFAULT_CHIPS
    : DEFAULT_CHIPS;

  const handleChipPress = (chip: ChipAction) => {
    const contentParam = contentId ? `?content_id=${contentId}` : '';
    const separator = chip.webPath.includes('?') ? '&' : '?';
    const fullContentParam = contentId
      ? `${separator}content_id=${contentId}`
      : '';
    const url = `${baseUrl}${chip.webPath}${fullContentParam || contentParam}`;
    Linking.openURL(url);
  };

  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {chips.map((chip) => (
          <TouchableOpacity
            key={chip.label}
            style={styles.chip}
            onPress={() => handleChipPress(chip)}
            activeOpacity={0.7}
          >
            <Text style={styles.chipText}>{chip.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  scrollContent: {
    paddingHorizontal: spacing.xs,
    gap: spacing.sm,
  },
  chip: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  chipText: {
    fontSize: fontSize.sm,
    color: '#FFFFFF',
    fontWeight: '600',
  },
});
