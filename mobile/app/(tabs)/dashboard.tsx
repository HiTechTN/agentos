import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { useFocusEffect, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { Card, Badge } from '../../src/components';
import {
  healthCheck,
  getRouterStatus,
  getPendingApprovals,
  getAdminSettings,
  HealthStatus,
  PendingApproval,
} from '../../src/api/client';
import { setAdminCache } from '../../src/components/AdminCache';
import { useOffline } from '../../src/services/offline';

interface StatItem {
  label: string;
  value: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}

export default function DashboardScreen() {
  const { isOnline, queueLength } = useOffline();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [llmStatus, setLlmStatus] = useState<string>('...');
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [h, p, llm] = await Promise.all([
        healthCheck().catch(() => null),
        getPendingApprovals().catch(() => ({ pending: [] })),
        getRouterStatus().then(() => 'Online').catch(() => 'Offline'),
      ]);
      if (h) setHealth(h);
      setPending(p.pending || []);
      setLlmStatus(llm);

      // Pre-fetch admin data in background
      getAdminSettings().then((s) =>
        setAdminCache({ settings: s.settings })
      ).catch(() => {});
    } catch { /* silent */ }
  }, []);

  useFocusEffect(
    useCallback(() => { fetchData(); }, [fetchData]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const stats: StatItem[] = [
    {
      label: 'API', value: health?.api ?? '...',
      icon: 'server-outline',
      color: health?.api === 'ok' ? Colors.light.success : Colors.light.error,
    },
    {
      label: 'Database', value: health?.database ?? '...',
      icon: 'server-outline',
      color: health?.database === 'ok' ? Colors.light.success : Colors.light.warning,
    },
    {
      label: 'Redis', value: health?.redis ?? '...',
      icon: 'layers-outline',
      color: health?.redis === 'ok' ? Colors.light.success : Colors.light.warning,
    },
    {
      label: 'LLM Router', value: llmStatus,
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
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>AgentOS</Text>
          <Text style={styles.version}>v{health?.version ?? '...'}</Text>
        </View>
        <TouchableOpacity
          style={styles.adminChip}
          onPress={() => router.push('/(tabs)/admin')}
          activeOpacity={0.7}
        >
          <Ionicons name="shield-outline" size={16} color={Colors.light.primary} />
          <Text style={styles.adminChipText}>Admin</Text>
        </TouchableOpacity>
      </View>

      {!isOnline && (
        <Card variant="elevated" style={styles.offlineCard}>
          <View style={styles.offlineRow}>
            <Ionicons name="cloud-offline-outline" size={20} color={Colors.light.warning} />
            <Text style={styles.offlineText}>
              Offline — {queueLength} request{queueLength !== 1 ? 's' : ''} queued
            </Text>
          </View>
        </Card>
      )}

      <View style={styles.statsGrid}>
        {stats.map((stat) => (
          <Card key={stat.label} variant="elevated" style={styles.statCard}>
            <View style={[styles.statIcon, { backgroundColor: stat.color + '15' }]}>
              <Ionicons name={stat.icon} size={22} color={stat.color} />
            </View>
            <Text style={[styles.statValue, { color: stat.color }]}>{stat.value}</Text>
            <Text style={styles.statLabel}>{stat.label}</Text>
          </Card>
        ))}
      </View>

      {pending.length > 0 && (
        <Card variant="outlined" style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Ionicons name="hand-left" size={18} color={Colors.light.warning} />
            <Text style={styles.sectionTitle}>Pending Approvals</Text>
            <Badge label={String(pending.length)} variant="warning" />
          </View>
          {pending.map((item) => (
            <TouchableOpacity key={item.id} style={styles.approvalRow} activeOpacity={0.7}>
              <View style={styles.approvalInfo}>
                <Text style={styles.approvalAction}>{item.action}</Text>
                <Text style={styles.approvalAgent}>{item.agent}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={Colors.light.textTertiary} />
            </TouchableOpacity>
          ))}
        </Card>
      )}

      <Card variant="default" style={styles.sectionCard}>
        <View style={styles.sectionHeader}>
          <Ionicons name="flash" size={18} color={Colors.light.primary} />
          <Text style={styles.sectionTitle}>Quick Actions</Text>
        </View>
        <View style={styles.actionsGrid}>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => router.push('/(tabs)/chat')}
            activeOpacity={0.7}
          >
            <View style={[styles.actionIcon, { backgroundColor: Colors.light.primaryLight }]}>
              <Ionicons name="chatbubble-ellipses" size={24} color={Colors.light.primary} />
            </View>
            <Text style={styles.actionLabel}>New Chat</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionCard} activeOpacity={0.7}>
            <View style={[styles.actionIcon, { backgroundColor: Colors.light.successLight }]}>
              <Ionicons name="git-branch" size={24} color={Colors.light.success} />
            </View>
            <Text style={styles.actionLabel}>Run Plan</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => router.push('/(tabs)/sessions')}
            activeOpacity={0.7}
          >
            <View style={[styles.actionIcon, { backgroundColor: Colors.light.infoLight }]}>
              <Ionicons name="time" size={24} color={Colors.light.info} />
            </View>
            <Text style={styles.actionLabel}>Sessions</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => router.push('/(tabs)/admin')}
            activeOpacity={0.7}
          >
            <View style={[styles.actionIcon, { backgroundColor: Colors.light.warningLight }]}>
              <Ionicons name="shield" size={24} color={Colors.light.warning} />
            </View>
            <Text style={styles.actionLabel}>Admin</Text>
          </TouchableOpacity>
        </View>
      </Card>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.xl,
  },
  title: {
    fontSize: FontSizes.xxl,
    fontWeight: '800',
    color: Colors.light.text,
  },
  version: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
  adminChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Colors.light.primaryLight,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
  },
  adminChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.primary,
  },
  offlineCard: {
    marginBottom: Spacing.md,
  },
  offlineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  offlineText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    color: Colors.light.warning,
    flex: 1,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: Spacing.xl,
  },
  statCard: {
    width: '47%',
    padding: Spacing.lg,
    alignItems: 'center',
    gap: 8,
  },
  statIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    fontWeight: '500',
  },
  sectionCard: {
    marginBottom: Spacing.lg,
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
    flex: 1,
  },
  approvalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.light.borderLight,
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
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  actionCard: {
    width: '47%',
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 14,
    padding: Spacing.lg,
    alignItems: 'center',
    gap: Spacing.sm,
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.text,
  },
});
