import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { messagesApi } from '../api/messages';
import { notificationsApi } from '../api/notifications';
import { LoginScreen } from '../screens/auth/LoginScreen';
import { ParentDashboardScreen } from '../screens/parent/ParentDashboardScreen';
import { ChildOverviewScreen } from '../screens/parent/ChildOverviewScreen';
import { CalendarScreen } from '../screens/parent/CalendarScreen';
import { MessagesListScreen } from '../screens/messages/MessagesListScreen';
import { ChatScreen } from '../screens/messages/ChatScreen';
import { NotificationsScreen } from '../screens/notifications/NotificationsScreen';
import { ProfileScreen } from '../screens/profile/ProfileScreen';
import { colors } from '../theme';

export type RootStackParamList = {
  Login: undefined;
  Main: undefined;
};

export type MainTabParamList = {
  Home: undefined;
  Calendar: undefined;
  Messages: undefined;
  Notifications: undefined;
  Profile: undefined;
};

export type HomeStackParamList = {
  Dashboard: undefined;
  ChildOverview: { studentId: number; name: string };
};

export type MessagesStackParamList = {
  ConversationsList: undefined;
  Chat: { conversationId: number; name: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();
const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const MsgStack = createNativeStackNavigator<MessagesStackParamList>();

function HomeStackScreen() {
  return (
    <HomeStack.Navigator>
      <HomeStack.Screen
        name="Dashboard"
        component={ParentDashboardScreen}
        options={{ headerShown: false }}
      />
      <HomeStack.Screen
        name="ChildOverview"
        component={ChildOverviewScreen}
        options={({ route }) => ({
          title: route.params.name,
          headerTintColor: colors.primary,
        })}
      />
    </HomeStack.Navigator>
  );
}

function MessagesStackScreen() {
  return (
    <MsgStack.Navigator>
      <MsgStack.Screen
        name="ConversationsList"
        component={MessagesListScreen}
        options={{ title: 'Messages', headerTintColor: colors.primary }}
      />
      <MsgStack.Screen
        name="Chat"
        component={ChatScreen}
        options={({ route }) => ({
          title: route.params.name,
          headerTintColor: colors.primary,
        })}
      />
    </MsgStack.Navigator>
  );
}

function MainTabs() {
  const { data: msgCount } = useQuery({
    queryKey: ['unreadMessages'],
    queryFn: messagesApi.getUnreadCount,
    refetchInterval: 30000, // poll every 30s
  });

  const { data: notifCount } = useQuery({
    queryKey: ['notifUnreadCount'],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30000,
  });

  const unreadMessages = msgCount?.total_unread || 0;
  const unreadNotifs = notifCount?.count || 0;

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const iconMap: Record<string, keyof typeof MaterialIcons.glyphMap> = {
            Home: 'home',
            Calendar: 'calendar-today',
            Messages: 'chat',
            Notifications: 'notifications',
            Profile: 'person',
          };
          return (
            <MaterialIcons
              name={iconMap[route.name]}
              size={size}
              color={color}
            />
          );
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        headerShown: false,
      })}
    >
      <Tab.Screen name="Home" component={HomeStackScreen} />
      <Tab.Screen
        name="Calendar"
        component={CalendarScreen}
        options={{ headerShown: true, headerTitle: 'Calendar', headerTintColor: colors.primary }}
      />
      <Tab.Screen
        name="Messages"
        component={MessagesStackScreen}
        options={{
          tabBarBadge: unreadMessages > 0 ? unreadMessages : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.error },
        }}
      />
      <Tab.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{
          headerShown: true,
          headerTitle: 'Notifications',
          headerTintColor: colors.primary,
          tabBarBadge: unreadNotifs > 0 ? unreadNotifs : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.error },
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ headerShown: true, headerTitle: 'Profile', headerTintColor: colors.primary }}
      />
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {token ? (
          <Stack.Screen name="Main" component={MainTabs} />
        ) : (
          <Stack.Screen name="Login" component={LoginScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
