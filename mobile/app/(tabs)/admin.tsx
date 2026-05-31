import { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  TextInput,
  RefreshControl,
  SectionList,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { Card, Badge, SkeletonList } from '../../src/components';
import { getAdminCache, setAdminCache } from '../../src/components/AdminCache';
import {
  getAdminServices,
  getAdminSettings,
  getAdminLLMProviders,
  getAdminUsers,
  testLLMModel,
  selectLLMModel,
  updateAdminSettings,
  getAdminDataCached,
  AdminSettings,
  ServiceStatus,
  AdminLLMProviders,
  AdminUsersResponse,
  AdminUser,
  LLMModelInfo,
} from '../../src/api/client';

type Section = 'status' | 'settings' | 'llm' | 'users' | '';

export default function AdminScreen() {
  const [section, setSection] = useState<Section>('');
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [llmData, setLlmData] = useState<AdminLLMProviders | null>(null);
  const [users, setUsers] = useState<AdminUsersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Pre-fetch all admin data from cache on mount
  useEffect(() => {
    (async () => {
      try {
        const cached = await getAdminCache();
        if (cached) {
          if (cached.services) setServices(cached.services as ServiceStatus);
          if (cached.settings) setSettings(cached.settings as AdminSettings);
          if (cached.llmModels) setLlmData(cached.llmModels as unknown as AdminLLMProviders);
          if (cached.users) setUsers({ users: cached.users as AdminUser[], total: cached.users.length });
        }
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  const fetchServices = useCallback(async () => {
    const d = await getAdminServices();
    setServices(d);
    setAdminCache({ services: d as any });
  }, []);

  const fetchSettings = useCallback(async () => {
    const d = await getAdminSettings();
    setSettings(d.settings);
    setAdminCache({ settings: d.settings });
  }, []);

  const fetchLLM = useCallback(async () => {
    const d = await getAdminLLMProviders();
    setLlmData(d);
    setAdminCache({ llmModels: d as any });
  }, []);

  const fetchUsers = useCallback(async () => {
    const d = await getAdminUsers();
    setUsers(d);
    setAdminCache({ users: d.users });
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (section === 'status') await fetchServices();
      else if (section === 'settings') await fetchSettings();
      else if (section === 'llm') await fetchLLM();
      else if (section === 'users') await fetchUsers();
      else {
        await Promise.all([fetchServices(), fetchSettings(), fetchLLM(), fetchUsers()]);
      }
    } finally {
      setRefreshing(false);
    }
  }, [section]);

  const changeSection = (s: Section) => {
    setSection(s);
    if (s === 'status' && !services) fetchServices();
    else if (s === 'settings' && !settings) fetchSettings();
    else if (s === 'llm' && !llmData) fetchLLM();
    else if (s === 'users' && !users) fetchUsers();
  };

  if (!section) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Admin Panel</Text>
          <TouchableOpacity onPress={onRefresh}>
            <Ionicons name="refresh-outline" size={22} color={Colors.light.primary} />
          </TouchableOpacity>
        </View>
        <ScrollView
          contentContainerStyle={styles.menu}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {([
            { key: 'status', icon: 'pulse-outline', label: 'System Status', desc: 'Services, databases, connections' },
            { key: 'settings', icon: 'settings-outline', label: 'Configuration', desc: 'App settings and environment' },
            { key: 'llm', icon: 'hardware-chip-outline', label: 'LLM Providers', desc: 'Models, routing, testing' },
            { key: 'users', icon: 'people-outline', label: 'Users', desc: 'Manage and view account details' },
          ] as const).map((item) => (
            <TouchableOpacity
              key={item.key}
              style={styles.menuItem}
              onPress={() => changeSection(item.key)}
              activeOpacity={0.7}
            >
              <View style={styles.menuIcon}>
                <Ionicons name={item.icon} size={24} color={Colors.light.primary} />
              </View>
              <View style={styles.menuText}>
                <Text style={styles.menuLabel}>{item.label}</Text>
                <Text style={styles.menuDesc}>{item.desc}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={Colors.light.textTertiary} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setSection('')} style={styles.backRow}>
          <Ionicons name="arrow-back" size={22} color={Colors.light.text} />
          <Text style={styles.headerTitle}>
            {section === 'status' ? 'System Status' : section === 'settings' ? 'Configuration' : section === 'llm' ? 'LLM Providers' : 'Users'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={onRefresh}>
          <Ionicons name="refresh-outline" size={22} color={Colors.light.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {section === 'status' && (
          loading ? <SkeletonList count={3} /> : <ServicesSection services={services} />
        )}
        {section === 'settings' && (
          loading ? <SkeletonList count={3} /> : <SettingsSection settings={settings} onRefresh={fetchSettings} />
        )}
        {section === 'llm' && (
          loading ? <SkeletonList count={3} /> : <LLMSection llmData={llmData} onRefresh={fetchLLM} />
        )}
        {section === 'users' && (
          loading ? <SkeletonList count={3} /> : <UsersSection users={users} />
        )}
      </ScrollView>
    </View>
  );
}

function ServicesSection({ services }: { services: ServiceStatus | null }) {
  if (!services) return <Text style={styles.emptyText}>No services data</Text>;

  const items = Object.entries(services.services || {});
  return (
    <View style={{ gap: Spacing.sm }}>
      {items.map(([name, status]) => {
        const isOk = status === 'ok' || (typeof status === 'object' && status.status === 'ok');
        const details = typeof status === 'object' ? status : null;
        const label = details?.models ? `${details.models.length} models` : undefined;
        return (
          <Card key={name} variant="outlined">
            <View style={styles.serviceRow}>
              <View style={[styles.serviceDot, { backgroundColor: isOk ? Colors.light.success : Colors.light.error }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{name}</Text>
                {details?.detail && <Text style={styles.cardError}>{details.detail}</Text>}
              </View>
              <Badge label={isOk ? 'OK' : 'ERR'} variant={isOk ? 'success' : 'error'} />
            </View>
            {label && <Text style={styles.cardDetail}>{label}</Text>}
            {details?.models && details.models.length > 0 && (
              <Text style={styles.cardDetail}>Models: {details.models.join(', ')}</Text>
            )}
          </Card>
        );
      })}
    </View>
  );
}

function SettingsSection({ settings, onRefresh }: { settings: AdminSettings | null; onRefresh: () => void }) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [filter, setFilter] = useState('');

  if (!settings) return <Text style={styles.emptyText}>No settings data</Text>;

  const entries = Object.entries(settings).filter(([k]) => !k.startsWith('_') && k !== 'model_config');
  const filtered = filter
    ? entries.filter(([k, v]) =>
        k.toLowerCase().includes(filter.toLowerCase()) ||
        String(v).toLowerCase().includes(filter.toLowerCase())
      )
    : entries;

  return (
    <View style={{ gap: Spacing.sm }}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search settings..."
        placeholderTextColor={Colors.light.textTertiary}
        value={filter}
        onChangeText={setFilter}
      />
      {filtered.slice(0, 50).map(([key, value]) => (
        <Card key={key} variant="outlined">
          {editingKey === key ? (
            <View>
              <Text style={styles.cardTitle}>{key}</Text>
              <TextInput
                style={styles.editInput}
                value={editValue}
                onChangeText={setEditValue}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <View style={styles.editActions}>
                <TouchableOpacity
                  style={styles.saveBtn}
                  onPress={async () => {
                    try {
                      await updateAdminSettings({ [key]: editValue });
                      Alert.alert('Saved', `${key} updated`);
                      setEditingKey(null);
                      onRefresh();
                    } catch (e: any) {
                      Alert.alert('Error', e.message);
                    }
                  }}
                >
                  <Text style={styles.saveBtnText}>Save</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.cancelBtn} onPress={() => setEditingKey(null)}>
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <TouchableOpacity onPress={() => { setEditingKey(key); setEditValue(String(value)); }}>
              <View style={styles.cardRow}>
                <Text style={styles.cardTitle} numberOfLines={1}>{key}</Text>
                <Ionicons name="create-outline" size={16} color={Colors.light.textTertiary} />
              </View>
              <Text style={styles.cardValue} numberOfLines={3}>{String(value)}</Text>
            </TouchableOpacity>
          )}
        </Card>
      ))}
    </View>
  );
}

function LLMSection({ llmData, onRefresh }: { llmData: AdminLLMProviders | null; onRefresh: () => void }) {
  const [selectedWorkType, setSelectedWorkType] = useState('');
  const [testModelId, setTestModelId] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms?: number; response?: string; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  if (!llmData) return <Text style={styles.emptyText}>No LLM data</Text>;

  const workTypes = Object.keys(llmData.models_by_type || {});
  const currentWT = selectedWorkType || workTypes[0] || '';
  const currentModels = llmData.models_by_type[currentWT] || [];

  return (
    <View style={{ gap: Spacing.sm }}>
      <Card variant="outlined">
        <Text style={styles.sectionLabel}>Work Type</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: Spacing.sm }}>
          {workTypes.map((wt) => (
            <TouchableOpacity
              key={wt}
              style={[styles.chip, wt === currentWT && styles.chipActive]}
              onPress={() => { setSelectedWorkType(wt); setTestResult(null); }}
            >
              <Text style={[styles.chipText, wt === currentWT && styles.chipTextActive]}>
                {wt.replace('_', ' ')}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </Card>

      <View style={{ flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm }}>
        <TextInput
          style={[styles.searchInput, { flex: 1 }]}
          placeholder="Test model ID..."
          placeholderTextColor={Colors.light.textTertiary}
          value={testModelId}
          onChangeText={setTestModelId}
        />
        <TouchableOpacity
          style={[styles.saveBtn, { paddingHorizontal: 20 }]}
          onPress={async () => {
            if (!testModelId) { Alert.alert('Error', 'Enter a model ID'); return; }
            setTesting(true);
            setTestResult(null);
            try {
              setTestResult(await testLLMModel(testModelId));
            } catch (e: any) {
              setTestResult({ success: false, error: e.message });
            } finally {
              setTesting(false);
            }
          }}
          disabled={testing}
        >
          {testing ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.saveBtnText}>Test</Text>
          )}
        </TouchableOpacity>
      </View>

      {testResult && (
        <Card variant="outlined" style={testResult.success ? styles.successCard : styles.errorCard}>
          <View style={styles.cardRow}>
            <Text style={styles.cardTitle}>
              {testResult.success ? '✓ Success' : '✗ Failed'}
            </Text>
            {testResult.latency_ms && (
              <Badge label={`${testResult.latency_ms.toFixed(0)}ms`} variant={testResult.success ? 'success' : 'error'} />
            )}
          </View>
          <Text style={styles.cardValue}>{testResult.response || testResult.error}</Text>
        </Card>
      )}

      {currentModels.map((model: LLMModelInfo) => {
        const isSelected = llmData.current_selections[currentWT] === model.id;
        return (
          <TouchableOpacity
            key={model.id}
            style={[styles.modelCard, isSelected && styles.modelCardSelected]}
            onPress={() => setTestModelId(model.id)}
            activeOpacity={0.7}
          >
            <View style={styles.cardRow}>
              <Text style={styles.cardTitle}>{model.name}</Text>
              {isSelected && <Badge label="Active" variant="success" />}
            </View>
            <Text style={styles.cardModelId}>{model.id}</Text>
            <View style={styles.tags}>
              <Text style={styles.tag}>ctx: {model.context_window.toLocaleString()}</Text>
              {model.supports_tools && <Text style={styles.tag}>tools</Text>}
              {model.supports_vision && <Text style={styles.tag}>vision</Text>}
            </View>
            <View style={styles.modelActions}>
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={async () => {
                  try {
                    await selectLLMModel(currentWT, model.id);
                    Alert.alert('Selected', `${model.name} for ${currentWT}`);
                    onRefresh();
                  } catch (e: any) {
                    Alert.alert('Error', e.message);
                  }
                }}
              >
                <Text style={styles.actionBtnText}>
                  {isSelected ? 'Re-select' : 'Select'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.actionBtn, styles.testBtn]}
                onPress={async () => {
                  setTestModelId(model.id);
                  setTesting(true);
                  setTestResult(null);
                  try {
                    setTestResult(await testLLMModel(model.id));
                  } catch (e: any) {
                    setTestResult({ success: false, error: e.message });
                  } finally {
                    setTesting(false);
                  }
                }}
              >
                <Text style={[styles.actionBtnText, { color: Colors.light.primary }]}>Test</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function UsersSection({ users }: { users: AdminUsersResponse | null }) {
  if (!users) return <Text style={styles.emptyText}>No users data</Text>;

  return (
    <View style={{ gap: Spacing.sm }}>
      <Text style={styles.totalText}>Total: {users.total} users</Text>
      {(users.users || []).map((user: AdminUser) => (
        <Card key={user.id} variant="outlined">
          <View style={styles.cardRow}>
            <View style={styles.userAvatar}>
              <Ionicons name="person-outline" size={20} color={Colors.light.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{user.name || user.email}</Text>
              <Text style={styles.cardDetail}>{user.email}</Text>
            </View>
            <Badge
              label={user.role}
              variant={user.role === 'admin' ? 'warning' : 'neutral'}
            />
          </View>
          <Text style={styles.cardDetail}>
            Joined {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}
            {user.email_verified ? ' · Verified' : ' · Not verified'}
          </Text>
        </Card>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.light.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.xl, paddingTop: 60, paddingBottom: Spacing.md,
    backgroundColor: Colors.light.surface, borderBottomWidth: 1, borderBottomColor: Colors.light.border,
  },
  headerTitle: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.light.text },
  backRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  content: { padding: Spacing.lg, paddingBottom: 40 },
  menu: { padding: Spacing.lg, gap: Spacing.sm },
  menuItem: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.light.surface,
    borderRadius: 14, padding: Spacing.lg, gap: Spacing.md,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 6, elevation: 2,
  },
  menuIcon: {
    width: 48, height: 48, borderRadius: 14, backgroundColor: Colors.light.primaryLight,
    alignItems: 'center', justifyContent: 'center',
  },
  menuText: { flex: 1 },
  menuLabel: { fontSize: FontSizes.md, fontWeight: '600', color: Colors.light.text },
  menuDesc: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: 2 },
  serviceRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  serviceDot: { width: 12, height: 12, borderRadius: 6 },
  cardTitle: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  cardValue: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginTop: Spacing.xs },
  cardRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  cardDetail: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: Spacing.xs },
  cardError: { fontSize: FontSizes.xs, color: Colors.light.error, marginTop: 2 },
  cardModelId: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, fontFamily: 'monospace', marginTop: 2 },
  emptyText: { fontSize: FontSizes.sm, color: Colors.light.textTertiary, textAlign: 'center', marginTop: 40 },
  tags: { flexDirection: 'row', gap: Spacing.xs, marginTop: Spacing.sm, flexWrap: 'wrap' },
  tag: {
    fontSize: FontSizes.xs, color: Colors.light.primary, backgroundColor: Colors.light.surfaceVariant,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, overflow: 'hidden',
  },
  chip: {
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16,
    borderWidth: 1, borderColor: Colors.light.border, marginRight: Spacing.sm,
  },
  chipActive: { backgroundColor: Colors.light.primary, borderColor: Colors.light.primary },
  chipText: { fontSize: FontSizes.xs, color: Colors.light.textSecondary },
  chipTextActive: { color: '#fff', fontWeight: '600' },
  sectionLabel: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  searchInput: {
    backgroundColor: Colors.light.surface, borderWidth: 1, borderColor: Colors.light.border,
    borderRadius: 12, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    fontSize: FontSizes.sm, color: Colors.light.text,
  },
  editInput: {
    backgroundColor: Colors.light.surfaceVariant, borderRadius: 8, padding: Spacing.sm,
    fontSize: FontSizes.sm, color: Colors.light.text, marginTop: Spacing.xs,
    borderWidth: 1, borderColor: Colors.light.border,
  },
  editActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  saveBtn: {
    backgroundColor: Colors.light.primary, paddingHorizontal: 20, paddingVertical: 8,
    borderRadius: 8, alignItems: 'center', justifyContent: 'center',
  },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: FontSizes.sm },
  cancelBtn: { paddingHorizontal: 16, paddingVertical: 8 },
  cancelBtnText: { color: Colors.light.textSecondary, fontSize: FontSizes.sm },
  modelCard: {
    backgroundColor: Colors.light.surface, borderRadius: 14, padding: Spacing.lg,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 6, elevation: 2,
  },
  modelCardSelected: { borderWidth: 2, borderColor: Colors.light.primary },
  modelActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.md },
  actionBtn: {
    borderWidth: 1, borderColor: Colors.light.border, borderRadius: 8,
    paddingHorizontal: 16, paddingVertical: 8,
  },
  actionBtnText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  testBtn: { borderColor: Colors.light.primary },
  successCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.success },
  errorCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.error },
  totalText: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginBottom: Spacing.sm },
  userAvatar: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center', justifyContent: 'center',
  },
});
