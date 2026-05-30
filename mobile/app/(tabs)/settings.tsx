import { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Switch,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { useAuth } from '../../src/auth/AuthContext';
import { getBaseUrl, healthCheck } from '../../src/api/client';

export default function SettingsScreen() {
  const { serverUrl, updateServerUrl, logout } = useAuth();
  const [url, setUrl] = useState(serverUrl || getBaseUrl());
  const [testing, setTesting] = useState(false);
  const [useSystemTheme, setUseSystemTheme] = useState(true);

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      await updateServerUrl(url);
      const health = await healthCheck();
      Alert.alert(
        'Connection OK',
        `Version: ${health.version || 'unknown'}\nAPI: ${health.api}\nDB: ${health.database || 'N/A'}\nRedis: ${health.redis || 'N/A'}`,
      );
    } catch (e: any) {
      Alert.alert('Connection Failed', e?.message || 'Could not reach server');
    } finally {
      setTesting(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Disconnect', 'Are you sure you want to disconnect?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Disconnect', style: 'destructive', onPress: () => logout() },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server Connection</Text>

        <Text style={styles.label}>Server URL</Text>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          placeholder="http://your-server:8003"
          placeholderTextColor={Colors.light.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />

        <TouchableOpacity
          style={[styles.button, styles.primaryButton, testing && styles.buttonDisabled]}
          onPress={handleTestConnection}
          disabled={testing}
        >
          <Ionicons name="flash-outline" size={18} color="#fff" />
          <Text style={styles.buttonText}>
            {testing ? 'Testing...' : 'Test & Apply'}
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Preferences</Text>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Ionicons name="color-palette-outline" size={20} color={Colors.light.textSecondary} />
            <Text style={styles.settingText}>Use System Theme</Text>
          </View>
          <Switch
            value={useSystemTheme}
            onValueChange={setUseSystemTheme}
            trackColor={{
              false: Colors.light.border,
              true: Colors.light.primary + '60',
            }}
            thumbColor={useSystemTheme ? Colors.light.primary : Colors.light.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>

        <View style={styles.aboutCard}>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>App</Text>
            <Text style={styles.aboutValue}>AgentOS Mobile</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Version</Text>
            <Text style={styles.aboutValue}>1.0.0</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Platform</Text>
            <Text style={styles.aboutValue}>{Platform.OS}</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Server</Text>
            <Text style={styles.aboutValue} numberOfLines={1}>
              {serverUrl}
            </Text>
          </View>
        </View>
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={20} color={Colors.light.error} />
        <Text style={styles.logoutText}>Disconnect</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  content: {
    padding: Spacing.lg,
    paddingBottom: 48,
  },
  section: {
    marginBottom: Spacing.xxl,
  },
  sectionTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: Spacing.md,
  },
  label: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    color: Colors.light.text,
    marginBottom: Spacing.xs,
  },
  input: {
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: FontSizes.md,
    color: Colors.light.text,
    marginBottom: Spacing.md,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
  },
  primaryButton: {
    backgroundColor: Colors.light.primary,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingText: {
    fontSize: FontSizes.md,
    color: Colors.light.text,
  },
  aboutCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
  },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
  },
  aboutLabel: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
  },
  aboutValue: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    color: Colors.light.text,
    maxWidth: '60%',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.light.error + '30',
  },
  logoutText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: Colors.light.error,
  },
});
