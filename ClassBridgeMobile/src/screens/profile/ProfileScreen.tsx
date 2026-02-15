import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { notificationsApi } from '../../api/notifications';
import { messagesApi } from '../../api/messages';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2)
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

export function ProfileScreen() {
  const { user, logout } = useAuth();

  const { data: notifCount } = useQuery({
    queryKey: ['notifUnreadCount'],
    queryFn: notificationsApi.getUnreadCount,
  });

  const { data: msgCount } = useQuery({
    queryKey: ['unreadMessages'],
    queryFn: messagesApi.getUnreadCount,
  });

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: () => logout(),
      },
    ]);
  };

  if (!user) return null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Profile header */}
      <View style={styles.profileHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{getInitials(user.full_name)}</Text>
        </View>
        <Text style={styles.name}>{user.full_name}</Text>
        <Text style={styles.email}>{user.email}</Text>
        <View style={styles.roleBadge}>
          <Text style={styles.roleBadgeText}>
            {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
          </Text>
        </View>
      </View>

      {/* Quick stats */}
      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <MaterialIcons name="notifications" size={22} color={colors.primary} />
          <Text style={styles.statValue}>
            {notifCount?.count ?? 0}
          </Text>
          <Text style={styles.statLabel}>Unread Notifs</Text>
        </View>
        <View style={styles.statCard}>
          <MaterialIcons name="chat" size={22} color={colors.secondary} />
          <Text style={styles.statValue}>
            {msgCount?.total_unread ?? 0}
          </Text>
          <Text style={styles.statLabel}>Unread Messages</Text>
        </View>
      </View>

      {/* Info section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>

        <View style={styles.infoRow}>
          <MaterialIcons name="email" size={20} color={colors.textMuted} />
          <Text style={styles.infoLabel}>Email</Text>
          <Text style={styles.infoValue}>{user.email}</Text>
        </View>

        <View style={styles.infoRow}>
          <MaterialIcons name="person" size={20} color={colors.textMuted} />
          <Text style={styles.infoLabel}>Role</Text>
          <Text style={styles.infoValue}>
            {user.roles?.length > 1
              ? user.roles.map(r => r.charAt(0).toUpperCase() + r.slice(1)).join(', ')
              : user.role.charAt(0).toUpperCase() + user.role.slice(1)}
          </Text>
        </View>

        <View style={styles.infoRow}>
          <MaterialIcons
            name={user.google_connected ? 'cloud-done' : 'cloud-off'}
            size={20}
            color={user.google_connected ? colors.secondary : colors.textMuted}
          />
          <Text style={styles.infoLabel}>Google</Text>
          <Text
            style={[
              styles.infoValue,
              { color: user.google_connected ? colors.secondary : colors.textMuted },
            ]}
          >
            {user.google_connected ? 'Connected' : 'Not connected'}
          </Text>
        </View>
      </View>

      {/* App info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>App</Text>

        <View style={styles.infoRow}>
          <MaterialIcons name="info" size={20} color={colors.textMuted} />
          <Text style={styles.infoLabel}>Version</Text>
          <Text style={styles.infoValue}>1.0.0 (Pilot)</Text>
        </View>

        <View style={styles.infoRow}>
          <MaterialIcons name="language" size={20} color={colors.textMuted} />
          <Text style={styles.infoLabel}>Web App</Text>
          <Text style={styles.infoValue}>classbridge.ca</Text>
        </View>
      </View>

      {/* Note about web */}
      <View style={styles.webNote}>
        <MaterialIcons name="laptop" size={20} color={colors.primary} />
        <Text style={styles.webNoteText}>
          To manage children, courses, study materials, and account settings, visit the web app at classbridge.ca
        </Text>
      </View>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <MaterialIcons name="logout" size={20} color={colors.error} />
        <Text style={styles.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },

  // Profile header
  profileHeader: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: fontSize.xxl,
    fontWeight: 'bold',
  },
  name: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
  },
  email: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  roleBadge: {
    marginTop: spacing.sm,
    backgroundColor: '#E3F2FD',
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  roleBadgeText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
  },

  // Stats
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  statValue: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: spacing.xs,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // Section
  section: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
  infoLabel: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    width: 80,
  },
  infoValue: {
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
  },

  // Web note
  webNote: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#E3F2FD',
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    gap: spacing.md,
  },
  webNoteText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 20,
  },

  // Logout
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: '#FDEDED',
  },
  logoutText: {
    fontSize: fontSize.md,
    color: colors.error,
    fontWeight: '600',
  },
});
