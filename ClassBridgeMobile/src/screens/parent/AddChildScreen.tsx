import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { parentApi } from '../../api/parent';
import { colors, spacing, fontSize, borderRadius } from '../../theme';

type Mode = 'create' | 'link';

export function AddChildScreen() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<Mode>('create');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');

  const createMutation = useMutation({
    mutationFn: () => parentApi.createChild(fullName.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
      queryClient.invalidateQueries({ queryKey: ['parentChildren'] });
      Alert.alert('Success', 'Child added successfully!');
      navigation.goBack();
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail || 'Failed to create child. Please try again.';
      Alert.alert('Error', msg);
    },
  });

  const linkMutation = useMutation({
    mutationFn: () => parentApi.linkChild(email.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
      queryClient.invalidateQueries({ queryKey: ['parentChildren'] });
      Alert.alert('Success', 'Child linked successfully!');
      navigation.goBack();
    },
    onError: (err: any) => {
      const msg =
        err?.response?.data?.detail || 'Failed to link child. Please check the email.';
      Alert.alert('Error', msg);
    },
  });

  const handleSubmit = () => {
    if (mode === 'create') {
      if (!fullName.trim()) {
        Alert.alert('Required', 'Please enter the child\'s name.');
        return;
      }
      createMutation.mutate();
    } else {
      if (!email.trim()) {
        Alert.alert('Required', 'Please enter the child\'s email.');
        return;
      }
      linkMutation.mutate();
    }
  };

  const isLoading = createMutation.isPending || linkMutation.isPending;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        {/* Mode Tabs */}
        <View style={styles.modeTabs}>
          <TouchableOpacity
            style={[styles.modeTab, mode === 'create' && styles.modeTabActive]}
            onPress={() => setMode('create')}
          >
            <MaterialIcons
              name="person-add"
              size={18}
              color={mode === 'create' ? colors.primary : colors.textMuted}
            />
            <Text
              style={[
                styles.modeTabText,
                mode === 'create' && styles.modeTabTextActive,
              ]}
            >
              Create New
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.modeTab, mode === 'link' && styles.modeTabActive]}
            onPress={() => setMode('link')}
          >
            <MaterialIcons
              name="link"
              size={18}
              color={mode === 'link' ? colors.primary : colors.textMuted}
            />
            <Text
              style={[
                styles.modeTabText,
                mode === 'link' && styles.modeTabTextActive,
              ]}
            >
              Link Existing
            </Text>
          </TouchableOpacity>
        </View>

        {/* Form */}
        <View style={styles.form}>
          {mode === 'create' ? (
            <>
              <Text style={styles.label}>Child's Full Name</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Sarah Johnson"
                placeholderTextColor={colors.textMuted}
                value={fullName}
                onChangeText={setFullName}
                autoCapitalize="words"
                autoFocus
              />
              <Text style={styles.hint}>
                Create a new student profile for your child. They can log in
                later with an invitation.
              </Text>
            </>
          ) : (
            <>
              <Text style={styles.label}>Child's Email</Text>
              <TextInput
                style={styles.input}
                placeholder="child@example.com"
                placeholderTextColor={colors.textMuted}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoFocus
              />
              <Text style={styles.hint}>
                Link an existing student account by their email address.
              </Text>
            </>
          )}

          <TouchableOpacity
            style={[styles.button, isLoading && styles.buttonDisabled]}
            onPress={handleSubmit}
            disabled={isLoading}
            activeOpacity={0.7}
          >
            <Text style={styles.buttonText}>
              {isLoading
                ? 'Please wait...'
                : mode === 'create'
                ? 'Create Child'
                : 'Link Child'}
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
  },
  modeTabs: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.xs,
    marginBottom: spacing.xl,
  },
  modeTab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.sm,
  },
  modeTabActive: {
    backgroundColor: '#E0F7F8',
  },
  modeTabText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    fontWeight: '500',
  },
  modeTabTextActive: {
    color: colors.primary,
    fontWeight: '600',
  },
  form: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  hint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: spacing.xl,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.lg,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
