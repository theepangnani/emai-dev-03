import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { HeaderIcons } from '../components/HeaderIcons';
import { messagesApi } from '../api/messages';
import { LoginScreen } from '../screens/auth/LoginScreen';
import { ParentDashboardScreen } from '../screens/parent/ParentDashboardScreen';
import { ChildOverviewScreen } from '../screens/parent/ChildOverviewScreen';
import { MyKidsScreen } from '../screens/parent/MyKidsScreen';
import { AddChildScreen } from '../screens/parent/AddChildScreen';
import { CoursesScreen } from '../screens/parent/CoursesScreen';
import { ClassMaterialsScreen } from '../screens/parent/ClassMaterialsScreen';
import { QuizHistoryScreen } from '../screens/parent/QuizHistoryScreen';
import { TasksScreen } from '../screens/parent/TasksScreen';
import { HelpScreen } from '../screens/parent/HelpScreen';
import { CalendarScreen } from '../screens/parent/CalendarScreen';
import { MessagesListScreen } from '../screens/messages/MessagesListScreen';
import { ChatScreen } from '../screens/messages/ChatScreen';
import { NotificationsScreen } from '../screens/notifications/NotificationsScreen';
import { ProfileScreen } from '../screens/profile/ProfileScreen';
import { colors } from '../theme';

// --- Type Definitions ---

export type RootStackParamList = {
  Login: undefined;
  MainTabs: undefined;
  Calendar: undefined;
  Notifications: undefined;
  Profile: undefined;
};

export type MainTabParamList = {
  Home: undefined;
  MyKids: undefined;
  Task: undefined;
  Message: undefined;
  Help: undefined;
};

export type HomeStackParamList = {
  Dashboard: undefined;
  ChildOverview: { studentId: number; name: string };
};

export type MyKidsStackParamList = {
  MyKidsHome: undefined;
  ChildOverview: { studentId: number; name: string };
  Courses: undefined;
  ClassMaterials: undefined;
  QuizHistory: undefined;
  AddChild: undefined;
};

export type TaskStackParamList = {
  TaskList: undefined;
};

export type MessagesStackParamList = {
  ConversationsList: undefined;
  Chat: { conversationId: number; name: string };
};

export type HelpStackParamList = {
  HelpHome: undefined;
};

// --- Stack & Tab Navigators ---

const RootStack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();
const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const MyKidsNavStack = createNativeStackNavigator<MyKidsStackParamList>();
const TaskNavStack = createNativeStackNavigator<TaskStackParamList>();
const MsgStack = createNativeStackNavigator<MessagesStackParamList>();
const HelpNavStack = createNativeStackNavigator<HelpStackParamList>();

// --- Stack Screens ---

function HomeStackScreen() {
  return (
    <HomeStack.Navigator
      screenOptions={{
        headerRight: () => <HeaderIcons />,
      }}
    >
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

function MyKidsStackScreen() {
  return (
    <MyKidsNavStack.Navigator
      screenOptions={{
        headerRight: () => <HeaderIcons />,
        headerTintColor: colors.primary,
      }}
    >
      <MyKidsNavStack.Screen
        name="MyKidsHome"
        component={MyKidsScreen}
        options={{ title: 'My Kids' }}
      />
      <MyKidsNavStack.Screen
        name="ChildOverview"
        component={ChildOverviewScreen}
        options={({ route }) => ({ title: route.params.name })}
      />
      <MyKidsNavStack.Screen
        name="Courses"
        component={CoursesScreen}
        options={{ title: 'Courses' }}
      />
      <MyKidsNavStack.Screen
        name="ClassMaterials"
        component={ClassMaterialsScreen}
        options={{ title: 'Class Materials' }}
      />
      <MyKidsNavStack.Screen
        name="QuizHistory"
        component={QuizHistoryScreen}
        options={{ title: 'Quiz History' }}
      />
      <MyKidsNavStack.Screen
        name="AddChild"
        component={AddChildScreen}
        options={{ title: 'Add Child', presentation: 'modal' }}
      />
    </MyKidsNavStack.Navigator>
  );
}

function TaskStackScreen() {
  return (
    <TaskNavStack.Navigator
      screenOptions={{
        headerRight: () => <HeaderIcons />,
        headerTintColor: colors.primary,
      }}
    >
      <TaskNavStack.Screen
        name="TaskList"
        component={TasksScreen}
        options={{ title: 'Tasks' }}
      />
    </TaskNavStack.Navigator>
  );
}

function MessagesStackScreen() {
  return (
    <MsgStack.Navigator
      screenOptions={{
        headerRight: () => <HeaderIcons />,
        headerTintColor: colors.primary,
      }}
    >
      <MsgStack.Screen
        name="ConversationsList"
        component={MessagesListScreen}
        options={{ title: 'Messages' }}
      />
      <MsgStack.Screen
        name="Chat"
        component={ChatScreen}
        options={({ route }) => ({
          title: route.params.name,
        })}
      />
    </MsgStack.Navigator>
  );
}

function HelpStackScreen() {
  return (
    <HelpNavStack.Navigator
      screenOptions={{
        headerRight: () => <HeaderIcons />,
        headerTintColor: colors.primary,
      }}
    >
      <HelpNavStack.Screen
        name="HelpHome"
        component={HelpScreen}
        options={{ title: 'Help & FAQ' }}
      />
    </HelpNavStack.Navigator>
  );
}

// --- Main Tabs ---

function MainTabs() {
  const { data: msgCount } = useQuery({
    queryKey: ['unreadMessages'],
    queryFn: messagesApi.getUnreadCount,
    refetchInterval: 30000,
  });

  const unreadMessages = msgCount?.total_unread || 0;

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const iconMap: Record<string, keyof typeof MaterialIcons.glyphMap> = {
            Home: 'home',
            MyKids: 'people',
            Task: 'check-circle',
            Message: 'chat',
            Help: 'help',
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
        name="MyKids"
        component={MyKidsStackScreen}
        options={{ title: 'My Kids' }}
      />
      <Tab.Screen name="Task" component={TaskStackScreen} />
      <Tab.Screen
        name="Message"
        component={MessagesStackScreen}
        options={{
          tabBarBadge: unreadMessages > 0 ? unreadMessages : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.error },
        }}
      />
      <Tab.Screen name="Help" component={HelpStackScreen} />
    </Tab.Navigator>
  );
}

// --- Root Navigator ---

export function AppNavigator() {
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  return (
    <NavigationContainer>
      <RootStack.Navigator screenOptions={{ headerShown: false }}>
        {token ? (
          <>
            <RootStack.Screen name="MainTabs" component={MainTabs} />
            <RootStack.Screen
              name="Calendar"
              component={CalendarScreen}
              options={{
                headerShown: true,
                title: 'Calendar',
                headerTintColor: colors.primary,
                presentation: 'card',
              }}
            />
            <RootStack.Screen
              name="Notifications"
              component={NotificationsScreen}
              options={{
                headerShown: true,
                title: 'Notifications',
                headerTintColor: colors.primary,
                presentation: 'card',
              }}
            />
            <RootStack.Screen
              name="Profile"
              component={ProfileScreen}
              options={{
                headerShown: true,
                title: 'Profile',
                headerTintColor: colors.primary,
                presentation: 'card',
              }}
            />
          </>
        ) : (
          <RootStack.Screen name="Login" component={LoginScreen} />
        )}
      </RootStack.Navigator>
    </NavigationContainer>
  );
}
