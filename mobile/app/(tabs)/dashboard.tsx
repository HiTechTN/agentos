import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import {
  healthCheck,
  getRouterStatus,
  getPendingApprovals,
  HealthStatus,
  PendingApproval,
} from '../../src/api/client';
import { useOffline } from '../../src/services/offline';

interface StatCard {
  label: string;
  value: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}

export default function DashboardScreen() {
  const { isOnline, queueLength, flush } = useOffline();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [llmStatus, setLlmStatus] = useState<string>('...');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [h, p, llm] = await Promise.all([
        healthCheck().catch(() => null),
        getPendingApprovals().catch(() => ({ pending: [] })),
        getRouterStatus()
          .then(() => 'Online')
          .catch(() => 'Offline'),
      ]);
      if (h) setHealth(h);
      setPending(p.pending || []);
      setLlmStatus(llm);
    } catch {
      // silently fail on refresh
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [fetchData]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const stats: StatCard[] = [
    {
      label: 'API',
      value: health?.api ?? '...',
      icon: 'server-outline',
      color: health?.api === 'ok' ? Colors.light.success : Colors.light.error,
    },
    {
      label: 'Database',
      value: health?.database ?? '...',
      icon: 'server-outline',
      color: health?.database === 'ok' ? Colors.light.success : Colors.light.warning,
    },
    {
      label: 'Redis',
      value: health?.redis ?? '...',
      icon: 'layers-outline',
      color: health?.redis === 'ok' ? Colors.light.success : Colors.light.warning,
    },
    {
      label: 'LLM Router',
      value: llmStatus,
      icon: 'sparkles-outline',
      color: llmStatus === 'Online' ? Colors.light.success : Colors.light.textTertiary,
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.greeting}>AgentOS</Text>
      <Text style={styles.subtitle}>v{health?.version ?? '...'}</Text>

      {!isOnline && (
        <View style={styles.offlineBanner}>
          <Ionicons name="cloud-offline-outline" size={16} color="#fff" />
          <Text style={styles.offlineBannerText}>
            Offline — {queueLength} request{queueLength !== 1 ? 's' : ''} queued
          </Text>
        </View>
      )}

      <View style={styles.statsGrid}>
        {stats.map((stat) => (
          <View key={stat.label} style={styles.statCard}>
            <Ionicons name={stat.icon} size={24} color={stat.color} />
            <Text style={[styles.statValue, { color: stat.color }]}>{stat.value}</Text>
            <Text style={styles.statLabel}>{stat.label}</Text>
          </View>
        ))}
      </View>

      {pending.length > 0 && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="hand-left-outline" size={18} color={Colors.light.warning} />
            <Text style={styles.sectionTitle}>
              Pending Approvals ({pending.length})
            </Text>
          </View>
          {pending.map((item) => (
            <View key={item.id} style={styles.approvalCard}>
              <View style={styles.approvalInfo}>
                <Text style={styles.approvalAction}>{item.action}</Text>
                <Text style={styles.approvalAgent}>{item.agent}</Text>
              </View>
              <TouchableOpacity style={styles.approveBtn}>
                <Ionicons name="checkmark-circle" size={28} color={Colors.light.success} />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Ionicons name="information-circle-outline" size={18} color={Colors.light.textSecondary} />
          <Text style={styles.sectionTitle}>Quick Actions</Text>
        </View>
        <View style={styles.quickActions}>
          <TouchableOpacity style={styles.actionButton}>
            <Ionicons name="chatbubble-ellipses-outline" size={22} color={Colors.light.primary} />
            <Text style={styles.actionText}>New Chat</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton}>
            <Ionicons name="git-branch-outline" size={22} color={Colors.light.primary} />
            <Text style={styles.actionText}>Run Plan</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton}>
            <Ionicons name="refresh-outline" size={22} color={Colors.light.primary} />
            <Text style={styles.actionText}>Refresh</Text>
          </TouchableOpacity>
        </View>
      </View>
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
    paddingBottom: 32,
  },
  greeting: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: Colors.light.text,
  },
  subtitle: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
    marginBottom: Spacing.sm,
  },
  offlineBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: Colors.light.warning,
    borderRadius: 8,
    padding: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  offlineBannerText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    color: '#fff',
    flex: 1,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: Spacing.xl,
  },
  statCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    padding: Spacing.lg,
    width: '47%',
    alignItems: 'center',
    gap: 6,
    shadowColor: Colors.light.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 2,
  },
  statValue: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    fontWeight: '500',
  },
  section: {
    marginBottom: Spacing.xl,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: Colors.light.text,
  },
  approvalCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
    shadowColor: Colors.light.cardShadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 4,
    elevation: 1,
  },
  approvalInfo: {
    flex: 1,
  },
  approvalAction: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.text,
  },
  approvalAgent: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
  approveBtn: {
    padding: 4,
  },
  quickActions: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
    alignItems: 'center',
    gap: 8,
    flex: 1,
    shadowColor: Colors.light.cardShadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 4,
    elevation: 1,
  },
  actionText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
    color: Colors.light.textSecondary,
  },
});
