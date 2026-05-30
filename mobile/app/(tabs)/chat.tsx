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
  Image,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import {
  runWorkflow,
  WorkflowResult,
  AttachmentData,
} from '../../src/api/client';

interface PickedAttachment {
  uri: string;
  filename: string;
  mimeType: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  attachments?: { uri: string; filename: string }[];
  timestamp: Date;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hello! I am AgentOS. Send me a prompt and I will execute it using my agents.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pickedAttachments, setPickedAttachments] = useState<PickedAttachment[]>([]);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    ImagePicker.requestCameraPermissionsAsync();
    ImagePicker.requestMediaLibraryPermissionsAsync();
  }, []);

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images', 'videos'],
      allowsMultipleSelection: true,
      quality: 0.7,
    });
    if (result.canceled) return;
    const newAttachments: PickedAttachment[] = result.assets.map((a) => ({
      uri: a.uri,
      filename: a.fileName || `attachment_${Date.now()}`,
      mimeType: a.mimeType || 'image/jpeg',
    }));
    setPickedAttachments((prev) => [...prev, ...newAttachments]);
  };

  const takePhoto = async () => {
    const result = await ImagePicker.launchCameraAsync({
      quality: 0.7,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    setPickedAttachments((prev) => [
      ...prev,
      {
        uri: asset.uri,
        filename: asset.fileName || `photo_${Date.now()}.jpg`,
        mimeType: asset.mimeType || 'image/jpeg',
      },
    ]);
  };

  const removeAttachment = (index: number) => {
    setPickedAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const pickFile = () => {
    Alert.alert('Add Attachment', 'Choose an option', [
      { text: 'Photo Library', onPress: pickImage },
      { text: 'Take Photo', onPress: takePhoto },
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
      attachments: pickedAttachments.map((a) => ({ uri: a.uri, filename: a.filename })),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setPickedAttachments([]);
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

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.messageRow, isUser ? styles.userRow : styles.assistantRow]}>
        <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
          {item.text ? (
            <Text style={[styles.messageText, isUser && styles.userText]}>
              {item.text}
            </Text>
          ) : null}
          {item.attachments?.map((att, i) => (
            <Image key={i} source={{ uri: att.uri }} style={styles.attachedImage} />
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
      />

      {pickedAttachments.length > 0 && (
        <View style={styles.attachmentPreview}>
          {pickedAttachments.map((att, i) => (
            <View key={i} style={styles.attachmentChip}>
              <Image source={{ uri: att.uri }} style={styles.thumb} />
              <Text style={styles.thumbFilename} numberOfLines={1}>
                {att.filename}
              </Text>
              <TouchableOpacity onPress={() => removeAttachment(i)}>
                <Ionicons name="close-circle" size={18} color={Colors.light.error} />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}

      <View style={styles.inputBar}>
        <TouchableOpacity style={styles.attachButton} onPress={pickFile}>
          <Ionicons name="attach" size={22} color={Colors.light.textSecondary} />
        </TouchableOpacity>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={
            pickedAttachments.length > 0
              ? 'Optional prompt for the attachment...'
              : 'Type a prompt...'
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
            <Ionicons name="send" size={20} color="#fff" />
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
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  assistantRow: {
    justifyContent: 'flex-start',
  },
  bubble: {
    maxWidth: '80%',
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
  attachedImage: {
    width: 200,
    height: 150,
    borderRadius: 8,
    marginTop: 6,
    resizeMode: 'cover',
  },
  attachmentPreview: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.light.surfaceVariant,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
  },
  attachmentChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.light.surface,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  thumb: {
    width: 28,
    height: 28,
    borderRadius: 4,
  },
  thumbFilename: {
    fontSize: FontSizes.xs,
    color: Colors.light.text,
    maxWidth: 80,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.light.surface,
    borderTopWidth: 1,
    borderTopColor: Colors.light.border,
    gap: 6,
  },
  attachButton: {
    padding: 8,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: Colors.light.primary,
    borderRadius: 24,
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    opacity: 0.5,
  },
});
