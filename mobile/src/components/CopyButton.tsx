import { useState, useCallback } from 'react';
import { TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { Colors } from '../theme';

interface CopyButtonProps {
  text: string;
  size?: number;
}

export function CopyButton({ text, size = 16 }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <TouchableOpacity
      style={styles.button}
      onPress={handleCopy}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
    >
      <Ionicons
        name={copied ? 'checkmark' : 'copy-outline'}
        size={size}
        color={copied ? Colors.light.success : Colors.light.textTertiary}
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    padding: 4,
  },
});
