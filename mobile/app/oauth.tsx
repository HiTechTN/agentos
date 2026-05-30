import { useEffect, useState } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  TouchableOpacity,
  Linking,
  Alert,
} from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Colors } from '../src/theme';
import { setToken, getBaseUrl } from '../src/api/client';

export default function OAuthScreen() {
  const { authUrl, provider } = useLocalSearchParams<{ authUrl: string; provider: string }>();
  const [status, setStatus] = useState<'opening' | 'waiting' | 'error'>('opening');

  useEffect(() => {
    if (!authUrl) {
      setStatus('error');
      return;
    }
    Linking.openURL(authUrl)
      .then(() => setStatus('waiting'))
      .catch(() => setStatus('error'));
  }, [authUrl]);

  const handleDeepLink = async (event: { url: string }) => {
    const { url } = event;
    const code = new URL(url).searchParams.get('code');
    if (!code) {
      Alert.alert('OAuth Error', 'No authorization code received');
      return;
    }

    try {
      const response = await fetch(
        `${getBaseUrl()}/api/v1/auth/${provider}/callback?code=${encodeURIComponent(code)}`,
        { method: 'POST' },
      );
      const data = await response.json();
      if (data.access_token) {
        await setToken(data.access_token);
        Alert.alert('Success', 'Logged in via ' + provider, [
          { text: 'OK', onPress: () => router.replace('/(tabs)/dashboard') },
        ]);
      } else {
        Alert.alert('OAuth Error', data.detail || 'Authentication failed');
      }
    } catch (e: any) {
      Alert.alert('OAuth Error', e?.message || 'Could not complete authentication');
    }
  };

  useEffect(() => {
    if (status === 'waiting') {
      Linking.addEventListener('url', handleDeepLink);
      return () => {
        // Cleanup handled by React Native automatically
      };
    }
  }, [status]);

  return (
    <View style={styles.container}>
      {status === 'opening' && (
        <>
          <ActivityIndicator size="large" color={Colors.light.primary} />
          <Text style={styles.text}>Opening {provider} login...</Text>
        </>
      )}
      {status === 'waiting' && (
        <>
          <ActivityIndicator size="large" color={Colors.light.primary} />
          <Text style={styles.text}>Waiting for {provider} authentication...</Text>
          <Text style={styles.hint}>Complete the login in your browser, then return here.</Text>
        </>
      )}
      {status === 'error' && (
        <>
          <Text style={styles.errorIcon}>⚠</Text>
          <Text style={styles.text}>Could not open authentication page</Text>
          <TouchableOpacity style={styles.button} onPress={() => router.back()}>
            <Text style={styles.buttonText}>Go Back</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    padding: 24,
    gap: 16,
  },
  text: {
    fontSize: 16,
    color: Colors.light.text,
    textAlign: 'center',
  },
  hint: {
    fontSize: 14,
    color: Colors.light.textSecondary,
    textAlign: 'center',
  },
  errorIcon: {
    fontSize: 48,
  },
  button: {
    backgroundColor: Colors.light.primary,
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
