import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { getLogs } from '../../src/api/client';

interface AgentInfo {
  name: string;
  icon: keyof typeof Ionicons.glyphMap;
  status: 'idle' | 'running' | 'error' | 'unknown';
  model: string;
  lastTask: string;
  color: string;
}

const AGENT_NAMES = ['DevAgent', 'ContentAgent', 'MarketingAgent', 'CommerceAgent'];

const AGENT_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  DevAgent: 'code-slash-outline',
  ContentAgent: 'document-text-outline',
  MarketingAgent: 'megaphone-outline',
  CommerceAgent: 'cart-outline',
};

const AGENT_COLORS: Record<string, string> = {
  DevAgent: '#6366f1',
  ContentAgent: '#22c55e',
  MarketingAgent: '#f59e0b',
  CommerceAgent: '#ef4444',
};

export default function AgentsScreen() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAgentStatuses = useCallback(async () => {
    try {
      const logsResult = await getLogs(50);
      const logs = logsResult.logs || [];

      const agentActivity: Record<string, { lastAction: string; count: number }> = {};
      for (const name of AGENT_NAMES) {
        agentActivity[name] = { lastAction: 'No activity', count: 0 };
      }

      for (const log of logs as Array<Record<string, unknown>>) {
        const agentId = log.agent_id as string;
        if (agentId && agentActivity[agentId]) {
          agentActivity[agentId].count++;
          agentActivity[agentId].lastAction = (log.action as string) || 'Unknown';
        }
      }

      const agentList: AgentInfo[] = AGENT_NAMES.map((name) => ({
        name,
        icon: AGENT_ICONS[name] || 'ellipse-outline',
        status: agentActivity[name].count > 0 ? 'running' : 'idle',
        model: 'Default',
        lastTask: agentActivity[name].lastAction,
        color: AGENT_COLORS[name] || Colors.light.textSecondary,
      }));

      setAgents(agentList);
    } catch {
      setAgents(
        AGENT_NAMES.map((name) => ({
          name,
          icon: AGENT_ICONS[name] || 'ellipse-outline',
          status: 'unknown',
          model: 'Default',
          lastTask: 'Unreachable',
          color: AGENT_COLORS[name] || Colors.light.textTertiary,
        })),
      );
    }
  }, []);

  useEffect(() => {
    fetchAgentStatuses();
  }, [fetchAgentStatuses]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAgentStatuses();
    setRefreshing(false);
  };

  const statusColor = (status: AgentInfo['status']) => {
    switch (status) {
      case 'idle':
        return Colors.light.textTertiary;
      case 'running':
        return Colors.light.success;
      case 'error':
        return Colors.light.error;
      default:
        return Colors.light.warning;
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {agents.map((agent) => (
        <TouchableOpacity key={agent.name} style={styles.agentCard}>
          <View style={[styles.agentIcon, { backgroundColor: agent.color + '20' }]}>
            <Ionicons name={agent.icon} size={28} color={agent.color} />
          </View>
          <View style={styles.agentInfo}>
            <View style={styles.agentHeader}>
              <Text style={styles.agentName}>{agent.name}</Text>
              <View style={[styles.statusDot, { backgroundColor: statusColor(agent.status) }]} />
            </View>
            <Text style={styles.agentDetail}>Last: {agent.lastTask}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={Colors.light.textTertiary} />
        </TouchableOpacity>
      ))}

      <View style={styles.infoCard}>
        <Ionicons name="information-circle-outline" size={20} color={Colors.light.info} />
        <Text style={styles.infoText}>
          Pull down to refresh agent status. Tap an agent for details.
        </Text>
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
  agentCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    padding: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
    shadowColor: Colors.light.cardShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 2,
  },
  agentIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.lg,
  },
  agentInfo: {
    flex: 1,
  },
  agentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  agentName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: Colors.light.text,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  agentDetail: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.lg,
    marginTop: Spacing.sm,
  },
  infoText: {
    flex: 1,
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    lineHeight: 18,
  },
});
