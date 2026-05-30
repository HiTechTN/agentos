import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { getLogs, SessionData } from '../../src/api/client';

interface LogEntry {
  id: string;
  timestamp: string;
  action: string;
  agentId: string;
  status: string;
  traceId?: string;
}

export default function SessionsScreen() {
  const [sessions, setSessions] = useState<LogEntry[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchSessions = useCallback(async () => {
    try {
      const result = await getLogs(50);
      const entries: LogEntry[] = (result.logs || []).map(
        (log: any, index: number) => ({
          id: `${log.trace_id || index}-${index}`,
          timestamp: log.timestamp || new Date().toISOString(),
          action: log.action || 'unknown',
          agentId: log.agent_id || 'system',
          status: log.status || 'completed',
          traceId: log.trace_id,
        }),
      );
      setSessions(entries);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchSessions();
    setRefreshing(false);
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return { name: 'checkmark-circle' as const, color: Colors.light.success };
      case 'failed':
      case 'error':
        return { name: 'alert-circle' as const, color: Colors.light.error };
      case 'running':
      case 'pending':
        return { name: 'time-outline' as const, color: Colors.light.warning };
      default:
        return { name: 'ellipse-outline' as const, color: Colors.light.textTertiary };
    }
  };

  const renderItem = ({ item }: { item: LogEntry }) => {
    const icon = statusIcon(item.status);
    return (
      <TouchableOpacity style={styles.sessionCard}>
        <Ionicons name={icon.name} size={22} color={icon.color} />
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionAction} numberOfLines={1}>
            {item.action}
          </Text>
          <Text style={styles.sessionAgent}>{item.agentId}</Text>
        </View>
        <Text style={styles.sessionTime}>
          {new Date(item.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </Text>
      </TouchableOpacity>
    );
  };

  if (sessions.length === 0 && !refreshing) {
    return (
      <View style={styles.empty}>
        <Ionicons name="time-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyText}>No recent activity</Text>
        <Text style={styles.emptyHint}>Run a workflow to see sessions here</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={sessions}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  list: {
    padding: Spacing.lg,
  },
  sessionCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
    gap: 12,
    shadowColor: Colors.light.cardShadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 4,
    elevation: 1,
  },
  sessionInfo: {
    flex: 1,
  },
  sessionAction: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.text,
  },
  sessionAgent: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
  sessionTime: {
    fontSize: FontSizes.xs,
    color: Colors.light.textTertiary,
  },
  empty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
    gap: 8,
  },
  emptyText: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: Colors.light.textSecondary,
  },
  emptyHint: {
    fontSize: FontSizes.sm,
    color: Colors.light.textTertiary,
  },
});
