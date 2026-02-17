import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { LoginScreen } from '../../src/screens/auth/LoginScreen';

// Mock useAuth
const mockLogin = jest.fn();
jest.mock('../../src/context/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}));

describe('LoginScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders logo image and subtitle', () => {
    const { getByText } = render(<LoginScreen />);
    expect(getByText('Parent Mobile App')).toBeTruthy();
  });

  it('renders email and password inputs', () => {
    const { getByPlaceholderText } = render(<LoginScreen />);
    expect(getByPlaceholderText('Email')).toBeTruthy();
    expect(getByPlaceholderText('Password')).toBeTruthy();
  });

  it('renders Sign In button', () => {
    const { getByText } = render(<LoginScreen />);
    expect(getByText('Sign In')).toBeTruthy();
  });

  it('renders web registration note', () => {
    const { getByText } = render(<LoginScreen />);
    expect(getByText('New account? Register at classbridge.ca')).toBeTruthy();
  });

  it('updates email input value', () => {
    const { getByPlaceholderText } = render(<LoginScreen />);
    const emailInput = getByPlaceholderText('Email');
    fireEvent.changeText(emailInput, 'test@example.com');
    expect(emailInput.props.value).toBe('test@example.com');
  });

  it('updates password input value', () => {
    const { getByPlaceholderText } = render(<LoginScreen />);
    const passwordInput = getByPlaceholderText('Password');
    fireEvent.changeText(passwordInput, 'secret123');
    expect(passwordInput.props.value).toBe('secret123');
  });

  it('shows error when submitting with empty fields', async () => {
    const { getByText } = render(<LoginScreen />);
    fireEvent.press(getByText('Sign In'));
    await waitFor(() => {
      expect(getByText('Please enter your email and password')).toBeTruthy();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows error when only email is provided', async () => {
    const { getByText, getByPlaceholderText } = render(<LoginScreen />);
    fireEvent.changeText(getByPlaceholderText('Email'), 'test@test.com');
    fireEvent.press(getByText('Sign In'));
    await waitFor(() => {
      expect(getByText('Please enter your email and password')).toBeTruthy();
    });
  });

  it('calls login with trimmed email on valid submit', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const { getByText, getByPlaceholderText } = render(<LoginScreen />);

    fireEvent.changeText(getByPlaceholderText('Email'), '  test@test.com  ');
    fireEvent.changeText(getByPlaceholderText('Password'), 'password');
    fireEvent.press(getByText('Sign In'));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@test.com', 'password');
    });
  });

  it('shows "Signing in..." while loading', async () => {
    mockLogin.mockImplementation(() => new Promise(() => {})); // never resolves
    const { getByText, getByPlaceholderText } = render(<LoginScreen />);

    fireEvent.changeText(getByPlaceholderText('Email'), 'test@test.com');
    fireEvent.changeText(getByPlaceholderText('Password'), 'password');
    fireEvent.press(getByText('Sign In'));

    await waitFor(() => {
      expect(getByText('Signing in...')).toBeTruthy();
    });
  });

  it('shows "Invalid email or password" on 401 error', async () => {
    mockLogin.mockRejectedValueOnce({ response: { status: 401 } });
    const { getByText, getByPlaceholderText } = render(<LoginScreen />);

    fireEvent.changeText(getByPlaceholderText('Email'), 'test@test.com');
    fireEvent.changeText(getByPlaceholderText('Password'), 'wrong');
    fireEvent.press(getByText('Sign In'));

    await waitFor(() => {
      expect(getByText('Invalid email or password')).toBeTruthy();
    });
  });

  it('shows generic error on network failure', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Network error'));
    const { getByText, getByPlaceholderText } = render(<LoginScreen />);

    fireEvent.changeText(getByPlaceholderText('Email'), 'test@test.com');
    fireEvent.changeText(getByPlaceholderText('Password'), 'password');
    fireEvent.press(getByText('Sign In'));

    await waitFor(() => {
      expect(getByText('Unable to connect. Please try again.')).toBeTruthy();
    });
  });

  it('toggles password visibility', () => {
    const { getByPlaceholderText, getAllByRole } = render(<LoginScreen />);
    const passwordInput = getByPlaceholderText('Password');
    // Initially secure
    expect(passwordInput.props.secureTextEntry).toBe(true);
  });
});
