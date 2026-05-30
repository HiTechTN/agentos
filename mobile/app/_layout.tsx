import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider } from '../src/auth/AuthContext';
import { NotificationsProvider } from '../src/services/notifications';
import { OfflineProvider } from '../src/services/offline';

export default function RootLayout() {
  return (
    <AuthProvider>
      <OfflineProvider>
        <NotificationsProvider>
          <StatusBar style="auto" />
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="index" />
            <Stack.Screen
              name="login"
              options={{ presentation: 'modal', animation: 'slide_from_bottom' }}
            />
            <Stack.Screen name="(tabs)" />
          </Stack>
        </NotificationsProvider>
      </OfflineProvider>
    </AuthProvider>
  );
}
