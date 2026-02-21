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
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { ChildHighlight } from '../../api/parent';

export function CoursesScreen() {
  const queryClient = useQueryClient();
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
    setRefreshing(false);
  }, [queryClient]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading courses..." />;
  }

  const children = dashboard?.child_highlights || [];
  const selected = selectedChildId
    ? children.find((c) => c.student_id === selectedChildId)
    : null;

  // Gather all courses across all children, or filter by selected child
  const courses = selected
    ? selected.courses
    : children.flatMap((c) => c.courses);

  // Deduplicate courses by id
  const uniqueCourses = courses.filter(
    (course, index, arr) => arr.findIndex((c) => c.id === course.id) === index
  );

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
        data={uniqueCourses}
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
            icon="menu-book"
            title="No courses yet"
            subtitle="Courses will appear here once synced"
          />
        }
        renderItem={({ item: course }) => (
          <View style={styles.courseCard}>
            <View style={styles.courseInfo}>
              <Text style={styles.courseName}>{course.name}</Text>
              {course.subject && (
                <Text style={styles.courseSubject}>{course.subject}</Text>
              )}
              {course.teacher_name && (
                <Text style={styles.courseTeacher}>{course.teacher_name}</Text>
              )}
            </View>
            {course.google_classroom_id && (
              <MaterialIcons
                name="cloud-done"
                size={18}
                color={colors.secondary}
              />
            )}
          </View>
        )}
      />
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
  courseCard: {
    flexDirection: 'row',
    alignItems: 'center',
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
  courseInfo: {
    flex: 1,
  },
  courseName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  courseSubject: {
    fontSize: fontSize.sm,
    color: colors.primary,
    marginTop: 2,
  },
  courseTeacher: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
