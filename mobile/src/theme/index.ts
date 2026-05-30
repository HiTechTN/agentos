export const Colors = {
  light: {
    primary: '#6366f1',
    primaryDark: '#4f46e5',
    background: '#f8fafc',
    surface: '#ffffff',
    surfaceVariant: '#f1f5f9',
    text: '#0f172a',
    textSecondary: '#64748b',
    textTertiary: '#94a3b8',
    border: '#e2e8f0',
    error: '#ef4444',
    success: '#22c55e',
    warning: '#f59e0b',
    info: '#3b82f6',
    tabBar: '#ffffff',
    tabBarBorder: '#e2e8f0',
    cardShadow: 'rgba(0, 0, 0, 0.05)',
  },
  dark: {
    primary: '#818cf8',
    primaryDark: '#6366f1',
    background: '#0f172a',
    surface: '#1e293b',
    surfaceVariant: '#334155',
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    textTertiary: '#64748b',
    border: '#334155',
    error: '#f87171',
    success: '#4ade80',
    warning: '#fbbf24',
    info: '#60a5fa',
    tabBar: '#1e293b',
    tabBarBorder: '#334155',
    cardShadow: 'rgba(0, 0, 0, 0.2)',
  },
};

export type ThemeColors = typeof Colors.light;

export const FontSizes = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 22,
  xxl: 28,
  title: 34,
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};
