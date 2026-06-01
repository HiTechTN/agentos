import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { router } from 'expo-router';
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
  description: string;
}

const AGENT_DETAILS: Record<string, { icon: keyof typeof Ionicons.glyphMap; color: string; desc: string }> = {
  DevAgent: { icon: 'code-slash-outline', color: '#6366f1', desc: 'Writes, debugs, and reviews code' },
  ContentAgent: { icon: 'document-text-outline', color: '#22c55e', desc: 'Creates and edits content' },
  MarketingAgent: { icon: 'megaphone-outline', color: '#f59e0b', desc: 'Manages marketing campaigns' },
  CommerceAgent: { icon: 'cart-outline', color: '#ef4444', desc: 'Handles e-commerce operations' },
};

const AGENT_NAMES = Object.keys(AGENT_DETAILS);

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

      const agentList: AgentInfo[] = AGENT_NAMES.map((name) => {
        const details = AGENT_DETAILS[name] || { icon: 'ellipse-outline' as keyof typeof Ionicons.glyphMap, color: Colors.light.textSecondary, desc: '' };
        return {
          name,
          icon: details.icon,
          status: agentActivity[name].count > 0 ? 'running' : 'idle',
          model: 'Default',
          lastTask: agentActivity[name].lastAction,
          color: details.color,
          description: details.desc,
        };
      });

      setAgents(agentList);
    } catch {
      setAgents(
        AGENT_NAMES.map((name) => {
          const details = AGENT_DETAILS[name] || { icon: 'ellipse-outline' as keyof typeof Ionicons.glyphMap, color: Colors.light.textTertiary, desc: '' };
          return {
            name,
            icon: details.icon,
            status: 'unknown',
            model: 'Default',
            lastTask: 'Unreachable',
            color: details.color,
            description: details.desc,
          };
        }),
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

  const statusLabel = (status: AgentInfo['status']) => {
    switch (status) {
      case 'idle': return 'Idle';
      case 'running': return 'Active';
      case 'error': return 'Error';
      default: return 'Unknown';
    }
  };

  const handleAgentPress = (agent: AgentInfo) => {
    Alert.alert(
      agent.name,
      `${agent.description}\n\nStatus: ${statusLabel(agent.status)}\nLast task: ${agent.lastTask}\nModel: ${agent.model}`,
      [
        { text: 'Close', style: 'cancel' },
        { text: 'Chat with Agent', onPress: () => router.push({
          pathname: '/(tabs)/chat',
          params: { agent: agent.name }
        })},
      ],
    );
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Agents</Text>
        <Text style={styles.subtitle}>{agents.filter(a => a.status === 'running').length} active</Text>
      </View>

      {agents.map((agent) => (
        <TouchableOpacity
          key={agent.name}
          style={styles.agentCard}
          onPress={() => handleAgentPress(agent)}
          activeOpacity={0.7}
        >
          <View style={[styles.agentIcon, { backgroundColor: agent.color + '20' }]}>
            <Ionicons name={agent.icon} size={28} color={agent.color} />
          </View>
          <View style={styles.agentInfo}>
            <View style={styles.agentHeader}>
              <Text style={styles.agentName}>{agent.name}</Text>
              <View style={[styles.statusDot, { backgroundColor: statusColor(agent.status) }]} />
            </View>
            <Text style={styles.agentDesc}>{agent.description}</Text>
            <Text style={styles.agentDetail}>Last: {agent.lastTask}</Text>
          </View>
          <View style={styles.agentActions}>
            <BadgeDot color={statusColor(agent.status)} label={statusLabel(agent.status)} />
            <Ionicons name="chevron-forward" size={18} color={Colors.light.textTertiary} />
          </View>
        </TouchableOpacity>
      ))}

      <View style={styles.helpCard}>
        <Ionicons name="information-circle-outline" size={18} color={Colors.light.info} />
        <Text style={styles.helpText}>
          Tap an agent to see details and start a conversation. Pull down to refresh status.
        </Text>
      </View>

      <TouchableOpacity
        style={styles.chatAllButton}
        onPress={() => router.push('/(tabs)/chat')}
        activeOpacity={0.7}
      >
        <Ionicons name="chatbubble-ellipses" size={18} color="#fff" />
        <Text style={styles.chatAllText}>Talk to All Agents</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function BadgeDot({ color, label }: { color: string; label: string }) {
  return (
    <View style={[styles.badgeDot, { backgroundColor: color + '20', borderColor: color }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.badgeLabel, { color }]}>{label}</Text>
    </View>
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
    alignItems: 'baseline',
    marginBottom: Spacing.xl,
  },
  title: {
    fontSize: FontSizes.xxl,
    fontWeight: '800',
    color: Colors.light.text,
  },
  subtitle: {
    fontSize: FontSizes.sm,
    color: Colors.light.textSecondary,
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
  agentDesc: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
  agentDetail: {
    fontSize: FontSizes.xs,
    color: Colors.light.textTertiary,
    marginTop: 2,
  },
  agentActions: {
    alignItems: 'flex-end',
    gap: 6,
  },
  badgeDot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    borderWidth: 1,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  badgeLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  helpCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: Colors.light.infoLight,
    borderRadius: 12,
    padding: Spacing.lg,
    marginTop: Spacing.sm,
    marginBottom: Spacing.md,
  },
  helpText: {
    flex: 1,
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    lineHeight: 18,
  },
  chatAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Colors.light.primary,
    borderRadius: 14,
    paddingVertical: 14,
  },
  chatAllText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
});
