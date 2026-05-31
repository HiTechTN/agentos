import { View, Text, StyleSheet } from 'react-native';
import { Colors, FontSizes } from '../theme';

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
}

export function Badge({ label, variant = 'neutral', size = 'sm' }: BadgeProps) {
  const colors = {
    success: { bg: Colors.light.successLight, text: Colors.light.success, dot: Colors.light.success },
    warning: { bg: Colors.light.warningLight, text: Colors.light.warning, dot: Colors.light.warning },
    error: { bg: Colors.light.errorLight, text: Colors.light.error, dot: Colors.light.error },
    info: { bg: Colors.light.infoLight, text: Colors.light.info, dot: Colors.light.info },
    neutral: { bg: Colors.light.surfaceVariant, text: Colors.light.textSecondary, dot: Colors.light.textTertiary },
  };

  const c = colors[variant];
  const isSmall = size === 'sm';

  return (
    <View style={[styles.badge, { backgroundColor: c.bg }, isSmall && styles.badgeSmall]}>
      <View style={[styles.dot, { backgroundColor: c.dot }, isSmall && styles.dotSmall]} />
      <Text style={[styles.text, { color: c.text }, isSmall && styles.textSmall]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  badgeSmall: {
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  dotSmall: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
  },
  text: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  textSmall: {
    fontSize: 11,
  },
});
