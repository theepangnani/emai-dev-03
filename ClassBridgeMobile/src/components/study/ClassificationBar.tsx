import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, TouchableOpacity } from 'react-native';
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
  onCorrection?: () => void;
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

interface SentencePart {
  text: string;
  bold: boolean;
}

function buildSentenceParts(dims: ClassificationDimension[]): SentencePart[] {
  if (dims.length === 0) return [];

  const parts: SentencePart[] = [];
  const typeVal = dims.find((d) => d.label === 'Type');
  const subjectVal = dims.find((d) => d.label === 'Subject');
  const studentVal = dims.find((d) => d.label === 'Student');
  const teacherVal = dims.find((d) => d.label === 'Teacher');

  const minConfidence = Math.min(...dims.map((d) => d.confidence));
  const isLowConfidence = minConfidence < CONFIDENCE_THRESHOLD;

  parts.push({ text: isLowConfidence ? 'This might be a ' : 'This looks like a ', bold: false });

  if (typeVal && subjectVal) {
    parts.push({ text: `${subjectVal.value} ${typeVal.value}`, bold: true });
  } else if (typeVal) {
    parts.push({ text: typeVal.value, bold: true });
  } else if (subjectVal) {
    parts.push({ text: subjectVal.value, bold: true });
  }

  if (studentVal) {
    parts.push({ text: ' for ', bold: false });
    parts.push({ text: studentVal.value, bold: true });
  }

  if (teacherVal) {
    parts.push({ text: ' from ', bold: false });
    parts.push({ text: teacherVal.value, bold: true });
  }

  parts.push({ text: '.', bold: false });

  return parts;
}

export function ClassificationBar(props: ClassificationBarProps) {
  const { loading = false, onCorrection } = props;
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

  const sentenceParts = buildSentenceParts(dimensions);

  return (
    <View style={styles.container}>
      {sentenceParts.length > 0 && (
        <Text style={styles.sentence}>
          {sentenceParts.map((part, i) => (
            <Text key={i} style={part.bold ? styles.sentenceBold : undefined}>
              {part.text}
            </Text>
          ))}
        </Text>
      )}
      {onCorrection && (
        <TouchableOpacity onPress={onCorrection}>
          <Text style={styles.correctionLink}>Not right?</Text>
        </TouchableOpacity>
      )}
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
    lineHeight: fontSize.sm * 1.5,
  },
  sentenceBold: {
    fontWeight: '700',
  },
  correctionLink: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    textDecorationLine: 'underline',
    marginTop: spacing.xs,
  },
});
