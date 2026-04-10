import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

interface ClassificationDimension {
  label: string;
  value: string;
  confidence: number;
  emoji: string;
}

interface ClassificationBarProps {
  materialType?: string;
  materialTypeDisplay?: string;
  materialTypeConfidence?: number;
  subject?: string;
  subjectConfidence?: number;
  studentName?: string;
  studentGrade?: number | null;
  studentConfidence?: number;
  teacherName?: string;
  teacherConfidence?: number;
  loading?: boolean;
}

const CONFIDENCE_THRESHOLD = 0.8;

function buildDimensions(props: ClassificationBarProps): ClassificationDimension[] {
  const dims: ClassificationDimension[] = [];

  if (props.materialTypeDisplay) {
    dims.push({
      label: 'Type',
      value: props.materialTypeDisplay,
      confidence: props.materialTypeConfidence ?? 1,
      emoji: '\u{1F4C4}',
    });
  }

  if (props.subject) {
    const subjectLabel =
      props.subject.charAt(0).toUpperCase() + props.subject.slice(1);
    dims.push({
      label: 'Subject',
      value: subjectLabel,
      confidence: props.subjectConfidence ?? 1,
      emoji: '\u{1F4DA}',
    });
  }

  if (props.studentName) {
    const studentValue = props.studentGrade
      ? `${props.studentName} \u2013 Grade ${props.studentGrade}`
      : props.studentName;
    dims.push({
      label: 'Student',
      value: studentValue,
      confidence: props.studentConfidence ?? 1,
      emoji: '\u{1F464}',
    });
  }

  if (props.teacherName) {
    dims.push({
      label: 'Teacher',
      value: props.teacherName,
      confidence: props.teacherConfidence ?? 1,
      emoji: '\u{1F468}\u{200D}\u{1F3EB}',
    });
  }

  return dims;
}

function buildSentence(dims: ClassificationDimension[]): string {
  if (dims.length === 0) return '';

  const parts: string[] = [];
  const typeVal = dims.find((d) => d.label === 'Type');
  const subjectVal = dims.find((d) => d.label === 'Subject');
  const studentVal = dims.find((d) => d.label === 'Student');
  const teacherVal = dims.find((d) => d.label === 'Teacher');

  if (typeVal && subjectVal) {
    parts.push(`${subjectVal.value} ${typeVal.value}`);
  } else if (typeVal) {
    parts.push(typeVal.value);
  } else if (subjectVal) {
    parts.push(subjectVal.value);
  }

  if (studentVal) {
    parts.push(`for ${studentVal.value}`);
  }

  if (teacherVal) {
    parts.push(`from ${teacherVal.value}`);
  }

  return parts.join(' ');
}

export function ClassificationBar(props: ClassificationBarProps) {
  const { loading = false } = props;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (loading) {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 0.4,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
        ])
      );
      animation.start();
      return () => animation.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [loading, pulseAnim]);

  const dimensions = buildDimensions(props);

  if (dimensions.length === 0 && !loading) {
    return null;
  }

  if (loading) {
    return (
      <Animated.View style={[styles.container, { opacity: pulseAnim }]}>
        <Text style={styles.loadingText}>Detecting document details...</Text>
      </Animated.View>
    );
  }

  const sentence = buildSentence(dimensions);

  return (
    <View style={styles.container}>
      {sentence ? <Text style={styles.sentence}>{sentence}</Text> : null}
      <View style={styles.badgeRow}>
        {dimensions.map((dim) => {
          const isLowConfidence = dim.confidence < CONFIDENCE_THRESHOLD;
          return (
            <View
              key={dim.label}
              style={[
                styles.badge,
                isLowConfidence && styles.badgeLowConfidence,
              ]}
            >
              <Text style={styles.badgeText}>
                {dim.emoji} {dim.value}
                {isLowConfidence ? ' ?' : ''}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  loadingText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  sentence: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: '500',
    marginBottom: spacing.sm,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  badge: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  badgeLowConfidence: {
    borderStyle: 'dashed',
    borderColor: colors.warning,
    backgroundColor: '#FFFDF5',
  },
  badgeText: {
    fontSize: fontSize.xs,
    color: colors.text,
  },
});
