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
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../src/theme';
import { useAuth } from '../src/auth/AuthContext';
import { healthCheck } from '../src/api/client';

export default function LoginScreen() {
  const { serverUrl, updateServerUrl, login } = useAuth();
  const [url, setUrl] = useState(serverUrl || 'http://localhost:8003');
  const [connecting, setConnecting] = useState(false);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      await updateServerUrl(url);
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
    setConnecting(true);
    try {
      await updateServerUrl(url);
      const resp = await fetch(
        `${url.replace(/\/+$/, '')}/api/v1/auth/${provider}/login?redirect_uri=agentos://oauth/callback/${provider}`,
      );
      const data = await resp.json();
      if (data.authorization_url) {
        router.push({
          pathname: '/oauth',
          params: { authUrl: data.authorization_url, provider },
        });
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
        <View style={styles.header}>
          <Text style={styles.logo}>⚡</Text>
          <Text style={styles.title}>AgentOS</Text>
          <Text style={styles.subtitle}>Mobile</Text>
        </View>

        <View style={styles.form}>
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
            style={[styles.button, styles.primaryButton, connecting && styles.buttonDisabled]}
            onPress={handleConnect}
            disabled={connecting}
          >
            {connecting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Connect</Text>
            )}
          </TouchableOpacity>
        </View>

        <View style={styles.divider}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>or</Text>
          <View style={styles.dividerLine} />
        </View>

        <View style={styles.socialRow}>
          <TouchableOpacity
            style={[styles.socialButton, styles.googleButton]}
            onPress={() => handleSocialLogin('google')}
          >
            <Ionicons name="logo-google" size={20} color={Colors.light.text} />
            <Text style={styles.socialText}>Google</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.socialButton, styles.githubButton]}
            onPress={() => handleSocialLogin('github')}
          >
            <Ionicons name="logo-github" size={20} color="#fff" />
            <Text style={[styles.socialText, { color: '#fff' }]}>GitHub</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.registerLink} onPress={() => router.push('/register')}>
          <Text style={styles.registerText}>
            Don't have an account? <Text style={styles.registerHighlight}>Create one</Text>
          </Text>
        </TouchableOpacity>

        <Text style={styles.hint}>
          Enter the URL of your AgentOS server to connect remotely.
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
    paddingHorizontal: 32,
  },
  header: {
    alignItems: 'center',
    marginBottom: 36,
  },
  logo: {
    fontSize: 64,
    marginBottom: 8,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: Colors.light.text,
  },
  subtitle: {
    fontSize: 18,
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  form: {
    gap: 12,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.light.text,
    marginBottom: -4,
  },
  input: {
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: Colors.light.text,
  },
  button: {
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  primaryButton: {
    backgroundColor: Colors.light.primary,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 20,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.light.border,
  },
  dividerText: {
    marginHorizontal: 12,
    fontSize: 13,
    color: Colors.light.textTertiary,
  },
  socialRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
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
    fontSize: 14,
    fontWeight: '600',
  },
  registerLink: {
    alignItems: 'center',
    marginBottom: 16,
  },
  registerText: {
    fontSize: 14,
    color: Colors.light.textSecondary,
  },
  registerHighlight: {
    color: Colors.light.primary,
    fontWeight: '600',
  },
  hint: {
    textAlign: 'center',
    color: Colors.light.textTertiary,
    fontSize: 13,
    lineHeight: 18,
  },
});
