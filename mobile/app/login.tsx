import { useState, useRef } from 'react';
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
  ScrollView,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../src/theme';
import { useAuth } from '../src/auth/AuthContext';
import { healthCheck, loginWithCredentials } from '../src/api/client';

export default function LoginScreen() {
  const { serverUrl, updateServerUrl } = useAuth();
  const [url, setUrl] = useState(serverUrl || 'http://192.168.0.100:8081');
  const [email, setEmail] = useState('admin@agentos.io');
  const [password, setPassword] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useState(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 600,
      useNativeDriver: true,
    }).start();
  });

  const handleConnect = async () => {
    const targetUrl = url.trim() || serverUrl || 'http://192.168.0.100:8081';
    if (!email.trim()) {
      Alert.alert('Email required', 'Please enter your email to connect');
      return;
    }
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
      const resp = await loginWithCredentials(email.trim(), password);
      const { setToken } = await import('../src/api/client');
      await setToken(resp.access_token);
      router.replace('/(tabs)/dashboard');
    } catch (e: any) {
      Alert.alert('Connection Error', e?.message || 'Could not connect to server');
    } finally {
      setConnecting(false);
    }
  };

  const handleQuickConnect = async () => {
    const targetUrl = url.trim() || 'http://192.168.0.100:8081';
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
      // Use the new /token endpoint for quick dev access
      const resp = await fetch(`${targetUrl.replace(/\/+$/, '')}/api/v1/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sub: 'quick', workspace: 'default' }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      const { setToken: saveToken } = await import('../src/api/client');
      await saveToken(data.access_token);
      router.replace('/(tabs)/dashboard');
    } catch (e: any) {
      Alert.alert('Connection Error', e?.message || 'Could not connect. Try email login.');
    } finally {
      setConnecting(false);
    }
  };

  const handleSocialLogin = async (provider: string) => {
    const targetUrl = url.trim() || serverUrl || 'http://192.168.0.100:8081';
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
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        <View style={styles.heroSection}>
          <View style={styles.heroIcon}>
            <Ionicons name="sparkles" size={36} color={Colors.light.primary} />
          </View>
          <Text style={styles.title}>AgentOS</Text>
          <Text style={styles.subtitle}>Multi-Agent Platform</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Sign in</Text>
          <Text style={styles.cardSubtitle}>Enter your credentials to continue</Text>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={Colors.light.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              editable={!connecting}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <View style={styles.passwordRow}>
              <TextInput
                style={[styles.input, styles.passwordInput]}
                value={password}
                onChangeText={setPassword}
                placeholder="Enter your password"
                placeholderTextColor={Colors.light.textTertiary}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                editable={!connecting}
              />
              <TouchableOpacity
                style={styles.eyeButton}
                onPress={() => setShowPassword(!showPassword)}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={Colors.light.textSecondary}
                />
              </TouchableOpacity>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.primaryButton, connecting && styles.buttonDisabled]}
            onPress={handleConnect}
            disabled={connecting}
            activeOpacity={0.8}
          >
            {connecting ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <>
                <Ionicons name="log-in-outline" size={18} color="#fff" />
                <Text style={styles.primaryButtonText}>Sign In</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.quickConnectRow}
            onPress={handleQuickConnect}
            disabled={connecting}
          >
            <Ionicons name="flash-outline" size={16} color={Colors.light.primary} />
            <Text style={styles.quickConnectText}>
              Quick Connect (dev mode)
            </Text>
          </TouchableOpacity>

          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
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

        <TouchableOpacity
          style={styles.advancedToggle}
          onPress={() => setShowAdvanced(!showAdvanced)}
        >
          <Ionicons
            name={showAdvanced ? 'chevron-up' : 'chevron-down'}
            size={14}
            color={Colors.light.textTertiary}
          />
          <Text style={styles.advancedToggleText}>
            {showAdvanced ? 'Hide server settings' : 'Server settings'}
          </Text>
        </TouchableOpacity>

        {showAdvanced && (
          <View style={styles.advancedSection}>
            <Text style={styles.label}>Server URL</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.input}
                value={url}
                onChangeText={setUrl}
                placeholder="http://192.168.0.100:8081"
                placeholderTextColor={Colors.light.textTertiary}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                editable={!connecting}
              />
            </View>
          </View>
        )}

        <View style={styles.helpCard}>
          <Ionicons name="help-circle-outline" size={16} color={Colors.light.info} />
          <Text style={styles.helpText}>
            New here? Use demo credentials: <Text style={styles.helpHighlight}>admin@agentos.io</Text> / any password. 
            Or tap "Create account" to register.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 40,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 28,
  },
  heroIcon: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: Colors.light.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  title: {
    fontSize: FontSizes.xxl,
    fontWeight: '800',
    color: Colors.light.text,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: FontSizes.sm,
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
  cardTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: 4,
  },
  cardSubtitle: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
    marginBottom: Spacing.xl,
  },
  inputGroup: {
    marginBottom: Spacing.md,
  },
  label: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.text,
    marginBottom: Spacing.xs,
  },
  input: {
    backgroundColor: Colors.light.surfaceVariant,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: FontSizes.md,
    color: Colors.light.text,
  },
  passwordRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  passwordInput: {
    flex: 1,
  },
  eyeButton: {
    position: 'absolute',
    right: 12,
    padding: 4,
  },
  primaryButton: {
    backgroundColor: Colors.light.primary,
    borderRadius: 14,
    paddingVertical: 15,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: Spacing.sm,
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  quickConnectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Spacing.md,
    marginTop: Spacing.xs,
  },
  quickConnectText: {
    fontSize: FontSizes.sm,
    color: Colors.light.primary,
    fontWeight: '500',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: Spacing.lg,
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
  advancedToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Spacing.md,
    marginTop: Spacing.sm,
  },
  advancedToggleText: {
    fontSize: FontSizes.sm,
    color: Colors.light.textTertiary,
  },
  advancedSection: {
    backgroundColor: Colors.light.surface,
    borderRadius: 14,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
  },
  inputRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  helpCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: Colors.light.infoLight,
    borderRadius: 12,
    padding: Spacing.md,
    marginTop: Spacing.sm,
  },
  helpText: {
    flex: 1,
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    lineHeight: 18,
  },
  helpHighlight: {
    fontWeight: '600',
    color: Colors.light.info,
  },
});
