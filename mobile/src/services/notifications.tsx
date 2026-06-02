import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
const PUSH_TOKEN_KEY = 'agentos_push_token';
const NOTIFICATIONS_ENABLED_KEY = 'agentos_notifications_enabled';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

interface NotificationContextType {
  expoPushToken: string | null;
  notificationsEnabled: boolean;
  setNotificationsEnabled: (enabled: boolean) => Promise<void>;
  lastNotification: Notifications.Notification | null;
}

const NotificationContext = createContext<NotificationContextType>({
  expoPushToken: null,
  notificationsEnabled: false,
  setNotificationsEnabled: async () => {},
  lastNotification: null,
});

async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS === 'web') {
    console.log('Push notifications require a physical device');
    return null;
  }

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#6366f1',
    });
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.log('Push notification permission not granted');
    return null;
  }

  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: 'b6900fa8-496a-414c-a929-c9be1b319f57',
  });
  return tokenData.data;
}

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const [expoPushToken, setExpoPushToken] = useState<string | null>(null);
  const [notificationsEnabled, setNotificationsEnabledState] = useState(true);
  const [lastNotification, setLastNotification] = useState<Notifications.Notification | null>(null);

  useEffect(() => {
    (async () => {
      const stored = await SecureStore.getItemAsync(NOTIFICATIONS_ENABLED_KEY);
      if (stored !== null) {
        setNotificationsEnabledState(stored === 'true');
      }
      const savedToken = await SecureStore.getItemAsync(PUSH_TOKEN_KEY);
      if (savedToken) {
        setExpoPushToken(savedToken);
      }
    })();
  }, []);

  useEffect(() => {
    if (!notificationsEnabled) return;

    registerForPushNotifications().then(async (token) => {
      if (token) {
        setExpoPushToken(token);
        await SecureStore.setItemAsync(PUSH_TOKEN_KEY, token);
      }
    });

    const notificationListener = Notifications.addNotificationReceivedListener((notification) => {
      setLastNotification(notification);
    });

    const responseListener = Notifications.addNotificationResponseReceivedListener((_response) => {
      // Could navigate to specific screen based on notification data
    });

    return () => {
      Notifications.removeNotificationSubscription(notificationListener);
      Notifications.removeNotificationSubscription(responseListener);
    };
  }, [notificationsEnabled]);

  const setNotificationsEnabled = useCallback(async (enabled: boolean) => {
    setNotificationsEnabledState(enabled);
    await SecureStore.setItemAsync(NOTIFICATIONS_ENABLED_KEY, String(enabled));
  }, []);

  return (
    <NotificationContext.Provider
      value={{ expoPushToken, notificationsEnabled, setNotificationsEnabled, lastNotification }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationContext);
}
