import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { parentApi } from '../../api/parent';
import { messagesApi } from '../../api/messages';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { ChildHighlight } from '../../api/parent';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { CompositeNavigationProp } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { HomeStackParamList } from '../../navigation/AppNavigator';
import type { MainTabParamList } from '../../navigation/AppNavigator';
import { useNavigation } from '@react-navigation/native';

type DashboardNavProp = CompositeNavigationProp<
  NativeStackNavigationProp<HomeStackParamList, 'Dashboard'>,
  BottomTabNavigationProp<MainTabParamList>
>;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2)
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function ParentDashboardScreen() {
  const navigation = useNavigation<DashboardNavProp>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const insets = useSafeAreaInsets();

  const {
    data: dashboard,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const { data: unreadCount } = useQuery({
    queryKey: ['unreadMessages'],
    queryFn: messagesApi.getUnreadCount,
  });

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
    await queryClient.invalidateQueries({ queryKey: ['unreadMessages'] });
    setRefreshing(false);
  }, [queryClient]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading dashboard..." />;
  }

  if (isError || !dashboard) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load dashboard"
          subtitle="Pull down to try again"
        />
      </View>
    );
  }

  const firstName = user?.full_name?.split(' ')[0] || '';
  const messageCount = unreadCount?.total_unread ?? dashboard.unread_messages;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + spacing.md }]}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[colors.primary]}
          tintColor={colors.primary}
        />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.greeting}>
          {getGreeting()}, {firstName}
        </Text>
        <Text style={styles.subtitle}>Here's how your children are doing</Text>
      </View>

      {/* Status Summary Cards */}
      <View style={styles.statusRow}>
        <StatusCard
          count={dashboard.total_overdue}
          label="Overdue"
          icon="warning"
          color={dashboard.total_overdue > 0 ? colors.error : colors.textMuted}
          bgColor={
            dashboard.total_overdue > 0 ? '#FDEDED' : colors.surface
          }
        />
        <StatusCard
          count={dashboard.total_due_today}
          label="Due Today"
          icon="schedule"
          color={
            dashboard.total_due_today > 0 ? colors.warning : colors.textMuted
          }
          bgColor={
            dashboard.total_due_today > 0 ? '#FFF8E1' : colors.surface
          }
        />
        <StatusCard
          count={messageCount}
          label="Messages"
          icon="chat"
          color={messageCount > 0 ? colors.primary : colors.textMuted}
          bgColor={messageCount > 0 ? '#E3F2FD' : colors.surface}
          onPress={() => navigation.navigate('Messages')}
        />
      </View>

      {/* Children */}
      {dashboard.child_highlights.length === 0 ? (
        <View style={styles.emptyCard}>
          <EmptyState
            icon="child-care"
            title="No children linked"
            subtitle="Add children from the web app to see them here"
          />
        </View>
      ) : (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Your Children</Text>
          {dashboard.child_highlights.map((child, index) => (
            <ChildCard
              key={child.student_id}
              child={child}
              colorIndex={index}
              onPress={() =>
                navigation.navigate('ChildOverview', {
                  studentId: child.student_id,
                  name: child.full_name,
                })
              }
            />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

// --- Sub-components ---

function StatusCard({
  count,
  label,
  icon,
  color,
  bgColor,
  onPress,
}: {
  count: number;
  label: string;
  icon: keyof typeof MaterialIcons.glyphMap;
  color: string;
  bgColor: string;
  onPress?: () => void;
}) {
  return (
    <TouchableOpacity
      style={[styles.statusCard, { backgroundColor: bgColor }]}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={onPress ? 0.7 : 1}
    >
      <MaterialIcons name={icon} size={20} color={color} />
      <Text style={[styles.statusCount, { color }]}>{count}</Text>
      <Text style={styles.statusLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

function ChildCard({
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

        {/* Status indicators */}
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

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },
  header: {
    marginBottom: spacing.xl,
    paddingTop: spacing.md,
  },
  greeting: {
    fontSize: fontSize.xxl,
    fontWeight: 'bold',
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },

  // Status cards row
  statusRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  statusCard: {
    flex: 1,
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: borderRadius.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  statusCount: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    marginTop: spacing.xs,
  },
  statusLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // Section
  section: {
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },

  // Empty state card
  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
  },

  // Child card
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
