import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import type { ChildHighlight } from '../api/parent';

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2)
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

export function ChildCard({
  child,
  colorIndex,
  onPress,
}: {
  child: ChildHighlight;
  colorIndex: number;
  onPress: () => void;
}) {
  const avatarColor =
    colors.childColors[colorIndex % colors.childColors.length];

  return (
    <TouchableOpacity
      style={styles.childCard}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={[styles.avatar, { backgroundColor: avatarColor }]}>
        <Text style={styles.avatarText}>{getInitials(child.full_name)}</Text>
      </View>

      <View style={styles.childInfo}>
        <View style={styles.childNameRow}>
          <Text style={styles.childName}>{child.full_name}</Text>
          {child.grade_level != null && (
            <View style={styles.gradeBadge}>
              <Text style={styles.gradeBadgeText}>
                Grade {child.grade_level}
              </Text>
            </View>
          )}
        </View>

        <Text style={styles.childStats}>
          {child.courses.length} course{child.courses.length !== 1 ? 's' : ''}
        </Text>

        <View style={styles.childStatusRow}>
          {child.overdue_count > 0 && (
            <View style={[styles.statusBadge, styles.statusOverdue]}>
              <Text style={styles.statusBadgeText}>
                {child.overdue_count} overdue
              </Text>
            </View>
          )}
          {child.due_today_count > 0 && (
            <View style={[styles.statusBadge, styles.statusDueToday]}>
              <Text style={styles.statusBadgeTextDark}>
                {child.due_today_count} due today
              </Text>
            </View>
          )}
          {child.upcoming_count > 0 && (
            <View style={[styles.statusBadge, styles.statusUpcoming]}>
              <Text style={styles.statusBadgeTextMuted}>
                {child.upcoming_count} upcoming
              </Text>
            </View>
          )}
          {child.overdue_count === 0 &&
            child.due_today_count === 0 &&
            child.upcoming_count === 0 && (
              <Text style={styles.allClear}>All caught up!</Text>
            )}
        </View>
      </View>

      <MaterialIcons
        name="chevron-right"
        size={24}
        color={colors.textMuted}
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  childCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: fontSize.lg,
    fontWeight: 'bold',
  },
  childInfo: {
    flex: 1,
  },
  childNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: 2,
  },
  childName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  gradeBadge: {
    backgroundColor: colors.divider,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  gradeBadgeText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  childStats: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  childStatusRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  statusBadge: {
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  statusOverdue: {
    backgroundColor: '#FDEDED',
  },
  statusDueToday: {
    backgroundColor: '#FFF8E1',
  },
  statusUpcoming: {
    backgroundColor: '#E3F2FD',
  },
  statusBadgeText: {
    fontSize: fontSize.xs,
    color: colors.error,
    fontWeight: '500',
  },
  statusBadgeTextDark: {
    fontSize: fontSize.xs,
    color: '#E65100',
    fontWeight: '500',
  },
  statusBadgeTextMuted: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: '500',
  },
  allClear: {
    fontSize: fontSize.xs,
    color: colors.secondary,
    fontWeight: '500',
  },
});
