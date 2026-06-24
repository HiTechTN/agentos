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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSizes, Spacing } from '../../src/theme';
import { Card, Badge, SkeletonList } from '../../src/components';
import { getAdminCache, setAdminCache } from '../../src/components/AdminCache';
import {
  getAdminServices,
  getAdminSettings,
  getAdminSettingsSchema,
  getAdminLLMProviders,
  getAdminUsers,
  testLLMModel,
  selectLLMModel,
  updateAdminSettings,
  AdminSettings,
  SettingsFieldMeta,
  SettingsSchemaResponse,
  ServiceStatus,
  AdminLLMProviders,
  AdminUsersResponse,
  AdminUser,
  LLMModelInfo,
} from '../../src/api/client';

type Section = 'status' | 'settings' | 'llm' | 'users' | '';

interface SectionConfig {
  key: Section;
  icon: keyof typeof Ionicons.glyphMap;
  iconFocused: keyof typeof Ionicons.glyphMap;
  label: string;
  desc: string;
  color: string;
}

const SECTIONS: SectionConfig[] = [
  {
    key: 'status',
    icon: 'pulse-outline',
    iconFocused: 'pulse',
    label: 'System Status',
    desc: 'Services, databases, connections',
    color: '#22c55e',
  },
  {
    key: 'settings',
    icon: 'cog-outline',
    iconFocused: 'cog',
    label: 'Configuration',
    desc: 'App settings and environment',
    color: '#6366f1',
  },
  {
    key: 'llm',
    icon: 'hardware-chip-outline',
    iconFocused: 'hardware-chip',
    label: 'LLM Providers',
    desc: 'Models, routing, testing',
    color: '#f59e0b',
  },
  {
    key: 'users',
    icon: 'people-outline',
    iconFocused: 'people',
    label: 'Users',
    desc: 'Manage and view account details',
    color: '#3b82f6',
  },
];

export default function AdminScreen() {
  const [section, setSection] = useState<Section>('');
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [settingsSchema, setSettingsSchema] = useState<SettingsSchemaResponse | null>(null);
  const [llmData, setLlmData] = useState<AdminLLMProviders | null>(null);
  const [users, setUsers] = useState<AdminUsersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchServices = useCallback(async () => {
    try {
      setError(null);
      const d = await getAdminServices();
      setServices(d);
      setAdminCache({ services: d as any });
    } catch (e: any) {
      setError(e?.message || 'Failed to load services');
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      setError(null);
      const [d, schema] = await Promise.all([
        getAdminSettings(),
        getAdminSettingsSchema().catch(() => null),
      ]);
      setSettings(d.settings);
      setSettingsSchema(schema);
      setAdminCache({ settings: d.settings });
    } catch (e: any) {
      setError(e?.message || 'Failed to load settings');
    }
  }, []);

  const fetchLLM = useCallback(async () => {
    try {
      setError(null);
      const d = await getAdminLLMProviders();
      setLlmData(d);
      setAdminCache({ llmModels: d as any });
    } catch (e: any) {
      setError(e?.message || 'Failed to load LLM providers');
    }
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      setError(null);
      const d = await getAdminUsers();
      setUsers(d);
      setAdminCache({ users: d.users });
    } catch (e: any) {
      setError(e?.message || 'Failed to load users');
    }
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
  }, [section, fetchServices, fetchSettings, fetchLLM, fetchUsers]);

  const changeSection = async (s: Section) => {
    setSection(s);
    setLoading(true);
    setError(null);
    try {
      if (s === 'status' && !services) await fetchServices();
      else if (s === 'settings' && !settings) await fetchSettings();
      else if (s === 'llm' && !llmData) await fetchLLM();
      else if (s === 'users' && !users) await fetchUsers();
    } finally {
      setLoading(false);
    }
  };

  // Main menu
  if (!section) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>Admin Panel</Text>
            <Text style={styles.headerSubtitle}>System management & monitoring</Text>
          </View>
          <TouchableOpacity onPress={onRefresh} style={styles.refreshBtn}>
            <Ionicons name="refresh-outline" size={20} color={Colors.light.primary} />
          </TouchableOpacity>
        </View>
        <ScrollView
          contentContainerStyle={styles.menu}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {SECTIONS.map((item) => {
            const hasData =
              (item.key === 'status' && services) ||
              (item.key === 'settings' && settings) ||
              (item.key === 'llm' && llmData) ||
              (item.key === 'users' && users);
            return (
              <TouchableOpacity
                key={item.key}
                style={styles.menuItem}
                onPress={() => changeSection(item.key)}
                activeOpacity={0.7}
              >
                <View style={[styles.menuIcon, { backgroundColor: item.color + '15' }]}>
                  <Ionicons name={item.icon} size={26} color={item.color} />
                </View>
                <View style={styles.menuText}>
                  <Text style={styles.menuLabel}>{item.label}</Text>
                  <Text style={styles.menuDesc}>{item.desc}</Text>
                </View>
                <View style={styles.menuRight}>
                  {hasData && <View style={[styles.loadedDot, { backgroundColor: item.color }]} />}
                  <Ionicons name="chevron-forward" size={18} color={Colors.light.textTertiary} />
                </View>
              </TouchableOpacity>
            );
          })}

          {/* Quick stats */}
          <View style={styles.statsRow}>
            {services && (
              <View style={styles.statCard}>
                <Ionicons name="checkmark-circle" size={18} color={Colors.light.success} />
                <Text style={styles.statValue}>
                  {Object.values(services.services || {}).filter(
                    (s) => s === 'ok' || (typeof s === 'object' && s?.status === 'ok')
                  ).length}
                </Text>
                <Text style={styles.statLabel}>Services OK</Text>
              </View>
            )}
            {llmData && (
              <View style={styles.statCard}>
                <Ionicons name="cube" size={18} color={Colors.light.warning} />
                <Text style={styles.statValue}>{Object.keys(llmData.models_by_type || {}).length}</Text>
                <Text style={styles.statLabel}>Work Types</Text>
              </View>
            )}
            {users && (
              <View style={styles.statCard}>
                <Ionicons name="person" size={18} color={Colors.light.info} />
                <Text style={styles.statValue}>{users.total}</Text>
                <Text style={styles.statLabel}>Users</Text>
              </View>
            )}
          </View>
        </ScrollView>
      </View>
    );
  }

  // Section content
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setSection('')} style={styles.backRow}>
          <Ionicons name="arrow-back" size={22} color={Colors.light.text} />
          <Text style={styles.headerTitle}>
            {SECTIONS.find((s) => s.key === section)?.label || section}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={onRefresh} style={styles.refreshBtn}>
          <Ionicons name="refresh-outline" size={20} color={Colors.light.primary} />
        </TouchableOpacity>
      </View>

      {error && (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle" size={18} color={Colors.light.error} />
          <Text style={styles.errorText} numberOfLines={2}>
            {error}
          </Text>
          <TouchableOpacity onPress={() => setError(null)}>
            <Ionicons name="close" size={16} color={Colors.light.error} />
          </TouchableOpacity>
        </View>
      )}

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {loading ? (
          <SkeletonList count={4} />
        ) : (
          <>
            {section === 'status' && <ServicesSection services={services} />}
            {section === 'settings' && (
              <SettingsSection settings={settings} schema={settingsSchema} onRefresh={fetchSettings} />
            )}
            {section === 'llm' && <LLMSection llmData={llmData} onRefresh={fetchLLM} />}
            {section === 'users' && <UsersSection users={users} />}
          </>
        )}
      </ScrollView>
    </View>
  );
}

function ServicesSection({ services }: { services: ServiceStatus | null }) {
  if (!services) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="cloud-offline-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyTitle}>No Services Data</Text>
        <Text style={styles.emptyDesc}>Pull down to refresh or check your connection</Text>
      </View>
    );
  }

  const items = Object.entries(services.services || {});
  if (items.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="checkmark-done-circle-outline" size={48} color={Colors.light.success} />
        <Text style={styles.emptyTitle}>All Clear</Text>
        <Text style={styles.emptyDesc}>No services to report</Text>
      </View>
    );
  }

  const getStatusColor = (status: string | { status: string; models?: string[]; detail?: string }) => {
    if (typeof status === 'string') return status === 'ok' ? Colors.light.success : Colors.light.error;
    return status.status === 'ok' ? Colors.light.success : Colors.light.error;
  };

  const getStatusLabel = (status: string | { status: string; models?: string[]; detail?: string }) => {
    if (typeof status === 'string') return status === 'ok' ? 'Operational' : 'Error';
    return status.status === 'ok' ? 'Operational' : 'Error';
  };

  return (
    <View style={{ gap: Spacing.sm }}>
      {items.map(([name, status]) => {
        const isOk = status === 'ok' || (typeof status === 'object' && status.status === 'ok');
        const details = typeof status === 'object' ? status : null;
        const statusColor = getStatusColor(status);
        return (
          <Card key={name} variant="outlined">
            <View style={styles.serviceRow}>
              <View style={[styles.serviceDot, { backgroundColor: statusColor }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{name}</Text>
                {details?.detail && (
                  <Text selectable style={styles.cardError}>
                    {details.detail}
                  </Text>
                )}
              </View>
              <Badge label={getStatusLabel(status)} variant={isOk ? 'success' : 'error'} />
            </View>
            {details?.models && details.models.length > 0 && (
              <View style={styles.modelTags}>
                {details.models.slice(0, 5).map((model) => (
                  <Text key={model} style={styles.modelTag}>
                    {model}
                  </Text>
                ))}
                {details.models.length > 5 && (
                  <Text style={styles.modelTag}>+{details.models.length - 5} more</Text>
                )}
              </View>
            )}
          </Card>
        );
      })}
    </View>
  );
}

function SettingsSection({
  settings,
  schema,
  onRefresh,
}: {
  settings: AdminSettings | null;
  schema: SettingsSchemaResponse | null;
  onRefresh: () => void;
}) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [filter, setFilter] = useState('');

  if (!settings) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="document-text-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyTitle}>No Settings Data</Text>
        <Text style={styles.emptyDesc}>Pull down to refresh</Text>
      </View>
    );
  }

  const entries = Object.entries(settings).filter(([k]) => !k.startsWith('_') && k !== 'model_config');
  const meta = schema?.schema?.fields || {};
  const categories = schema?.schema?.categories || {};

  const filtered = filter
    ? entries.filter(
        ([k, v]) =>
          k.toLowerCase().includes(filter.toLowerCase()) ||
          String(v).toLowerCase().includes(filter.toLowerCase()) ||
          (meta[k]?.description || '').toLowerCase().includes(filter.toLowerCase()) ||
          (meta[k]?.category || '').toLowerCase().includes(filter.toLowerCase())
      )
    : entries;

  const grouped: Record<string, [string, string | number | boolean | null][]> = {};
  const uncategorized: [string, string | number | boolean | null][] = [];
  const seenCategories = new Set<string>();
  for (const [key, value] of filtered) {
    const cat = meta[key]?.category || '';
    if (cat) {
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push([key, value]);
      seenCategories.add(cat);
    } else {
      uncategorized.push([key, value]);
    }
  }
  const categoryOrder = Object.keys(categories).filter((c) => seenCategories.has(c));

  const openLink = async (url: string) => {
    try {
      const { Linking } = await import('react-native');
      await Linking.openURL(url);
    } catch {
      /* ignore */
    }
  };

  return (
    <View style={{ gap: Spacing.sm }}>
      <View style={styles.searchRow}>
        <Ionicons name="search" size={16} color={Colors.light.textTertiary} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search settings..."
          placeholderTextColor={Colors.light.textTertiary}
          value={filter}
          onChangeText={setFilter}
        />
        {filter ? (
          <TouchableOpacity onPress={() => setFilter('')}>
            <Ionicons name="close-circle" size={16} color={Colors.light.textTertiary} />
          </TouchableOpacity>
        ) : null}
      </View>

      {categoryOrder.map((category) => {
        const catDesc = categories[category] || '';
        const catEntries = grouped[category] || [];
        return (
          <View key={category} style={{ marginBottom: Spacing.sm }}>
            <View style={styles.categoryHeader}>
              <Text style={styles.categoryTitle}>{category}</Text>
              {catDesc ? <Text style={styles.categoryDesc}>{catDesc}</Text> : null}
            </View>
            {catEntries.slice(0, 20).map(([key, value]) => {
              const fieldMeta = meta[key] as SettingsFieldMeta | undefined;
              return (
                <Card key={key} variant="outlined" style={{ marginBottom: Spacing.xs }}>
                  {editingKey === key ? (
                    <View>
                      <View style={styles.cardRow}>
                        <Text style={styles.cardTitle}>{key}</Text>
                        <Ionicons name="create-outline" size={16} color={Colors.light.primary} />
                      </View>
                      {fieldMeta?.description ? (
                        <Text style={styles.fieldDesc}>{fieldMeta.description}</Text>
                      ) : null}
                      <TextInput
                        style={styles.editInput}
                        value={editValue}
                        onChangeText={setEditValue}
                        autoCapitalize="none"
                        autoCorrect={false}
                        placeholder={fieldMeta?.placeholder || ''}
                        placeholderTextColor={Colors.light.textTertiary}
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
                        <Text style={styles.cardTitle} numberOfLines={1}>
                          {key}
                        </Text>
                        {fieldMeta?.help_url ? (
                          <TouchableOpacity
                            onPress={() => openLink(fieldMeta.help_url!)}
                            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                          >
                            <Ionicons name="information-circle-outline" size={18} color={Colors.light.primary} />
                          </TouchableOpacity>
                        ) : null}
                        <Ionicons name="create-outline" size={16} color={Colors.light.textTertiary} />
                      </View>
                      {fieldMeta?.description ? (
                        <Text style={styles.fieldDesc}>{fieldMeta.description}</Text>
                      ) : null}
                      <Text selectable style={styles.cardValue} numberOfLines={2}>
                        {String(value)}
                      </Text>
                    </TouchableOpacity>
                  )}
                </Card>
              );
            })}
          </View>
        );
      })}
      {uncategorized.length > 0 && (
        <View style={{ marginBottom: Spacing.sm }}>
          <Text style={styles.categoryTitle}>Other</Text>
          {uncategorized.slice(0, 20).map(([key, value]) => (
            <Card key={key} variant="outlined" style={{ marginBottom: Spacing.xs }}>
              <TouchableOpacity onPress={() => { setEditingKey(key); setEditValue(String(value)); }}>
                <View style={styles.cardRow}>
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {key}
                  </Text>
                  <Ionicons name="create-outline" size={16} color={Colors.light.textTertiary} />
                </View>
                <Text selectable style={styles.cardValue} numberOfLines={2}>
                  {String(value)}
                </Text>
              </TouchableOpacity>
            </Card>
          ))}
        </View>
      )}
    </View>
  );
}

function LLMSection({
  llmData,
  onRefresh,
}: {
  llmData: AdminLLMProviders | null;
  onRefresh: () => void;
}) {
  const [selectedWorkType, setSelectedWorkType] = useState('');
  const [testModelId, setTestModelId] = useState('');
  const [testResult, setTestResult] = useState<{
    success: boolean;
    latency_ms?: number;
    response?: string;
    error?: string;
  } | null>(null);
  const [testing, setTesting] = useState(false);

  if (!llmData) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="hardware-chip-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyTitle}>No LLM Data</Text>
        <Text style={styles.emptyDesc}>Pull down to refresh</Text>
      </View>
    );
  }

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
              onPress={() => {
                setSelectedWorkType(wt);
                setTestResult(null);
              }}
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
            if (!testModelId) {
              Alert.alert('Error', 'Enter a model ID');
              return;
            }
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
            <Text style={styles.cardTitle}>{testResult.success ? '✓ Success' : '✗ Failed'}</Text>
            {testResult.latency_ms && (
              <Badge
                label={`${testResult.latency_ms.toFixed(0)}ms`}
                variant={testResult.success ? 'success' : 'error'}
              />
            )}
          </View>
          <Text selectable style={styles.cardValue}>
            {testResult.response || testResult.error}
          </Text>
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
            <Text selectable style={styles.cardModelId}>
              {model.id}
            </Text>
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
                <Text style={styles.actionBtnText}>{isSelected ? 'Re-select' : 'Select'}</Text>
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
  if (!users) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="people-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyTitle}>No Users Data</Text>
        <Text style={styles.emptyDesc}>Pull down to refresh</Text>
      </View>
    );
  }

  const userList = users.users || [];
  if (userList.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="person-add-outline" size={48} color={Colors.light.textTertiary} />
        <Text style={styles.emptyTitle}>No Users Found</Text>
        <Text style={styles.emptyDesc}>No users registered yet</Text>
      </View>
    );
  }

  return (
    <View style={{ gap: Spacing.sm }}>
      <Text style={styles.totalText}>
        {users.total} user{users.total !== 1 ? 's' : ''} registered
      </Text>
      {userList.map((user: AdminUser) => (
        <Card key={user.id} variant="outlined">
          <View style={styles.cardRow}>
            <View style={styles.userAvatar}>
              <Ionicons name="person-outline" size={20} color={Colors.light.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{user.name || user.email}</Text>
              <Text style={styles.cardDetail}>{user.email}</Text>
            </View>
            <Badge label={user.role} variant={user.role === 'admin' ? 'warning' : 'neutral'} />
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: 60,
    paddingBottom: Spacing.md,
    backgroundColor: Colors.light.surface,
    borderBottomWidth: 1,
    borderBottomColor: Colors.light.border,
  },
  headerTitle: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.light.text },
  headerSubtitle: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: 2 },
  backRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  refreshBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: { padding: Spacing.lg, paddingBottom: 40 },
  menu: { padding: Spacing.lg, gap: Spacing.sm },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    padding: Spacing.lg,
    gap: Spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  menuIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuText: { flex: 1 },
  menuLabel: { fontSize: FontSizes.md, fontWeight: '600', color: Colors.light.text },
  menuDesc: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: 2 },
  menuRight: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  loadedDot: { width: 8, height: 8, borderRadius: 4 },
  statsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.lg,
  },
  statCard: {
    flex: 1,
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    padding: Spacing.md,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  statValue: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.light.text },
  statLabel: { fontSize: FontSizes.xs, color: Colors.light.textTertiary },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.light.errorLight,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  errorText: { flex: 1, fontSize: FontSizes.sm, color: Colors.light.error },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
    gap: Spacing.sm,
  },
  emptyTitle: { fontSize: FontSizes.md, fontWeight: '600', color: Colors.light.textSecondary },
  emptyDesc: { fontSize: FontSizes.sm, color: Colors.light.textTertiary },
  serviceRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  serviceDot: { width: 12, height: 12, borderRadius: 6 },
  modelTags: {
    flexDirection: 'row',
    gap: Spacing.xs,
    marginTop: Spacing.sm,
    flexWrap: 'wrap',
  },
  modelTag: {
    fontSize: FontSizes.xs,
    color: Colors.light.textSecondary,
    backgroundColor: Colors.light.surfaceVariant,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  cardTitle: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  cardValue: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginTop: Spacing.xs },
  cardRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  cardDetail: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: Spacing.xs },
  cardError: { fontSize: FontSizes.xs, color: Colors.light.error, marginTop: 2 },
  cardModelId: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, fontFamily: 'monospace', marginTop: 2 },
  tags: { flexDirection: 'row', gap: Spacing.xs, marginTop: Spacing.sm, flexWrap: 'wrap' },
  tag: {
    fontSize: FontSizes.xs,
    color: Colors.light.primary,
    backgroundColor: Colors.light.surfaceVariant,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginRight: Spacing.sm,
  },
  chipActive: { backgroundColor: Colors.light.primary, borderColor: Colors.light.primary },
  chipText: { fontSize: FontSizes.xs, color: Colors.light.textSecondary },
  chipTextActive: { color: '#fff', fontWeight: '600' },
  sectionLabel: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 12,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    padding: 0,
  },
  editInput: {
    backgroundColor: Colors.light.surfaceVariant,
    borderRadius: 8,
    padding: Spacing.sm,
    fontSize: FontSizes.sm,
    color: Colors.light.text,
    marginTop: Spacing.xs,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  editActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  saveBtn: {
    backgroundColor: Colors.light.primary,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: FontSizes.sm },
  cancelBtn: { paddingHorizontal: 16, paddingVertical: 8 },
  cancelBtnText: { color: Colors.light.textSecondary, fontSize: FontSizes.sm },
  modelCard: {
    backgroundColor: Colors.light.surface,
    borderRadius: 14,
    padding: Spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  modelCardSelected: { borderWidth: 2, borderColor: Colors.light.primary },
  modelActions: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.md },
  actionBtn: {
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  actionBtnText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.light.text },
  testBtn: { borderColor: Colors.light.primary },
  successCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.success },
  errorCard: { borderLeftWidth: 4, borderLeftColor: Colors.light.error },
  totalText: { fontSize: FontSizes.sm, color: Colors.light.textSecondary, marginBottom: Spacing.sm },
  categoryHeader: { marginBottom: Spacing.sm, marginTop: Spacing.md },
  categoryTitle: { fontSize: FontSizes.md, fontWeight: '700', color: Colors.light.text },
  categoryDesc: { fontSize: FontSizes.xs, color: Colors.light.textTertiary, marginTop: 2 },
  fieldDesc: { fontSize: FontSizes.xs, color: Colors.light.textSecondary, marginTop: 2, lineHeight: 16 },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.light.surfaceVariant,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
