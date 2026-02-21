import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { parentApi } from '../../api/parent';
import { courseContentsApi } from '../../api/courseContents';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { CourseContentItem } from '../../api/courseContents';

const TYPE_ICONS: Record<string, keyof typeof MaterialIcons.glyphMap> = {
  study_guide: 'auto-stories',
  quiz: 'quiz',
  flashcards: 'style',
};

const TYPE_LABELS: Record<string, string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
};

export function ClassMaterialsScreen() {
  const queryClient = useQueryClient();
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);

  const { data: dashboard } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const children = dashboard?.child_highlights || [];
  const selectedChild = selectedChildId
    ? children.find((c) => c.student_id === selectedChildId)
    : null;

  const {
    data: materials,
    isLoading,
  } = useQuery({
    queryKey: ['classMaterials', selectedChild?.user_id],
    queryFn: () =>
      courseContentsApi.list(
        selectedChild ? { student_user_id: selectedChild.user_id } : undefined
      ),
  });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['classMaterials'] });
    setRefreshing(false);
  }, [queryClient]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading materials..." />;
  }

  const activeMaterials = (materials || []).filter((m) => !m.archived_at);

  return (
    <View style={styles.container}>
      {/* Child Filter */}
      {children.length > 1 && (
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[
              styles.filterChip,
              !selectedChildId && styles.filterChipActive,
            ]}
            onPress={() => setSelectedChildId(null)}
          >
            <Text
              style={[
                styles.filterChipText,
                !selectedChildId && styles.filterChipTextActive,
              ]}
            >
              All
            </Text>
          </TouchableOpacity>
          {children.map((child) => (
            <TouchableOpacity
              key={child.student_id}
              style={[
                styles.filterChip,
                selectedChildId === child.student_id && styles.filterChipActive,
              ]}
              onPress={() => setSelectedChildId(child.student_id)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  selectedChildId === child.student_id &&
                    styles.filterChipTextActive,
                ]}
              >
                {child.full_name.split(' ')[0]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <FlatList
        data={activeMaterials}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
        ListEmptyComponent={
          <EmptyState
            icon="description"
            title="No materials yet"
            subtitle="Class materials will appear here"
          />
        }
        renderItem={({ item }) => (
          <MaterialCard item={item} />
        )}
      />
    </View>
  );
}

function MaterialCard({ item }: { item: CourseContentItem }) {
  const icon = TYPE_ICONS[item.content_type] || 'insert-drive-file';
  const typeLabel = TYPE_LABELS[item.content_type] || item.content_type;

  return (
    <View style={styles.materialCard}>
      <View style={styles.materialIcon}>
        <MaterialIcons name={icon} size={24} color={colors.primary} />
      </View>
      <View style={styles.materialInfo}>
        <Text style={styles.materialTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <View style={styles.materialMeta}>
          <View style={styles.typeBadge}>
            <Text style={styles.typeBadgeText}>{typeLabel}</Text>
          </View>
          {item.course_name && (
            <Text style={styles.courseName} numberOfLines={1}>
              {item.course_name}
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  filterChip: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: spacing.lg,
    paddingTop: spacing.sm,
  },
  materialCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    gap: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  materialIcon: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.md,
    backgroundColor: '#E0F7F8',
    alignItems: 'center',
    justifyContent: 'center',
  },
  materialInfo: {
    flex: 1,
  },
  materialTitle: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  materialMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  typeBadge: {
    backgroundColor: colors.divider,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  typeBadgeText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  courseName: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    flex: 1,
  },
});
