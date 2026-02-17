/* global jest */
const React = require('react');

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  setItem: jest.fn(() => Promise.resolve()),
  getItem: jest.fn(() => Promise.resolve(null)),
  removeItem: jest.fn(() => Promise.resolve()),
  multiRemove: jest.fn(() => Promise.resolve()),
}));

// Mock @expo/vector-icons — render icon name as text for assertions
jest.mock('@expo/vector-icons', () => {
  const mockReact = require('react');
  const RN = require('react-native');
  const MaterialIcons = (props: Record<string, unknown>) =>
    mockReact.createElement(RN.Text, { testID: `icon-${props.name}` }, props.name as string);
  MaterialIcons.glyphMap = {};
  return { MaterialIcons };
});

// Mock react-native-safe-area-context
jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }: { children: React.ReactNode }) => children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));

// Mock react-native-screens
jest.mock('react-native-screens', () => ({
  enableScreens: jest.fn(),
}));

// Mock @react-navigation/native
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();

jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({
    navigate: mockNavigate,
    goBack: mockGoBack,
  }),
  useRoute: () => ({
    params: {},
  }),
  NavigationContainer: ({ children }: { children: React.ReactNode }) => children,
}));

// Fix window.dispatchEvent for React 19 test-renderer
if (typeof window !== 'undefined' && !window.dispatchEvent) {
  window.dispatchEvent = jest.fn();
}

// Silence console.warn/error noise from React test environment
const originalWarn = console.warn;
const originalError = console.error;
console.warn = (...args: unknown[]) => {
  const msg = typeof args[0] === 'string' ? args[0] : '';
  if (
    msg.includes('act(') ||
    msg.includes('An update to') ||
    msg.includes('React.createElement') ||
    msg.includes('not wrapped in act')
  ) return;
  originalWarn(...args);
};
console.error = (...args: unknown[]) => {
  const msg = typeof args[0] === 'string' ? args[0] : '';
  if (
    msg.includes('act(') ||
    msg.includes('An update to') ||
    msg.includes('not wrapped in act') ||
    msg.includes('Warning:')
  ) return;
  originalError(...args);
};

export { mockNavigate, mockGoBack };
