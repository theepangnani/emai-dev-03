import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { messagesApi } from '../../api/messages';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { ConversationSummary } from '../../api/messages';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { MessagesStackParamList } from '../../navigation/AppNavigator';

type NavProp = NativeStackNavigationProp<MessagesStackParamList, 'ConversationsList'>;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2)
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const messageDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (messageDay.getTime() === today.getTime()) {
    return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (messageDay.getTime() === yesterday.getTime()) {
    return 'Yesterday';
  }

  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function MessagesListScreen() {
  const navigation = useNavigation<NavProp>();
  const queryClient = useQueryClient();

  const { data: conversations, isLoading, isError } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => messagesApi.listConversations(),
  });

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['conversations'] });
    await queryClient.invalidateQueries({ queryKey: ['unreadMessages'] });
    setRefreshing(false);
  }, [queryClient]);

  const renderConversation = ({ item }: { item: ConversationSummary }) => {
    const hasUnread = item.unread_count > 0;

    return (
      <TouchableOpacity
        style={[styles.conversationCard, hasUnread && styles.conversationUnread]}
        onPress={() =>
          navigation.navigate('Chat', {
            conversationId: item.id,
            name: item.other_participant_name,
          })
        }
        activeOpacity={0.7}
      >
        <View style={[styles.avatar, hasUnread && styles.avatarUnread]}>
          <Text style={styles.avatarText}>
            {getInitials(item.other_participant_name)}
          </Text>
        </View>

        <View style={styles.conversationInfo}>
          <View style={styles.conversationHeader}>
            <Text
              style={[styles.participantName, hasUnread && styles.textBold]}
              numberOfLines={1}
            >
              {item.other_participant_name}
            </Text>
            <Text style={styles.timeText}>{formatTime(item.last_message_at)}</Text>
          </View>

          {item.subject && (
            <Text style={styles.subject} numberOfLines={1}>
              {item.subject}
            </Text>
          )}

          <View style={styles.previewRow}>
            <Text
              style={[styles.preview, hasUnread && styles.previewUnread]}
              numberOfLines={1}
            >
              {item.last_message_preview || 'No messages yet'}
            </Text>
            {hasUnread && (
              <View style={styles.unreadBadge}>
                <Text style={styles.unreadBadgeText}>{item.unread_count}</Text>
              </View>
            )}
          </View>

          {item.student_name && (
            <Text style={styles.studentTag}>Re: {item.student_name}</Text>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading messages..." />;
  }

  if (isError) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load messages"
          subtitle="Pull down to try again"
        />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={
        conversations?.length === 0 ? styles.emptyContent : styles.listContent
      }
      data={conversations}
      keyExtractor={item => String(item.id)}
      renderItem={renderConversation}
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
          icon="chat-bubble-outline"
          title="No conversations"
          subtitle="Messages with teachers will appear here"
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
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

  // Conversation card
  conversationCard: {
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
  conversationUnread: {
    backgroundColor: colors.unread,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.textMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  avatarUnread: {
    backgroundColor: colors.primary,
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  conversationInfo: {
    flex: 1,
  },
  conversationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  participantName: {
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
    marginRight: spacing.sm,
  },
  textBold: {
    fontWeight: '700',
  },
  timeText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  subject: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  previewRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  preview: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    flex: 1,
  },
  previewUnread: {
    color: colors.text,
  },
  unreadBadge: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
    marginLeft: spacing.sm,
  },
  unreadBadgeText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: 'bold',
  },
  studentTag: {
    fontSize: fontSize.xs,
    color: colors.primary,
    marginTop: 2,
  },
});
