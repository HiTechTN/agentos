import { useState, useEffect } from 'react';
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
import {
  getBaseUrl,
  healthCheck,
  setOfflineEnqueue,
  setOnlineStatus,
} from '../../src/api/client';
import { useNotifications } from '../../src/services/notifications';
import { useOffline } from '../../src/services/offline';

export default function SettingsScreen() {
  const { serverUrl, updateServerUrl, logout } = useAuth();
  const { expoPushToken, notificationsEnabled, setNotificationsEnabled } = useNotifications();
  const { isOnline, queueLength, enqueue, flush } = useOffline();
  const [url, setUrl] = useState(serverUrl || getBaseUrl());
  const [testing, setTesting] = useState(false);
  const [useSystemTheme, setUseSystemTheme] = useState(true);

  useEffect(() => {
    setOfflineEnqueue(enqueue);
  }, [enqueue]);

  useEffect(() => {
    setOnlineStatus(isOnline);
  }, [isOnline]);

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
          placeholder="http://192.168.0.100:8081"
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
        <Text style={styles.sectionTitle}>Notifications</Text>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Ionicons name="notifications-outline" size={20} color={Colors.light.textSecondary} />
            <Text style={styles.settingText}>Push Notifications</Text>
          </View>
          <Switch
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            trackColor={{
              false: Colors.light.border,
              true: Colors.light.primary + '60',
            }}
            thumbColor={notificationsEnabled ? Colors.light.primary : Colors.light.textTertiary}
          />
        </View>

        {expoPushToken && (
          <View style={styles.tokenCard}>
            <Text style={styles.tokenLabel}>Push Token</Text>
            <Text style={styles.tokenValue} numberOfLines={1} selectable>
              {expoPushToken}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Offline</Text>

        <View style={styles.settingRow}>
          <View style={styles.settingInfo}>
            <Ionicons
              name={isOnline ? 'wifi-outline' : 'cloud-offline-outline'}
              size={20}
              color={isOnline ? Colors.light.success : Colors.light.error}
            />
            <Text style={styles.settingText}>
              {isOnline ? 'Connected' : 'Offline'}
            </Text>
          </View>
          {!isOnline && (
            <View style={styles.offlineBadge}>
              <Text style={styles.offlineBadgeText}>{queueLength} queued</Text>
            </View>
          )}
        </View>

        {queueLength > 0 && isOnline && (
          <TouchableOpacity style={styles.flushButton} onPress={flush}>
            <Ionicons name="sync-outline" size={18} color="#fff" />
            <Text style={styles.flushButtonText}>
              Sync {queueLength} queued request{queueLength > 1 ? 's' : ''}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>

        <View style={styles.aboutCard}>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>App</Text>
            <Text style={styles.aboutValue}>AgentOS v7.2.2</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Version</Text>
            <Text style={styles.aboutValue}>7.2.2</Text>
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
  tokenCard: {
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 8,
    padding: Spacing.md,
    marginTop: Spacing.sm,
  },
  tokenLabel: {
    fontSize: FontSizes.xs,
    color: Colors.light.textTertiary,
    marginBottom: 4,
  },
  tokenValue: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  offlineBadge: {
    backgroundColor: Colors.light.warning + '30',
    borderRadius: 8,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  offlineBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    color: Colors.light.warning,
  },
  flushButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.light.primary,
    borderRadius: 12,
    padding: Spacing.md,
    marginTop: Spacing.sm,
  },
  flushButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#fff',
  },
});
