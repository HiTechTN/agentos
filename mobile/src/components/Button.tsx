import { TouchableOpacity, Text, ActivityIndicator, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../theme';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  loading?: boolean;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

export function Button({
  title, onPress, variant = 'primary', loading, disabled, icon, size = 'md', fullWidth,
}: ButtonProps) {
  const isDisabled = disabled || loading;

  const variantStyles = {
    primary: { bg: Colors.light.primary, text: '#fff', border: Colors.light.primary },
    secondary: { bg: Colors.light.surfaceVariant, text: Colors.light.text, border: Colors.light.border },
    outline: { bg: 'transparent', text: Colors.light.primary, border: Colors.light.primary },
    ghost: { bg: 'transparent', text: Colors.light.textSecondary, border: 'transparent' },
    danger: { bg: Colors.light.error, text: '#fff', border: Colors.light.error },
  };

  const sizeStyles = {
    sm: { py: 10, px: 14, fs: FontSizes.xs, iconSize: 16 },
    md: { py: 14, px: 20, fs: FontSizes.sm, iconSize: 18 },
    lg: { py: 16, px: 24, fs: FontSizes.md, iconSize: 20 },
  };

  const v = variantStyles[variant];
  const s = sizeStyles[size];

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
      style={[
        styles.base,
        {
          backgroundColor: v.bg,
          borderColor: v.border,
          paddingVertical: s.py,
          paddingHorizontal: s.px,
          opacity: isDisabled ? 0.5 : 1,
        },
        fullWidth && styles.fullWidth,
      ]}
    >
      <View style={styles.content}>
        {loading ? (
          <ActivityIndicator size="small" color={v.text} />
        ) : (
          <>
            {icon && <Ionicons name={icon} size={s.iconSize} color={v.text} />}
            <Text style={[styles.text, { color: v.text, fontSize: s.fs }]}>{title}</Text>
          </>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  fullWidth: { width: '100%' },
  content: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  text: { fontWeight: '600' },
});
