import React from 'react';
import { View, TouchableOpacity, StyleSheet, Text } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { notificationsApi } from '../api/notifications';
import { colors, spacing, fontSize, borderRadius } from '../theme';

export function HeaderIcons() {
  const navigation = useNavigation<any>();

  const { data: notifCount } = useQuery({
    queryKey: ['notifUnreadCount'],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30000,
  });

  const unreadNotifs = notifCount?.count || 0;

  return (
    <View style={styles.container}>
      <TouchableOpacity
        onPress={() => navigation.navigate('Calendar')}
        style={styles.iconButton}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <MaterialIcons name="calendar-today" size={22} color={colors.text} />
      </TouchableOpacity>

      <TouchableOpacity
        onPress={() => navigation.navigate('Notifications')}
        style={styles.iconButton}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <MaterialIcons name="notifications" size={22} color={colors.text} />
        {unreadNotifs > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>
              {unreadNotifs > 99 ? '99+' : unreadNotifs}
            </Text>
          </View>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        onPress={() => navigation.navigate('Profile')}
        style={styles.iconButton}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <MaterialIcons name="person" size={22} color={colors.text} />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginRight: spacing.sm,
  },
  iconButton: {
    padding: spacing.xs,
    position: 'relative',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -4,
    backgroundColor: colors.error,
    borderRadius: borderRadius.full,
    minWidth: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: fontSize.xs - 2,
    fontWeight: 'bold',
  },
});
