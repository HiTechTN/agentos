import { useState, useCallback } from 'react';
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
  Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { useAuth } from '../../src/auth/AuthContext';
import {
  getAdminServices,
  getAdminSettings,
  getAdminLLMProviders,
  getAdminUsers,
  testLLMModel,
  selectLLMModel,
  updateAdminSettings,
  AdminSettings,
  ServiceStatus,
  AdminLLMProviders,
  AdminUsersResponse,
  AdminUser,
} from '../../src/api/client';

type Section = 'status' | 'settings' | 'llm' | 'users' | '';

export default function AdminScreen() {
  const { logout } = useAuth();
  const [section, setSection] = useState<Section>('status');
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [llmData, setLlmData] = useState<AdminLLMProviders | null>(null);
  const [users, setUsers] = useState<AdminUsersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [selectedWorkType, setSelectedWorkType] = useState('general');
  const [testModelId, setTestModelId] = useState('');
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms?: number; response?: string; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const fetchServices = useCallback(async () => {
    try {
      const data = await getAdminServices();
      setServices(data);
    } catch { /* ignore */ }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      const data = await getAdminSettings();
      setSettings(data.settings);
    } catch { /* ignore */ }
  }, []);

  const fetchLLM = useCallback(async () => {
    try {
      const data = await getAdminLLMProviders();
      setLlmData(data);
    } catch { /* ignore */ }
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      const data = await getAdminUsers();
      setUsers(data);
    } catch { /* ignore */ }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (section === 'status') await fetchServices();
      else if (section === 'settings') await fetchSettings();
      else if (section === 'llm') await fetchLLM();
      else if (section === 'users') await fetchUsers();
    } finally {
      setRefreshing(false);
    }
  }, [section, fetchServices, fetchSettings, fetchLLM, fetchUsers]);

  const changeSection = (s: Section) => {
    setSection(s);
    setTestResult(null);
    setEditingKey(null);
    if (s === 'status') fetchServices();
    else if (s === 'settings') fetchSettings();
    else if (s === 'llm') fetchLLM();
    else if (s === 'users') fetchUsers();
  };

  if (!section) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>Admin Panel</Text>
        </View>
        <View style={styles.menu}>
          {([
            { key: 'status', icon: 'pulse-outline', label: 'System Status' },
            { key: 'settings', icon: 'settings-outline', label: 'Configuration' },
            { key: 'llm', icon: 'hardware-chip-outline', label: 'LLM Providers' },
            { key: 'users', icon: 'people-outline', label: 'Users' },
          ] as const).map((item) => (
            <TouchableOpacity
              key={item.key}
              style={styles.menuItem}
              onPress={() => changeSection(item.key)}
            >
              <View style={styles.menuIcon}>
                <Ionicons name={item.icon} size={24} color={Colors.light.primary} />
              </View>
              <View style={styles.menuText}>
                <Text style={styles.menuLabel}>{item.label}</Text>
                <Text style={styles.menuArrow}>{'>'}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={styles.backButton} onPress={() => setSection('')}>
          <Ionicons name="arrow-back" size={20} color={Colors.light.text} />
          <Text style={styles.backText}>Back to Dashboard</Text>
        </TouchableOpacity>
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
        {section === 'status' && <ServicesSection services={services} loading={loading} />}
        {section === 'settings' && (
          <SettingsSection
            settings={settings}
            loading={loading}
            editingKey={editingKey}
            editValue={editValue}
            setEditingKey={setEditingKey}
            setEditValue={setEditValue}
            onSave={async (key, value) => {
              try {
                await updateAdminSettings({ [key]: value });
                Alert.alert('Saved', `${key} updated`);
                setEditingKey(null);
                fetchSettings();
              } catch (e: any) {
                Alert.alert('Error', e.message);
              }
            }}
          />
        )}
        {section === 'llm' && (
          <LLMSection
            llmData={llmData}
            loading={loading}
            selectedWorkType={selectedWorkType}
            setSelectedWorkType={setSelectedWorkType}
            testModelId={testModelId}
            setTestModelId={setTestModelId}
            testResult={testResult}
            testing={testing}
            onTest={async () => {
              if (!testModelId) { Alert.alert('Error', 'Select a model first'); return; }
              setTesting(true);
              setTestResult(null);
              try {
                const result = await testLLMModel(testModelId);
                setTestResult(result);
              } catch (e: any) {
                setTestResult({ success: false, error: e.message });
              } finally {
                setTesting(false);
              }
            }}
            onSelect={async (wt, mid) => {
              try {
                await selectLLMModel(wt, mid);
                Alert.alert('Selected', `${mid} for ${wt}`);
                fetchLLM();
              } catch (e: any) {
                Alert.alert('Error', e.message);
              }
            }}
            onModelTest={async (mid) => {
              setTestModelId(mid);
              setTesting(true);
              setTestResult(null);
              try {
                const result = await testLLMModel(mid);
                setTestResult(result);
              } catch (e: any) {
                setTestResult({ success: false, error: e.message });
              } finally {
                setTesting(false);
              }
            }}
          />
        )}
        {section === 'users' && <UsersSection users={users} loading={loading} />}
      </ScrollView>
    </View>
  );
}

function ServicesSection({ services }: { services: ServiceStatus | null; loading: boolean }) {
  if (!services) return <ActivityIndicator style={{ marginTop: 40 }} />;

  const items = Object.entries(services.services || {});
  return (
    <View style={styles.section}>
      {items.map(([name, status]) => {
        const isOk = status === 'ok' || (typeof status === 'object' && status.status === 'ok');
        const details = typeof status === 'object' ? status : null;
        return (
          <View key={name} style={styles.card}>
            <View style={styles.cardRow}>
              <View style={[styles.dot, { backgroundColor: isOk ? Colors.light.success : Colors.light.error }]} />
              <Text style={styles.cardTitle}>{name.toUpperCase()}</Text>
              <Text style={[styles.cardStatus, { color: isOk ? Colors.light.success : Colors.light.error }]}>
                {isOk ? 'OK' : 'ERROR'}
              </Text>
            </View>
            {details?.models && details.models.length > 0 && (
              <Text style={styles.cardDetail}>Models: {details.models.join(', ')}</Text>
            )}
            {details?.detail && (
              <Text style={styles.cardError}>{details.detail}</Text>
            )}
          </View>
        );
      })}
    </View>
  );
}

function SettingsSection({
  settings, editingKey, editValue, setEditingKey, setEditValue, onSave,
}: {
  settings: AdminSettings | null; loading: boolean;
  editingKey: string | null; editValue: string;
  setEditingKey: (k: string | null) => void; setEditValue: (v: string) => void;
  onSave: (key: string, value: string) => Promise<void>;
}) {
  if (!settings) return <ActivityIndicator style={{ marginTop: 40 }} />;

  const entries = Object.entries(settings).filter(([k]) => !k.startsWith('_') && k !== 'model_config');
  const [filter, setFilter] = useState('');

  const filtered = filter
    ? entries.filter(([k, v]) => k.toLowerCase().includes(filter.toLowerCase()) || String(v).toLowerCase().includes(filter.toLowerCase()))
    : entries;

  return (
    <View style={styles.section}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search settings..."
        placeholderTextColor={Colors.light.textTertiary}
        value={filter}
        onChangeText={setFilter}
      />
      {filtered.slice(0, 50).map(([key, value]) => (
        <View key={key} style={styles.card}>
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
                <TouchableOpacity style={styles.saveBtn} onPress={() => onSave(key, editValue)}>
                  <Text style={styles.saveBtnText}>Save</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.cancelBtn} onPress={() => setEditingKey(null)}>
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <TouchableOpacity onPress={() => { setEditingKey(key); setEditValue(String(value)); }}>
              <Text style={styles.cardTitle}>{key}</Text>
              <Text style={styles.cardValue} numberOfLines={2}>{String(value)}</Text>
            </TouchableOpacity>
          )}
        </View>
      ))}
    </View>
  );
}

function LLMSection({
  llmData, selectedWorkType, setSelectedWorkType, testModelId, setTestModelId,
  testResult, testing, onTest, onSelect, onModelTest,
}: {
  llmData: AdminLLMProviders | null; loading: boolean;
  selectedWorkType: string; setSelectedWorkType: (v: string) => void;
  testModelId: string; setTestModelId: (v: string) => void;
  testResult: { success: boolean; latency_ms?: number; response?: string; error?: string } | null;
  testing: boolean; onTest: () => Promise<void>;
  onSelect: (workType: string, modelId: string) => Promise<void>;
  onModelTest: (modelId: string) => Promise<void>;
}) {
  if (!llmData) return <ActivityIndicator style={{ marginTop: 40 }} />;

  const workTypes = Object.keys(llmData.models_by_type || {});
  const currentModels = llmData.models_by_type[selectedWorkType] || [];

  return (
    <View style={styles.section}>
      <View style={styles.card}>
        <Text style={styles.sectionLabel}>Work Type</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
          {workTypes.map((wt) => (
            <TouchableOpacity
              key={wt}
              style={[styles.chip, wt === selectedWorkType && styles.chipActive]}
              onPress={() => setSelectedWorkType(wt)}
            >
              <Text style={[styles.chipText, wt === selectedWorkType && styles.chipTextActive]}>
                {wt.replace('_', ' ')}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {currentModels.map((model) => (
        <TouchableOpacity
          key={model.id}
          style={[styles.card, testModelId === model.id && styles.cardSelected]}
          onPress={() => setTestModelId(model.id)}
        >
          <View style={styles.cardRow}>
            <Text style={styles.cardTitle}>{model.name}</Text>
            {llmData.current_selections[selectedWorkType] === model.id && (
              <View style={styles.activeBadge}>
                <Text style={styles.activeBadgeText}>Active</Text>
              </View>
            )}
          </View>
          <Text style={styles.cardDetail}>{model.id}</Text>
          <View style={styles.tags}>
            <Text style={styles.tag}>ctx: {model.context_window.toLocaleString()}</Text>
            {model.supports_tools && <Text style={styles.tag}>tools</Text>}
            {model.supports_vision && <Text style={styles.tag}>vision</Text>}
          </View>
          <View style={styles.cardActions}>
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={() => onSelect(selectedWorkType, model.id)}
            >
              <Text style={styles.actionBtnText}>Select</Text>
            </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionBtn, styles.testBtn]}
            onPress={async () => {
              onModelTest(model.id);
            }}
            >
              <Text style={[styles.actionBtnText, { color: Colors.light.primary }]}>Test</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      ))}

      {testResult && (
        <View style={[styles.card, testResult.success ? styles.successCard : styles.errorCard]}>
          <Text style={styles.cardTitle}>
            {testResult.success ? 'Success' : 'Failed'}
            {testResult.latency_ms ? ` (${testResult.latency_ms.toFixed(0)}ms)` : ''}
          </Text>
          <Text style={styles.cardValue}>
            {testResult.response || testResult.error}
          </Text>
        </View>
      )}
    </View>
  );
}

function UsersSection({ users }: { users: AdminUsersResponse | null; loading: boolean }) {
  if (!users) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <View style={styles.section}>
      <Text style={styles.totalText}>Total: {users.total} users</Text>
      {(users.users || []).map((user: AdminUser) => (
        <View key={user.id} style={styles.card}>
          <View style={styles.cardRow}>
            <View style={styles.avatar}>
              <Ionicons name="person-outline" size={20} color={Colors.light.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{user.name || user.email}</Text>
              <Text style={styles.cardDetail}>{user.email}</Text>
            </View>
            <View style={[styles.roleBadge, user.role === 'admin' && styles.adminBadge]}>
              <Text style={[styles.roleText, user.role === 'admin' && styles.adminText]}>
                {user.role}
              </Text>
            </View>
          </View>
          <Text style={styles.cardDetail}>
            Joined: {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}
            {user.email_verified ? ' | Verified' : ' | Not verified'}
          </Text>
        </View>
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
  headerTitle: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.light.text, marginLeft: Spacing.sm },
  backRow: { flexDirection: 'row', alignItems: 'center' },
  title: { fontSize: FontSizes.xxl, fontWeight: '700', color: Colors.light.text },
  content: { padding: Spacing.lg, paddingBottom: 40 },
  menu: { padding: Spacing.lg, gap: Spacing.sm },
  menuItem: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.light.surface,
    borderRadius: 12, padding: Spacing.lg, marginBottom: Spacing.sm,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  menuIcon: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center', justifyContent: 'center', marginRight: Spacing.md,
  },
  menuText: { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  menuLabel: { fontSize: FontSizes.md, fontWeight: '600', color: Colors.light.text },
  menuArrow: { fontSize: FontSizes.lg, color: Colors.light.textTertiary },
  section: { gap: Spacing.sm },
  card: {
    backgroundColor: Colors.light.surface, borderRadius: 12, padding: Spacing.lg,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  cardSelected: { borderWidth: 2, borderColor: Colors.light.primary },
  cardRow: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.xs },
  cardTitle: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text, flex: 1 },
  cardValue: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginTop: Spacing.xs },
  cardStatus: { fontSize: FontSizes.sm, fontWeight: '700', marginLeft: 'auto' },
  cardDetail: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: 2 },
  cardError: { fontSize: FontSizes.xs, color: Colors.light.error, marginTop: Spacing.xs },
  cardActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.sm },
  tags: { flexDirection: 'row', gap: Spacing.xs, marginTop: Spacing.xs, flexWrap: 'wrap' },
  tag: {
    fontSize: FontSizes.xs, color: Colors.light.primary, backgroundColor: Colors.light.surfaceVariant,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, overflow: 'hidden',
  },
  chipRow: { marginTop: Spacing.sm },
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
    borderRadius: 8,
  },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: FontSizes.sm },
  cancelBtn: { paddingHorizontal: 16, paddingVertical: 8 },
  cancelBtnText: { color: Colors.light.textSecondary, fontSize: FontSizes.sm },
  activeBadge: {
    backgroundColor: Colors.light.success + '20', paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 8,
  },
  activeBadgeText: { fontSize: FontSizes.xs, color: Colors.light.success, fontWeight: '600' },
  actionBtn: {
    borderWidth: 1, borderColor: Colors.light.border, borderRadius: 8,
    paddingHorizontal: 16, paddingVertical: 8,
  },
  actionBtnText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  testBtn: { borderColor: Colors.light.primary },
  successCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.success },
  errorCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.error },
  totalText: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginBottom: Spacing.sm },
  avatar: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center', justifyContent: 'center', marginRight: Spacing.sm,
  },
  roleBadge: {
    backgroundColor: Colors.light.surfaceVariant, paddingHorizontal: 10, paddingVertical: 3,
    borderRadius: 8,
  },
  adminBadge: { backgroundColor: Colors.light.warning + '30' },
  roleText: { fontSize: FontSizes.xs, color: Colors.light.textSecondary, fontWeight: '600' },
  adminText: { color: Colors.light.warning },
  backButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    padding: Spacing.lg, gap: Spacing.sm,
  },
  backText: { fontSize: FontSizes.md, color: Colors.light.textSecondary },
});
