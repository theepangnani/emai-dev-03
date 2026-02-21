import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { parentApi } from '../../api/parent';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { ChildCard } from '../../components/ChildCard';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { MyKidsStackParamList } from '../../navigation/AppNavigator';

type NavProp = NativeStackNavigationProp<MyKidsStackParamList, 'MyKidsHome'>;

interface ActionItem {
  icon: keyof typeof MaterialIcons.glyphMap;
  label: string;
  color: string;
  bgColor: string;
  onPress: () => void;
}

export function MyKidsScreen() {
  const navigation = useNavigation<NavProp>();
  const queryClient = useQueryClient();

  const {
    data: dashboard,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
    setRefreshing(false);
  }, [queryClient]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  if (isError || !dashboard) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load"
          subtitle="Pull down to try again"
        />
      </View>
    );
  }

  const actions: ActionItem[] = [
    {
      icon: 'person-add',
      label: 'Add Child',
      color: colors.primary,
      bgColor: '#E0F7F8',
      onPress: () => navigation.navigate('AddChild'),
    },
    {
      icon: 'menu-book',
      label: 'View Courses',
      color: '#4285F4',
      bgColor: '#E3F2FD',
      onPress: () => navigation.navigate('Courses'),
    },
    {
      icon: 'description',
      label: 'Class Materials',
      color: '#34A853',
      bgColor: '#E8F5E9',
      onPress: () => navigation.navigate('ClassMaterials'),
    },
    {
      icon: 'quiz',
      label: 'Quiz History',
      color: '#9C27B0',
      bgColor: '#F3E5F5',
      onPress: () => navigation.navigate('QuizHistory'),
    },
  ];

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
      {/* Children Section */}
      {dashboard.child_highlights.length === 0 ? (
        <View style={styles.emptyCard}>
          <EmptyState
            icon="child-care"
            title="No children linked"
            subtitle="Tap 'Add Child' below to get started"
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

      {/* Action Buttons */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          {actions.map((action) => (
            <TouchableOpacity
              key={action.label}
              style={[styles.actionCard, { backgroundColor: action.bgColor }]}
              onPress={action.onPress}
              activeOpacity={0.7}
            >
              <MaterialIcons name={action.icon} size={28} color={action.color} />
              <Text style={[styles.actionLabel, { color: action.color }]}>
                {action.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
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
  errorContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    marginBottom: spacing.xl,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  actionCard: {
    width: '47%',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    borderRadius: borderRadius.lg,
    gap: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  actionLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    textAlign: 'center',
  },
});
