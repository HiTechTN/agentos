import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  Modal,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { getLogs, getSession, SessionData } from '../../src/api/client';

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
  const [selectedSession, setSelectedSession] = useState<LogEntry | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionData | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

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

  const handleSessionPress = async (entry: LogEntry) => {
    setSelectedSession(entry);
    if (entry.traceId) {
      setLoadingDetail(true);
      try {
        const detail = await getSession(entry.traceId);
        setSessionDetail(detail);
      } catch {
        setSessionDetail(null);
      }
      setLoadingDetail(false);
    }
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
      <TouchableOpacity
        style={styles.sessionCard}
        onPress={() => handleSessionPress(item)}
        activeOpacity={0.7}
      >
        <View style={[styles.statusIconWrap, { backgroundColor: icon.color + '15' }]}>
          <Ionicons name={icon.name} size={18} color={icon.color} />
        </View>
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionAction} numberOfLines={1}>
            {item.action}
          </Text>
          <Text style={styles.sessionAgent}>{item.agentId}</Text>
        </View>
        <View style={styles.sessionMeta}>
          <Text style={styles.sessionTime}>
            {new Date(item.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </Text>
          <Ionicons name="chevron-forward" size={14} color={Colors.light.textTertiary} />
        </View>
      </TouchableOpacity>
    );
  };

  if (sessions.length === 0 && !refreshing) {
    return (
      <View style={styles.empty}>
        <View style={styles.emptyIcon}>
          <Ionicons name="time-outline" size={40} color={Colors.light.textTertiary} />
        </View>
        <Text style={styles.emptyText}>No recent activity</Text>
        <Text style={styles.emptyHint}>Run a workflow from the Chat tab to see sessions here</Text>
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

      <Modal visible={!!selectedSession} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Session Details</Text>
              <TouchableOpacity onPress={() => { setSelectedSession(null); setSessionDetail(null); }}>
                <Ionicons name="close" size={24} color={Colors.light.text} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalBody}>
              {selectedSession && (
                <>
                  <View style={styles.detailRow}>
                    <Text style={styles.detailLabel}>Action</Text>
                    <Text style={styles.detailValue}>{selectedSession.action}</Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={styles.detailLabel}>Agent</Text>
                    <Text style={styles.detailValue}>{selectedSession.agentId}</Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={styles.detailLabel}>Status</Text>
                    <View style={styles.detailStatusRow}>
                      <View style={[styles.detailDot, { backgroundColor: statusIcon(selectedSession.status).color }]} />
                      <Text style={styles.detailValue}>{selectedSession.status}</Text>
                    </View>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={styles.detailLabel}>Time</Text>
                    <Text style={styles.detailValue}>
                      {new Date(selectedSession.timestamp).toLocaleString()}
                    </Text>
                  </View>
                  {selectedSession.traceId && (
                    <View style={styles.detailRow}>
                      <Text style={styles.detailLabel}>Trace ID</Text>
                      <Text selectable style={[styles.detailValue, styles.mono]} numberOfLines={1}>
                        {selectedSession.traceId}
                      </Text>
                    </View>
                  )}
                  {loadingDetail && (
                    <Text style={styles.loadingText}>Loading details...</Text>
                  )}
                  {sessionDetail && sessionDetail.result && (
                    <View style={styles.detailSection}>
                      <Text style={styles.detailSectionTitle}>Result</Text>
                      <Text selectable style={styles.detailResult}>{sessionDetail.result}</Text>
                    </View>
                  )}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
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
    borderRadius: 14,
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
  statusIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
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
  sessionMeta: {
    alignItems: 'flex-end',
    gap: 4,
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
    gap: 12,
    padding: 32,
  },
  emptyIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  emptyText: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: Colors.light.textSecondary,
  },
  emptyHint: {
    fontSize: FontSizes.sm,
    color: Colors.light.textTertiary,
    textAlign: 'center',
    lineHeight: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: Colors.light.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '80%',
    paddingBottom: 32,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.xl,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
  },
  modalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    color: Colors.light.text,
  },
  modalBody: {
    padding: Spacing.xl,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.borderLight,
  },
  detailLabel: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
    fontWeight: '500',
  },
  detailValue: {
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    fontWeight: '500',
    maxWidth: '60%',
    textAlign: 'right',
  },
  detailStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  detailDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  mono: {
    fontFamily: 'monospace',
    fontSize: FontSizes.xs,
  },
  loadingText: {
    fontSize: FontSizes.sm,
    color: Colors.light.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.lg,
  },
  detailSection: {
    marginTop: Spacing.lg,
  },
  detailSectionTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.text,
    marginBottom: Spacing.sm,
  },
  detailResult: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
    lineHeight: 20,
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 8,
    padding: Spacing.md,
  },
});
