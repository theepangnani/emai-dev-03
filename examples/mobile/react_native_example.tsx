/**
 * Example: React Native App Structure with Shared Code
 *
 * This shows how to structure a React Native app that shares code with your web app.
 */

// ==========================================
// 1. SHARED: shared/api/client.ts
// ==========================================
// This is EXACTLY THE SAME as your web app's API client!
// 70% CODE REUSE!

import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';  // Mobile storage

const API_BASE_URL = __DEV__
  ? 'http://localhost:8000/api/v1'  // Dev
  : 'https://www.classbridge.ca/api';  // Prod

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Add auth token
apiClient.interceptors.request.use(
  async (config) => {
    const token = await AsyncStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 (refresh token)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh token
        const refreshToken = await AsyncStorage.getItem('refresh_token');
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        // Save new token
        await AsyncStorage.setItem('access_token', data.access_token);

        // Retry original request
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - logout user
        await AsyncStorage.multiRemove(['access_token', 'refresh_token', 'user']);
        // Navigate to login (see example below)
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);


// ==========================================
// 2. SHARED: shared/api/endpoints/auth.ts
// ==========================================
// Can be shared 100% between web and mobile!

import { apiClient } from '../client';

export interface LoginRequest {
  username: string;  // email
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  roles: string[];
  is_active: boolean;
  google_connected: boolean;
  profile_picture_url?: string;
  created_at: string;
}

export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const { data } = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return data;
  },

  register: async (userData: any): Promise<User> => {
    const { data } = await apiClient.post('/auth/register', userData);
    return data;
  },

  refreshToken: async (refreshToken: string): Promise<LoginResponse> => {
    const { data } = await apiClient.post('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  getCurrentUser: async (): Promise<User> => {
    const { data } = await apiClient.get('/users/me');
    return data;
  },
};


// ==========================================
// 3. SHARED: shared/api/endpoints/courses.ts
// ==========================================
import { apiClient } from '../client';

export interface Course {
  id: number;
  name: string;
  description: string;
  teacher_id: number | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export const coursesApi = {
  list: async (skip = 0, limit = 20): Promise<PaginatedResponse<Course>> => {
    const { data } = await apiClient.get('/courses', {
      params: { skip, limit },
    });
    return data;
  },

  get: async (id: number): Promise<Course> => {
    const { data } = await apiClient.get(`/courses/${id}`);
    return data;
  },

  create: async (course: Partial<Course>): Promise<Course> => {
    const { data } = await apiClient.post('/courses', course);
    return data;
  },
};


// ==========================================
// 4. SHARED: shared/hooks/useAuth.ts
// ==========================================
// React Query hook - works on both web and mobile!

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi, LoginRequest, User } from '../api/endpoints/auth';

export const useAuth = () => {
  const queryClient = useQueryClient();

  // Get current user
  const { data: user, isLoading } = useQuery({
    queryKey: ['currentUser'],
    queryFn: authApi.getCurrentUser,
    retry: false,
    enabled: false,  // Only fetch when logged in
  });

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data) => {
      // Save tokens
      await AsyncStorage.setItem('access_token', data.access_token);
      await AsyncStorage.setItem('refresh_token', data.refresh_token);

      // Fetch user data
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    },
  });

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: async () => {
      // Clear tokens
      await AsyncStorage.multiRemove(['access_token', 'refresh_token', 'user']);

      // Clear cache
      queryClient.clear();
    },
  });

  return {
    user,
    isLoading,
    login: loginMutation.mutate,
    logout: logoutMutation.mutate,
    isAuthenticated: !!user,
  };
};


// ==========================================
// 5. MOBILE: screens/LoginScreen.tsx
// ==========================================
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useAuth } from '../../shared/hooks/useAuth';

export const LoginScreen = ({ navigation }: any) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, isLoading } = useAuth();

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please enter email and password');
      return;
    }

    try {
      await login({ username: email, password });
      // Navigation happens automatically via navigation listener
    } catch (error: any) {
      Alert.alert('Login Failed', error.response?.data?.detail || 'Invalid credentials');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>ClassBridge</Text>

      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />

      <TextInput
        style={styles.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity
        style={styles.button}
        onPress={handleLogin}
        disabled={isLoading}
      >
        {isLoading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Login</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity onPress={() => navigation.navigate('Register')}>
        <Text style={styles.link}>Don't have an account? Sign up</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 40,
    color: '#4f46e5',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#4f46e5',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  link: {
    color: '#4f46e5',
    textAlign: 'center',
    marginTop: 20,
  },
});


// ==========================================
// 6. MOBILE: screens/CoursesScreen.tsx
// ==========================================
import React from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { coursesApi, Course } from '../../shared/api/endpoints/courses';

export const CoursesScreen = ({ navigation }: any) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['courses'],
    queryFn: () => coursesApi.list(0, 20),
  });

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#4f46e5" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>Failed to load courses</Text>
      </View>
    );
  }

  const renderCourse = ({ item }: { item: Course }) => (
    <TouchableOpacity
      style={styles.courseCard}
      onPress={() => navigation.navigate('CourseDetail', { courseId: item.id })}
    >
      <Text style={styles.courseName}>{item.name}</Text>
      <Text style={styles.courseDescription} numberOfLines={2}>
        {item.description}
      </Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={data?.items || []}
        renderItem={renderCourse}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.list}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  list: {
    padding: 15,
  },
  courseCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  courseName: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  courseDescription: {
    fontSize: 14,
    color: '#666',
  },
  errorText: {
    color: 'red',
    fontSize: 16,
  },
});


// ==========================================
// 7. MOBILE: App.tsx (Navigation Setup)
// ==========================================
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoginScreen } from './screens/LoginScreen';
import { CoursesScreen } from './screens/CoursesScreen';

const Stack = createNativeStackNavigator();
const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="Login">
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="Courses"
            component={CoursesScreen}
            options={{ title: 'My Courses' }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </QueryClientProvider>
  );
}


// ==========================================
// 8. MOBILE: Push Notifications Setup
// ==========================================
// services/pushNotificationService.ts

import messaging from '@react-native-firebase/messaging';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiClient } from '../../shared/api/client';

export const pushNotificationService = {
  // Request permission and get FCM token
  async requestPermission() {
    const authStatus = await messaging().requestPermission();
    const enabled =
      authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
      authStatus === messaging.AuthorizationStatus.PROVISIONAL;

    if (enabled) {
      console.log('Push notification permission granted');
      await this.registerDevice();
    }
  },

  // Register device with backend
  async registerDevice() {
    try {
      const token = await messaging().getToken();
      const platform = Platform.OS === 'ios' ? 'ios' : 'android';

      // Send to backend
      await apiClient.post('/devices/register', {
        token,
        platform,
      });

      // Save locally
      await AsyncStorage.setItem('fcm_token', token);
    } catch (error) {
      console.error('Failed to register device:', error);
    }
  },

  // Handle foreground notifications
  onMessageReceived(callback: (message: any) => void) {
    return messaging().onMessage(callback);
  },

  // Handle notification tap when app is in background
  onNotificationOpenedApp(callback: (message: any) => void) {
    messaging().onNotificationOpenedApp(callback);
  },

  // Handle notification tap when app was closed
  async getInitialNotification() {
    const message = await messaging().getInitialNotification();
    return message;
  },

  // Unregister device (on logout)
  async unregisterDevice() {
    try {
      const token = await AsyncStorage.getItem('fcm_token');
      if (token) {
        await apiClient.delete('/devices/unregister', {
          data: { token },
        });
        await AsyncStorage.removeItem('fcm_token');
      }
    } catch (error) {
      console.error('Failed to unregister device:', error);
    }
  },
};

// Usage in App.tsx:
/*
useEffect(() => {
  pushNotificationService.requestPermission();

  // Handle foreground notifications
  const unsubscribe = pushNotificationService.onMessageReceived((message) => {
    Alert.alert(message.notification.title, message.notification.body);
  });

  return unsubscribe;
}, []);
*/


// ==========================================
// 9. PROJECT STRUCTURE
// ==========================================
/*
ClassBridge/
├── shared/                          # 100% SHARED CODE
│   ├── api/
│   │   ├── client.ts               # Axios instance (REUSE!)
│   │   ├── endpoints/
│   │   │   ├── auth.ts             # Auth endpoints (REUSE!)
│   │   │   ├── courses.ts          # Courses endpoints (REUSE!)
│   │   │   ├── assignments.ts      # Assignments endpoints (REUSE!)
│   │   │   └── messages.ts         # Messages endpoints (REUSE!)
│   ├── hooks/
│   │   ├── useAuth.ts              # Auth hook (REUSE!)
│   │   ├── useCourses.ts           # Courses hook (REUSE!)
│   │   └── useAssignments.ts       # Assignments hook (REUSE!)
│   ├── types/
│   │   └── index.ts                # TypeScript interfaces (REUSE!)
│   └── utils/
│       ├── validation.ts           # Validation helpers (REUSE!)
│       └── formatting.ts           # Date/text formatting (REUSE!)
│
├── mobile/                          # REACT NATIVE APP
│   ├── App.tsx
│   ├── screens/
│   │   ├── LoginScreen.tsx
│   │   ├── DashboardScreen.tsx
│   │   ├── CoursesScreen.tsx
│   │   ├── AssignmentsScreen.tsx
│   │   └── MessagesScreen.tsx
│   ├── components/
│   │   ├── CourseCard.tsx
│   │   ├── AssignmentCard.tsx
│   │   └── MessageBubble.tsx
│   ├── navigation/
│   │   └── AppNavigator.tsx
│   ├── services/
│   │   └── pushNotificationService.ts
│   ├── package.json
│   └── app.json
│
└── frontend/                        # EXISTING REACT WEB APP
    └── (keep as is)

*/


// ==========================================
// 10. PACKAGE.JSON for Mobile
// ==========================================
/*
{
  "name": "ClassBridgeMobile",
  "version": "1.0.0",
  "main": "expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "web": "expo start --web"
  },
  "dependencies": {
    "react": "18.2.0",
    "react-native": "0.73.0",
    "@react-navigation/native": "^6.1.0",
    "@react-navigation/native-stack": "^6.9.0",
    "@tanstack/react-query": "^5.0.0",  // SAME AS WEB!
    "axios": "^1.6.0",                   // SAME AS WEB!
    "@react-native-async-storage/async-storage": "^1.21.0",
    "@react-native-firebase/app": "^19.0.0",
    "@react-native-firebase/messaging": "^19.0.0",
    "react-native-vector-icons": "^10.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0"              // SAME AS WEB!
  }
}
*/
