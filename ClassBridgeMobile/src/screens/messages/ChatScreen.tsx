import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { messagesApi } from '../../api/messages';
import { useAuth } from '../../context/AuthContext';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { MessageResponse } from '../../api/messages';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { MessagesStackParamList } from '../../navigation/AppNavigator';

type Props = NativeStackScreenProps<MessagesStackParamList, 'Chat'>;

function formatMessageTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function formatDateHeader(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const msgDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (msgDay.getTime() === today.getTime()) return 'Today';
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (msgDay.getTime() === yesterday.getTime()) return 'Yesterday';
  return date.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export function ChatScreen({ route }: Props) {
  const { conversationId } = route.params;
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const flatListRef = useRef<FlatList>(null);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);

  const { data: conversation, isLoading, isError } = useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => messagesApi.getConversation(conversationId),
  });

  // Mark as read when conversation loads
  useEffect(() => {
    if (conversation) {
      messagesApi.markAsRead(conversationId).then(() => {
        queryClient.invalidateQueries({ queryKey: ['conversations'] });
        queryClient.invalidateQueries({ queryKey: ['unreadMessages'] });
      }).catch(() => {});
    }
  }, [conversation, conversationId, queryClient]);

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      messagesApi.sendMessage(conversationId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
  });

  const handleSend = useCallback(async () => {
    const text = messageText.trim();
    if (!text || sending) return;

    setSending(true);
    setMessageText('');
    try {
      await sendMutation.mutateAsync(text);
    } catch {
      setMessageText(text); // restore on failure
    } finally {
      setSending(false);
    }
  }, [messageText, sending, sendMutation]);

  // Reverse messages and insert date separators for inverted FlatList
  const itemsWithDates = React.useMemo(() => {
    const reversed = conversation?.messages ? [...conversation.messages].reverse() : [];
    const items: Array<{ type: 'message'; data: MessageResponse } | { type: 'date'; date: string }> = [];
    let lastDate = '';
    // reversed: oldest first visually in inverted list = newest first in array
    for (let i = reversed.length - 1; i >= 0; i--) {
      const msg = reversed[i];
      const msgDate = new Date(msg.created_at);
      const dateStr = `${msgDate.getFullYear()}-${msgDate.getMonth()}-${msgDate.getDate()}`;
      if (dateStr !== lastDate) {
        items.push({ type: 'date', date: msg.created_at });
        lastDate = dateStr;
      }
      items.push({ type: 'message', data: msg });
    }
    return items.reverse(); // re-reverse for inverted FlatList
  }, [conversation?.messages]);

  const renderItem = ({ item }: { item: (typeof itemsWithDates)[0] }) => {
    if (item.type === 'date') {
      return (
        <View style={styles.dateHeader}>
          <Text style={styles.dateHeaderText}>{formatDateHeader(item.date)}</Text>
        </View>
      );
    }

    const msg = item.data;
    const isMine = msg.sender_id === user?.id;

    return (
      <View
        style={[
          styles.bubbleRow,
          isMine ? styles.bubbleRowMine : styles.bubbleRowTheirs,
        ]}
      >
        <View
          style={[
            styles.bubble,
            isMine ? styles.bubbleMine : styles.bubbleTheirs,
          ]}
        >
          {!isMine && (
            <Text style={styles.senderName}>{msg.sender_name}</Text>
          )}
          <Text style={[styles.messageText, isMine && styles.messageTextMine]}>
            {msg.content}
          </Text>
          <Text style={[styles.timeText, isMine && styles.timeTextMine]}>
            {formatMessageTime(msg.created_at)}
          </Text>
        </View>
      </View>
    );
  };

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  if (isError) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load conversation"
        />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Subject bar */}
      {conversation?.subject && (
        <View style={styles.subjectBar}>
          <Text style={styles.subjectText}>{conversation.subject}</Text>
          {conversation.student_name && (
            <Text style={styles.studentText}>
              Re: {conversation.student_name}
            </Text>
          )}
        </View>
      )}

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        style={styles.messagesList}
        contentContainerStyle={
          itemsWithDates.length === 0 ? styles.emptyMessages : styles.messagesContent
        }
        data={itemsWithDates}
        keyExtractor={(item, index) =>
          item.type === 'date' ? `date-${index}` : `msg-${item.data.id}`
        }
        renderItem={renderItem}
        inverted
        ListEmptyComponent={
          <EmptyState
            icon="chat-bubble-outline"
            title="No messages yet"
            subtitle="Send the first message"
          />
        }
      />

      {/* Input bar */}
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={messageText}
          onChangeText={setMessageText}
          placeholder="Type a message..."
          placeholderTextColor={colors.textMuted}
          multiline
          maxLength={2000}
          editable={!sending}
        />
        <TouchableOpacity
          style={[
            styles.sendButton,
            (!messageText.trim() || sending) && styles.sendButtonDisabled,
          ]}
          onPress={handleSend}
          disabled={!messageText.trim() || sending}
        >
          <MaterialIcons
            name="send"
            size={22}
            color={
              messageText.trim() && !sending ? '#FFFFFF' : colors.textMuted
            }
          />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },

  // Subject bar
  subjectBar: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  subjectText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  studentText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    marginTop: 1,
  },

  // Messages list
  messagesList: {
    flex: 1,
  },
  messagesContent: {
    padding: spacing.md,
    paddingBottom: spacing.sm,
  },
  emptyMessages: {
    flex: 1,
    justifyContent: 'center',
    transform: [{ scaleY: -1 }], // un-invert for empty state
  },

  // Date header
  dateHeader: {
    alignItems: 'center',
    marginVertical: spacing.sm,
  },
  dateHeaderText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    backgroundColor: colors.divider,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
  },

  // Message bubbles
  bubbleRow: {
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  bubbleRowMine: {
    alignItems: 'flex-end',
  },
  bubbleRowTheirs: {
    alignItems: 'flex-start',
  },
  bubble: {
    maxWidth: '80%',
    borderRadius: borderRadius.lg,
    padding: spacing.md,
  },
  bubbleMine: {
    backgroundColor: colors.primary,
    borderBottomRightRadius: 4,
  },
  bubbleTheirs: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  senderName: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: 2,
  },
  messageText: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 20,
  },
  messageTextMine: {
    color: '#FFFFFF',
  },
  timeText: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: spacing.xs,
    alignSelf: 'flex-end',
  },
  timeTextMine: {
    color: 'rgba(255,255,255,0.7)',
  },

  // Input bar
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: spacing.sm,
    paddingBottom: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  input: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    fontSize: fontSize.md,
    color: colors.text,
    maxHeight: 100,
    marginRight: spacing.sm,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: colors.divider,
  },
});
