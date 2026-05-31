import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Animated,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../src/theme';
import { useAuth } from '../src/auth/AuthContext';
import { healthCheck } from '../src/api/client';

export default function LoginScreen() {
  const { serverUrl, updateServerUrl, login } = useAuth();
  const [url, setUrl] = useState(serverUrl || '');
  const [connecting, setConnecting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleConnect = async () => {
    const targetUrl = url.trim() || (serverUrl || '').trim() || 'http://192.168.0.100:8004';
    setUrl(targetUrl);
    setConnecting(true);
    try {
      await updateServerUrl(targetUrl);
      const health = await healthCheck();
      if (health.api !== 'ok') {
        Alert.alert('Connection Error', 'Server is not responding');
        setConnecting(false);
        return;
      }
      await login('mobile');
      router.replace('/(tabs)/dashboard');
    } catch (e: any) {
      Alert.alert('Connection Error', e?.message || 'Could not connect to server');
    } finally {
      setConnecting(false);
    }
  };

  const handleSocialLogin = async (provider: string) => {
    const targetUrl = url.trim() || serverUrl || 'http://192.168.0.100:8004';
    if (!url.trim()) setUrl(targetUrl);
    setConnecting(true);
    try {
      await updateServerUrl(targetUrl);
      const resp = await fetch(
        `${targetUrl.replace(/\/+$/, '')}/api/v1/auth/${provider}/login?redirect_uri=agentos://oauth/callback/${provider}`,
      );
      const data = await resp.json();
      if (data.authorization_url) {
        router.push({ pathname: '/oauth', params: { authUrl: data.authorization_url, provider } });
      }
    } catch (e: any) {
      Alert.alert('OAuth Error', e?.message || `Could not connect to ${provider}`);
    } finally {
      setConnecting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.content}>
        <View style={styles.heroSection}>
          <View style={styles.heroIcon}>
            <Ionicons name="sparkles" size={40} color={Colors.light.primary} />
          </View>
          <Text style={styles.title}>AgentOS</Text>
          <Text style={styles.subtitle}>Multi-Agent Platform</Text>
        </View>

        <View style={styles.card}>
          <TouchableOpacity
            style={styles.quickConnectButton}
            onPress={handleConnect}
            disabled={connecting}
            activeOpacity={0.8}
          >
            {connecting ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <>
                <Ionicons name="flash" size={20} color="#fff" />
                <Text style={styles.quickConnectText}>Quick Connect</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.advancedToggle}
            onPress={() => setShowAdvanced(!showAdvanced)}
          >
            <Text style={styles.advancedToggleText}>
              {showAdvanced ? 'Hide manual URL' : 'Manual server URL'}
            </Text>
            <Ionicons
              name={showAdvanced ? 'chevron-up' : 'chevron-down'}
              size={14}
              color={Colors.light.textTertiary}
            />
          </TouchableOpacity>

          {showAdvanced && (
            <View style={styles.advancedSection}>
              <Text style={styles.inputLabel}>Server URL</Text>
              <View style={styles.inputRow}>
                <TextInput
                  style={styles.input}
                  value={url}
                  onChangeText={setUrl}
                  placeholder="http://192.168.0.100:8004"
                  placeholderTextColor={Colors.light.textTertiary}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
                <TouchableOpacity style={styles.connectButton} onPress={handleConnect} disabled={connecting}>
                  {connecting ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <Ionicons name="arrow-forward" size={20} color="#fff" />
                  )}
                </TouchableOpacity>
              </View>
            </View>
          )}

          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or continue with</Text>
            <View style={styles.dividerLine} />
          </View>

          <View style={styles.socialRow}>
            <TouchableOpacity
              style={[styles.socialButton, styles.googleButton]}
              onPress={() => handleSocialLogin('google')}
              disabled={connecting}
            >
              <Ionicons name="logo-google" size={18} color={Colors.light.text} />
              <Text style={styles.socialText}>Google</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.socialButton, styles.githubButton]}
              onPress={() => handleSocialLogin('github')}
              disabled={connecting}
            >
              <Ionicons name="logo-github" size={18} color="#fff" />
              <Text style={[styles.socialText, { color: '#fff' }]}>GitHub</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.registerLink} onPress={() => router.push('/register')}>
            <Text style={styles.registerText}>
              New to AgentOS? <Text style={styles.registerHighlight}>Create account</Text>
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.hint}>
          Connect to your AgentOS server to manage agents, workflows, and chat.
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 32,
  },
  heroIcon: {
    width: 72,
    height: 72,
    borderRadius: 24,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: FontSizes.title,
    fontWeight: '800',
    color: Colors.light.text,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: FontSizes.md,
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  card: {
    backgroundColor: Colors.light.surface,
    borderRadius: 20,
    padding: Spacing.xxl,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 4,
  },
  quickConnectButton: {
    backgroundColor: Colors.light.primary,
    borderRadius: 14,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  quickConnectText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  advancedToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Spacing.md,
    marginTop: Spacing.xs,
  },
  advancedToggleText: {
    fontSize: FontSizes.sm,
    color: Colors.light.textTertiary,
  },
  advancedSection: {
    marginBottom: Spacing.md,
  },
  inputLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.textSecondary,
    marginBottom: Spacing.sm,
  },
  inputRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.light.surfaceVariant,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  connectButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: Colors.light.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: Spacing.xl,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.light.border,
  },
  dividerText: {
    marginHorizontal: 12,
    fontSize: FontSizes.xs,
    color: Colors.light.textTertiary,
  },
  socialRow: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.lg,
  },
  socialButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  googleButton: {
    backgroundColor: Colors.light.surface,
  },
  githubButton: {
    backgroundColor: '#24292e',
    borderColor: '#24292e',
  },
  socialText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  registerLink: {
    alignItems: 'center',
  },
  registerText: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
  },
  registerHighlight: {
    color: Colors.light.primary,
    fontWeight: '600',
  },
  hint: {
    textAlign: 'center',
    color: Colors.light.textTertiary,
    fontSize: FontSizes.xs,
    lineHeight: 18,
    marginTop: Spacing.xl,
    paddingHorizontal: Spacing.xl,
  },
});
