import { useEffect, useState } from 'react';
import { Redirect, Stack } from 'expo-router';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import { Colors } from '../src/theme';
import { isAuthenticated } from '../src/api/client';

export default function Index() {
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
    setChecked(true);
  }, []);

  if (!checked) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  if (!authed) {
    return <Redirect href="/login" />;
  }

  return <Redirect href="/dashboard" />;
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
  },
});
