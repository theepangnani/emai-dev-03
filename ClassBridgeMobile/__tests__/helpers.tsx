import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react-native';

// Create a fresh QueryClient for each test
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

// Wrapper that provides QueryClient + any other providers
export function renderWithProviders(
  ui: React.ReactElement,
  {
    queryClient = createTestQueryClient(),
  }: { queryClient?: QueryClient } = {},
) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper }),
    queryClient,
  };
}

// Mock user for tests
export const mockUser = {
  id: 1,
  email: 'parent@test.com',
  full_name: 'Jane Doe',
  role: 'parent',
  roles: ['parent'],
  is_active: true,
  google_connected: true,
};

// Mock auth context value
export const mockAuthContext = {
  user: mockUser,
  token: 'mock-token',
  isLoading: false,
  login: jest.fn(),
  logout: jest.fn(),
};
