import React from 'react';
import { render } from '@testing-library/react-native';
import { PlaceholderScreen } from '../../src/screens/common/PlaceholderScreen';

describe('PlaceholderScreen', () => {
  it('renders "Coming soon..." text', () => {
    const { getByText } = render(<PlaceholderScreen />);
    expect(getByText('Coming soon...')).toBeTruthy();
  });

  it('renders without crashing', () => {
    const { toJSON } = render(<PlaceholderScreen />);
    expect(toJSON()).toBeTruthy();
  });
});
