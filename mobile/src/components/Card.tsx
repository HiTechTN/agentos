import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../theme';

type CardVariant = 'default' | 'elevated' | 'outlined';

interface CardProps {
  children: React.ReactNode;
  variant?: CardVariant;
  onPress?: () => void;
  style?: any;
}

export function Card({ children, variant = 'default', style }: CardProps) {
  const variantStyles = {
    default: {
      backgroundColor: Colors.light.surface,
      borderWidth: 0,
      shadowOpacity: 1,
      elevation: 2,
    },
    elevated: {
      backgroundColor: Colors.light.surface,
      borderWidth: 0,
      shadowOpacity: 1,
      elevation: 4,
      shadowRadius: 12,
    },
    outlined: {
      backgroundColor: Colors.light.surface,
      borderWidth: 1,
      borderColor: Colors.light.border,
      shadowOpacity: 0,
      elevation: 0,
    },
  };

  const v = variantStyles[variant];

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: v.backgroundColor,
          borderWidth: v.borderWidth,
          borderColor: (v as any).borderColor,
          elevation: v.elevation,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

export function CardRow({ children, style }: { children: React.ReactNode; style?: any }) {
  return <View style={[styles.row, style]}>{children}</View>;
}

export function CardSection({ icon, title, children }: { icon?: keyof typeof Ionicons.glyphMap; title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        {icon && <Ionicons name={icon} size={16} color={Colors.light.textSecondary} />}
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    padding: Spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    marginBottom: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  section: {
    marginBottom: Spacing.xl,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
