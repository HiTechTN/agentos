import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../theme';

const FILE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  pdf: 'document-outline',
  doc: 'document-text-outline',
  docx: 'document-text-outline',
  xls: 'grid-outline',
  xlsx: 'grid-outline',
  ppt: 'easel-outline',
  pptx: 'easel-outline',
  md: 'code-slash-outline',
  txt: 'document-outline',
  csv: 'grid-outline',
  json: 'code-slash-outline',
  xml: 'code-slash-outline',
  yaml: 'code-slash-outline',
  yml: 'code-slash-outline',
};

const FILE_COLORS: Record<string, string> = {
  pdf: '#ef4444',
  doc: '#3b82f6',
  docx: '#3b82f6',
  xls: '#22c55e',
  xlsx: '#22c55e',
  ppt: '#f59e0b',
  pptx: '#f59e0b',
  md: '#6366f1',
  txt: '#64748b',
  csv: '#22c55e',
  json: '#f59e0b',
};

function getExtension(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FilePreviewProps {
  uri: string;
  filename: string;
  mimeType?: string;
  size?: number;
  variant?: 'chat' | 'list' | 'picker';
}

export function FilePreview({ uri, filename, mimeType, size, variant = 'list' }: FilePreviewProps) {
  const ext = getExtension(filename);
  const icon = FILE_ICONS[ext] || 'document-outline';
  const color = FILE_COLORS[ext] || Colors.light.textSecondary;

  if (mimeType?.startsWith('image/')) {
    return (
      <Image
        source={{ uri }}
        style={[styles.image, variant === 'chat' && styles.imageChat]}
        resizeMode="cover"
      />
    );
  }

  return (
    <View style={[styles.fileCard, variant === 'chat' && styles.fileCardChat]}>
      <View style={[styles.iconBox, { backgroundColor: color + '15' }]}>
        <Ionicons name={icon} size={variant === 'chat' ? 20 : 24} color={color} />
      </View>
      <View style={styles.fileInfo}>
        <Text style={[styles.filename, variant === 'chat' && styles.filenameChat]} numberOfLines={1}>
          {filename}
        </Text>
        {size ? (
          <Text style={styles.fileSize}>{formatFileSize(size)}</Text>
        ) : null}
      </View>
      {ext ? (
        <View style={[styles.extBadge, { backgroundColor: color + '15' }]}>
          <Text style={[styles.extText, { color }]}>{ext.toUpperCase()}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  image: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    marginTop: Spacing.sm,
  },
  imageChat: {
    width: 200,
    height: 150,
  },
  fileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 12,
    padding: Spacing.md,
    marginTop: Spacing.xs,
  },
  fileCardChat: {
    padding: Spacing.sm,
    gap: Spacing.sm,
  },
  iconBox: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fileInfo: {
    flex: 1,
  },
  filename: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    color: Colors.light.text,
  },
  filenameChat: {
    fontSize: FontSizes.xs,
  },
  fileSize: {
    fontSize: FontSizes.xs,
    color: Colors.light.textTertiary,
    marginTop: 2,
  },
  extBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  extText: {
    fontSize: 10,
    fontWeight: '700',
  },
});
