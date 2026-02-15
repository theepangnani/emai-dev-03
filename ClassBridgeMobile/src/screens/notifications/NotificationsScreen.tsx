import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../../api/notifications';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { NotificationResponse } from '../../api/notifications';

const ICON_MAP: Record<string, keyof typeof MaterialIcons.glyphMap> = {
  assignment_due: 'assignment-late',
  grade_posted: 'grade',
  message: 'chat',
  system: 'info',
};

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function NotificationsScreen() {
  const queryClient = useQueryClient();

  const { data: notifications, isLoading, isError, refetch } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(),
  });

  const markReadMutation = useMutation({
    mutationFn: (id: number) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const unreadCount = notifications?.filter(n => !n.read).length ?? 0;

  const renderNotification = ({ item }: { item: NotificationResponse }) => {
    const iconName = ICON_MAP[item.type] || 'notifications';

    return (
      <TouchableOpacity
        style={[styles.notifCard, !item.read && styles.notifUnread]}
        onPress={() => {
          if (!item.read) {
            markReadMutation.mutate(item.id);
          }
        }}
        activeOpacity={0.7}
      >
        <View
          style={[
            styles.iconContainer,
            !item.read && styles.iconContainerUnread,
          ]}
        >
          <MaterialIcons
            name={iconName}
            size={22}
            color={!item.read ? colors.primary : colors.textMuted}
          />
        </View>

        <View style={styles.notifContent}>
          <Text
            style={[styles.notifTitle, !item.read && styles.notifTitleUnread]}
            numberOfLines={2}
          >
            {item.title}
          </Text>
          {item.content && (
            <Text style={styles.notifBody} numberOfLines={2}>
              {item.content}
            </Text>
          )}
          <Text style={styles.notifTime}>{formatTime(item.created_at)}</Text>
        </View>

        {!item.read && <View style={styles.unreadDot} />}
      </TouchableOpacity>
    );
  };

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading notifications..." />;
  }

  if (isError) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load notifications"
          subtitle="Pull down to try again"
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header bar with mark all read */}
      {unreadCount > 0 && (
        <View style={styles.headerBar}>
          <Text style={styles.headerText}>
            {unreadCount} unread
          </Text>
          <TouchableOpacity
            onPress={() => markAllReadMutation.mutate()}
            disabled={markAllReadMutation.isPending}
          >
            <Text style={styles.markAllText}>
              {markAllReadMutation.isPending ? 'Marking...' : 'Mark all read'}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      <FlatList
        style={styles.list}
        contentContainerStyle={
          notifications?.length === 0 ? styles.emptyContent : styles.listContent
        }
        data={notifications}
        keyExtractor={item => String(item.id)}
        renderItem={renderNotification}
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
            icon="notifications-none"
            title="No notifications"
            subtitle="You're all caught up!"
          />
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxxl,
  },
  emptyContent: {
    flex: 1,
    justifyContent: 'center',
  },
  errorContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },

  // Header bar
  headerBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  headerText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  markAllText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
  },

  // Notification card
  notifCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
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
  notifUnread: {
    backgroundColor: colors.unread,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.divider,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  iconContainerUnread: {
    backgroundColor: '#E3F2FD',
  },
  notifContent: {
    flex: 1,
  },
  notifTitle: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  notifTitleUnread: {
    fontWeight: '600',
  },
  notifBody: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  notifTime: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
    marginTop: spacing.xs,
    marginLeft: spacing.xs,
  },
});
