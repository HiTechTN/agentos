import { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  ScrollView,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { FilePreview } from '../../src/components';
import {
  runWorkflow,
  WorkflowResult,
  AttachmentData,
} from '../../src/api/client';

interface PickedAttachment {
  uri: string;
  filename: string;
  mimeType: string;
  size?: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  attachments?: { uri: string; filename: string; mimeType: string }[];
  timestamp: Date;
}

const ALLOWED_EXTENSIONS = [
  'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
  'md', 'txt', 'csv', 'json', 'xml', 'yaml', 'yml',
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
];

const SUGGESTIONS = [
  { text: 'Create a simple REST API in Python', icon: 'code-slash' as const },
  { text: 'Write a product description for a smart water bottle', icon: 'document-text' as const },
  { text: 'Plan a marketing campaign for a new app launch', icon: 'megaphone' as const },
  { text: 'Create an e-commerce product listing', icon: 'cart' as const },
  { text: 'Analyze this PDF document', icon: 'document-attach' as const },
];

export default function ChatScreen() {
  const params = useLocalSearchParams<{ suggest?: string; agent?: string }>();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hello! I am AgentOS. Send me a prompt, attach documents, or both — I can analyze PDFs, Word docs, spreadsheets, Markdown, and more.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pickedAttachments, setPickedAttachments] = useState<PickedAttachment[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    if (params.suggest === 'plan') {
      setInput('Create a plan to ');
      flatListRef.current?.scrollToEnd({ animated: false });
    }
    if (params.agent) {
      setInput(`Ask ${params.agent} to `);
    }
  }, [params.suggest, params.agent]);

  const pickImages = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      quality: 0.7,
    });
    if (result.canceled) return;
    const newAttachments: PickedAttachment[] = result.assets.map((a) => ({
      uri: a.uri,
      filename: a.fileName || `image_${Date.now()}.jpg`,
      mimeType: a.mimeType || 'image/jpeg',
      size: a.fileSize || undefined,
    }));
    setPickedAttachments((prev) => [...prev, ...newAttachments]);
    setShowSuggestions(false);
  };

  const pickDocuments = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'application/vnd.ms-powerpoint',
          'application/vnd.openxmlformats-officedocument.presentationml.presentation',
          'text/plain',
          'text/csv',
          'text/markdown',
          'application/json',
          'application/xml',
          'image/*',
        ],
        multiple: true,
        copyToCacheDirectory: true,
      });

      if (result.canceled) return;
      const assets = 'assets' in result ? result.assets : [result];
      const newAttachments: PickedAttachment[] = assets.map((a: any) => ({
        uri: a.uri || a.file?.uri || '',
        filename: a.name || a.file?.name || `doc_${Date.now()}`,
        mimeType: a.mimeType || a.file?.mimeType || 'application/octet-stream',
        size: a.size || a.file?.size || undefined,
      })).filter((a: PickedAttachment) => a.uri);

      setPickedAttachments((prev) => [...prev, ...newAttachments]);
      setShowSuggestions(false);
    } catch (e: any) {
      if (e?.message !== 'User canceled') {
        Alert.alert('Error', 'Could not pick document');
      }
    }
  };

  const takePhoto = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Permission required', 'Camera access is needed to take photos');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;
    const asset = result.assets[0];
    setPickedAttachments((prev) => [
      ...prev,
      {
        uri: asset.uri,
        filename: asset.fileName || `photo_${Date.now()}.jpg`,
        mimeType: asset.mimeType || 'image/jpeg',
        size: asset.fileSize || undefined,
      },
    ]);
    setShowSuggestions(false);
  };

  const removeAttachment = (index: number) => {
    setPickedAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const pickFile = () => {
    Alert.alert('Add to message', 'What would you like to attach?', [
      { text: 'Camera', onPress: takePhoto },
      { text: 'Gallery', onPress: pickImages },
      { text: 'Document (PDF, DOCX, MD...)', onPress: pickDocuments },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if ((!trimmed && pickedAttachments.length === 0) || loading) return;

    const attachmentData: AttachmentData[] = [];
    for (const att of pickedAttachments) {
      try {
        const b64 = await FileSystem.readAsStringAsync(att.uri, {
          encoding: FileSystem.EncodingType.Base64,
        });
        attachmentData.push({
          filename: att.filename,
          mime_type: att.mimeType,
          data_base64: b64,
        });
      } catch {
        // skip failed reads
      }
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: trimmed,
      attachments: pickedAttachments.map((a) => ({ uri: a.uri, filename: a.filename, mimeType: a.mimeType })),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setPickedAttachments([]);
    setShowSuggestions(false);
    setLoading(true);

    try {
      const prompt = trimmed || `Analyze the attached ${attachmentData.length > 1 ? 'files' : 'file'}`;
      const result: WorkflowResult = await runWorkflow(prompt, 'default', attachmentData);

      const responseText =
        result.status === 'failed'
          ? `Error: ${result.error?.message || 'Unknown error'}`
          : result.result || JSON.stringify(result, null, 2);

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: responseText,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        text: `Connection error: ${e?.message || 'Could not reach server'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = (text: string) => {
    setInput(text);
    setShowSuggestions(false);
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.messageRow, isUser ? styles.userRow : styles.assistantRow]}>
        {!isUser && (
          <View style={styles.avatar}>
            <Ionicons name="sparkles" size={16} color={Colors.light.primary} />
          </View>
        )}
        <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
          {item.text ? (
            <Text selectable style={[styles.messageText, isUser && styles.userText]}>{item.text}</Text>
          ) : null}
          {item.attachments?.map((att, i) => (
            <View key={i} style={styles.attachPreview}>
              <FilePreview
                uri={att.uri}
                filename={att.filename}
                mimeType={att.mimeType}
                variant="chat"
              />
            </View>
          ))}
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() =>
          flatListRef.current?.scrollToEnd({ animated: true })
        }
        ListFooterComponent={
          showSuggestions && messages.length === 1 ? (
            <View style={styles.suggestions}>
              <Text style={styles.suggestionsTitle}>Try asking:</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {SUGGESTIONS.map((s, i) => (
                  <TouchableOpacity
                    key={i}
                    style={styles.suggestionChip}
                    onPress={() => handleSuggestion(s.text)}
                    activeOpacity={0.7}
                  >
                    <Ionicons name={s.icon} size={16} color={Colors.light.primary} />
                    <Text style={styles.suggestionText}>{s.text}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          ) : null
        }
      />

      {pickedAttachments.length > 0 && (
        <View style={styles.attachmentBar}>
          {pickedAttachments.map((att, i) => (
            <View key={i} style={styles.attachmentChip}>
              <FilePreview
                uri={att.uri}
                filename={att.filename}
                mimeType={att.mimeType}
                size={att.size}
                variant="chat"
              />
              <TouchableOpacity
                style={styles.removeButton}
                onPress={() => removeAttachment(i)}
              >
                <Ionicons name="close-circle" size={20} color={Colors.light.error} />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}

      <View style={styles.inputBar}>
        <TouchableOpacity style={styles.attachButton} onPress={pickFile}>
          <Ionicons name="add-circle" size={26} color={Colors.light.textSecondary} />
        </TouchableOpacity>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={
            pickedAttachments.length > 0
              ? 'Optional prompt for the attached files...'
              : 'Type a prompt or attach a document...'
          }
          placeholderTextColor={Colors.light.textTertiary}
          multiline
          maxLength={2000}
          editable={!loading}
        />
        <TouchableOpacity
          style={[
            styles.sendButton,
            (!input.trim() && pickedAttachments.length === 0) || loading
              ? styles.sendButtonDisabled
              : undefined,
          ]}
          onPress={sendMessage}
          disabled={(!input.trim() && pickedAttachments.length === 0) || loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Ionicons name="arrow-up" size={22} color="#fff" />
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  messageList: {
    padding: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  messageRow: {
    marginBottom: Spacing.md,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: Spacing.sm,
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  assistantRow: {
    justifyContent: 'flex-start',
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bubble: {
    maxWidth: '78%',
    borderRadius: 18,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  userBubble: {
    backgroundColor: Colors.light.primary,
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: Colors.light.surface,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  messageText: {
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    lineHeight: 20,
  },
  userText: {
    color: '#fff',
  },
  attachPreview: {
    marginTop: Spacing.sm,
  },
  suggestions: {
    marginTop: Spacing.lg,
    gap: Spacing.sm,
  },
  suggestionsTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.textSecondary,
  },
  suggestionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginRight: Spacing.sm,
  },
  suggestionText: {
    fontSize: FontSizes.xs,
    color: Colors.light.text,
  },
  attachmentBar: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.light.surfaceVariant,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
  },
  attachmentChip: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  removeButton: {
    marginLeft: Spacing.sm,
    padding: 4,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.light.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
    gap: 8,
    paddingBottom: Platform.OS === 'ios' ? 24 : Spacing.sm,
  },
  attachButton: {
    padding: 6,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: Colors.light.primary,
    borderRadius: 22,
    width: 42,
    height: 42,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
});
