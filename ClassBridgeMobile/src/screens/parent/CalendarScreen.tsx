import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { parentApi } from '../../api/parent';
import { tasksApi } from '../../api/tasks';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

interface CalendarItem {
  id: number;
  title: string;
  type: 'assignment' | 'task';
  dueDate: string;
  courseName?: string;
  isCompleted?: boolean;
  priority?: string;
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = [];
  const date = new Date(year, month, 1);
  while (date.getMonth() === month) {
    days.push(new Date(date));
    date.setDate(date.getDate() + 1);
  }
  return days;
}

export function CalendarScreen() {
  const today = new Date();
  const [currentMonth, setCurrentMonth] = useState(today.getMonth());
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [selectedDate, setSelectedDate] = useState<string>(dateKey(today));

  const { data: dashboard, isLoading, refetch } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const { data: tasks, refetch: refetchTasks } = useQuery({
    queryKey: ['allTasks'],
    queryFn: () => tasksApi.list(),
  });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refetch(), refetchTasks()]);
    setRefreshing(false);
  }, [refetch, refetchTasks]);

  // Build course name lookup from child_highlights
  const courseNameMap = useMemo(() => {
    const map: Record<number, string> = {};
    if (dashboard) {
      for (const child of dashboard.child_highlights) {
        for (const course of child.courses) {
          map[course.id] = course.name;
        }
      }
    }
    return map;
  }, [dashboard]);

  // Merge assignments + tasks into CalendarItems
  const allItems = useMemo<CalendarItem[]>(() => {
    const items: CalendarItem[] = [];
    if (dashboard) {
      for (const a of dashboard.all_assignments) {
        if (a.due_date) {
          items.push({
            id: a.id,
            title: a.title,
            type: 'assignment',
            dueDate: a.due_date,
            courseName: courseNameMap[a.course_id],
          });
        }
      }
    }
    if (tasks) {
      for (const t of tasks) {
        if (t.due_date && !t.archived_at) {
          items.push({
            id: t.id + 1_000_000,
            title: t.title,
            type: 'task',
            dueDate: t.due_date,
            isCompleted: t.is_completed,
            priority: t.priority ?? undefined,
          });
        }
      }
    }
    return items;
  }, [dashboard, tasks, courseNameMap]);

  // Group items by date key
  const itemsByDate = useMemo(() => {
    const map: Record<string, CalendarItem[]> = {};
    for (const item of allItems) {
      const dk = dateKey(new Date(item.dueDate));
      if (!map[dk]) map[dk] = [];
      map[dk].push(item);
    }
    return map;
  }, [allItems]);

  // Calendar grid
  const days = getDaysInMonth(currentYear, currentMonth);
  const firstDayOfWeek = days[0].getDay();
  const todayKey = dateKey(today);
  const selectedItems = itemsByDate[selectedDate] || [];

  const goToPrevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear(y => y - 1);
    } else {
      setCurrentMonth(m => m - 1);
    }
  };

  const goToNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear(y => y + 1);
    } else {
      setCurrentMonth(m => m + 1);
    }
  };

  const goToToday = () => {
    setCurrentMonth(today.getMonth());
    setCurrentYear(today.getFullYear());
    setSelectedDate(todayKey);
  };

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading calendar..." />;
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[colors.primary]}
          tintColor={colors.primary}
        />
      }
    >
      {/* Month header */}
      <View style={styles.monthHeader}>
        <TouchableOpacity onPress={goToPrevMonth} style={styles.navButton}>
          <MaterialIcons name="chevron-left" size={28} color={colors.text} />
        </TouchableOpacity>
        <TouchableOpacity onPress={goToToday}>
          <Text style={styles.monthTitle}>
            {MONTHS[currentMonth]} {currentYear}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={goToNextMonth} style={styles.navButton}>
          <MaterialIcons name="chevron-right" size={28} color={colors.text} />
        </TouchableOpacity>
      </View>

      {/* Weekday headers */}
      <View style={styles.weekdayRow}>
        {WEEKDAYS.map(d => (
          <Text key={d} style={styles.weekdayText}>{d}</Text>
        ))}
      </View>

      {/* Calendar grid */}
      <View style={styles.calendarGrid}>
        {/* Empty cells for padding before 1st day */}
        {Array.from({ length: firstDayOfWeek }).map((_, i) => (
          <View key={`pad-${i}`} style={styles.dayCell} />
        ))}

        {days.map(day => {
          const dk = dateKey(day);
          const isToday = dk === todayKey;
          const isSelected = dk === selectedDate;
          const hasItems = !!itemsByDate[dk];
          const itemCount = itemsByDate[dk]?.length || 0;
          const hasOverdue = itemsByDate[dk]?.some(
            item => item.type === 'assignment' && new Date(item.dueDate) < today && dk < todayKey
          );

          return (
            <TouchableOpacity
              key={dk}
              style={[
                styles.dayCell,
                isSelected && styles.dayCellSelected,
                isToday && !isSelected && styles.dayCellToday,
              ]}
              onPress={() => setSelectedDate(dk)}
              activeOpacity={0.7}
            >
              <Text
                style={[
                  styles.dayNumber,
                  isSelected && styles.dayNumberSelected,
                  isToday && !isSelected && styles.dayNumberToday,
                ]}
              >
                {day.getDate()}
              </Text>
              {hasItems && (
                <View style={styles.dotRow}>
                  <View
                    style={[
                      styles.dot,
                      {
                        backgroundColor: hasOverdue
                          ? colors.error
                          : itemCount > 2
                            ? colors.warning
                            : colors.primary,
                      },
                    ]}
                  />
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Selected day items */}
      <View style={styles.dayDetail}>
        <Text style={styles.dayDetailTitle}>
          {formatSelectedDate(selectedDate)}
        </Text>

        {selectedItems.length === 0 ? (
          <View style={styles.emptyDay}>
            <Text style={styles.emptyDayText}>Nothing scheduled</Text>
          </View>
        ) : (
          selectedItems
            .sort((a, b) => a.type.localeCompare(b.type))
            .map(item => (
              <View key={item.id} style={styles.itemCard}>
                <View
                  style={[
                    styles.itemTypeIndicator,
                    {
                      backgroundColor:
                        item.type === 'assignment'
                          ? colors.primary
                          : colors.secondary,
                    },
                  ]}
                />
                <View style={styles.itemInfo}>
                  <Text
                    style={[
                      styles.itemTitle,
                      item.isCompleted && styles.itemTitleCompleted,
                    ]}
                  >
                    {item.title}
                  </Text>
                  <View style={styles.itemMeta}>
                    <Text style={styles.itemType}>
                      {item.type === 'assignment' ? 'Assignment' : 'Task'}
                    </Text>
                    {item.courseName && (
                      <Text style={styles.itemCourse}>{item.courseName}</Text>
                    )}
                    {item.priority === 'high' && (
                      <Text style={styles.highPriority}>High</Text>
                    )}
                  </View>
                </View>
                {item.isCompleted && (
                  <MaterialIcons
                    name="check-circle"
                    size={20}
                    color={colors.secondary}
                  />
                )}
              </View>
            ))
        )}
      </View>
    </ScrollView>
  );
}

function formatSelectedDate(dk: string): string {
  const [year, month, day] = dk.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingBottom: spacing.xxxl,
  },

  // Month header
  monthHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  navButton: {
    padding: spacing.xs,
  },
  monthTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
  },

  // Weekday headers
  weekdayRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.xs,
  },
  weekdayText: {
    flex: 1,
    textAlign: 'center',
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.textMuted,
  },

  // Calendar grid
  calendarGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: spacing.sm,
  },
  dayCell: {
    width: '14.28%',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    minHeight: 44,
  },
  dayCellSelected: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
  },
  dayCellToday: {
    borderWidth: 1.5,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
  },
  dayNumber: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: '500',
  },
  dayNumberSelected: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  dayNumberToday: {
    color: colors.primary,
    fontWeight: 'bold',
  },
  dotRow: {
    flexDirection: 'row',
    marginTop: 2,
    gap: 2,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
  },

  // Day detail
  dayDetail: {
    padding: spacing.lg,
  },
  dayDetailTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  emptyDay: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.xl,
    alignItems: 'center',
  },
  emptyDayText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },

  // Item card
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  itemTypeIndicator: {
    width: 4,
    height: '80%',
    borderRadius: 2,
    marginRight: spacing.md,
    minHeight: 28,
  },
  itemInfo: {
    flex: 1,
  },
  itemTitle: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
  },
  itemTitleCompleted: {
    textDecorationLine: 'line-through',
    color: colors.textMuted,
  },
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: 2,
  },
  itemType: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  itemCourse: {
    fontSize: fontSize.xs,
    color: colors.primary,
  },
  highPriority: {
    fontSize: fontSize.xs,
    color: colors.error,
    fontWeight: '600',
  },
});
