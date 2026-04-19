import { useEffect, useState, useCallback } from 'react';
import { voiceSettingsAPI, agentsAPI } from '../services/api';

/**
 * VoiceSettingsTab — Settings tab for VAPI voice call configuration.
 *
 * Agent section (all users):
 *   - View / edit own voice profile (voice, tone, assistant name, opening message, mode)
 *
 * Admin section (admin / superadmin):
 *   - CRUD on AgentVoiceTemplates
 *   - Assign a template to any agent
 */
export default function VoiceSettingsTab({ isAdmin }) {
  // ── Agent profile ───────────────────────────────────────────────────────────
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Available voices/tones come from the agent's assigned template
  const [availableVoices, setAvailableVoices] = useState([]);
  const [availableTones, setAvailableTones] = useState([]);

  // ── Admin: templates ────────────────────────────────────────────────────────
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templateError, setTemplateError] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null); // null | 'new' | object
  const [templateSaving, setTemplateSaving] = useState(false);

  // ── Admin: assign template to agent ────────────────────────────────────────
  const [agents, setAgents] = useState([]);
  const [assignState, setAssignState] = useState({}); // { agentId: { templateId, saving } }

  // ── Load profile ────────────────────────────────────────────────────────────
  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const res = await voiceSettingsAPI.getMyProfile();
      const prof = res.data;
      setProfile(prof);

      // Load dropdown options from the agent's template
      if (prof?.template_id) {
        const [voicesRes, tonesRes] = await Promise.all([
          voiceSettingsAPI.getAvailableVoices(prof.template_id),
          voiceSettingsAPI.getAvailableTones(prof.template_id),
        ]);
        setAvailableVoices(voicesRes.data?.voice_ids || []);
        setAvailableTones(tonesRes.data?.tones || []);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        // Profile not yet configured — normal for new agents
        setProfile(null);
      } else {
        setProfileError(err.response?.data?.detail || 'Error al cargar perfil de voz');
      }
    } finally {
      setProfileLoading(false);
    }
  }, []);

  // ── Load templates + agents (admin) ────────────────────────────────────────
  const loadTemplates = useCallback(async () => {
    if (!isAdmin) return;
    setTemplatesLoading(true);
    setTemplateError(null);
    try {
      const [tmplRes, agentsRes] = await Promise.all([
        voiceSettingsAPI.listTemplates(),
        agentsAPI.getAll(),
      ]);
      setTemplates(tmplRes.data || []);
      setAgents(agentsRes.data || []);
    } catch (err) {
      setTemplateError(err.response?.data?.detail || 'Error al cargar plantillas');
    } finally {
      setTemplatesLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    loadProfile();
    loadTemplates();
  }, [loadProfile, loadTemplates]);

  // ── Save profile ────────────────────────────────────────────────────────────
  const handleSaveProfile = async (e) => {
    e.preventDefault();
    if (!profile) return;
    setProfileSaving(true);
    setProfileSuccess(false);
    try {
      const payload = {
        selected_voice_id: profile.selected_voice_id || null,
        selected_tone: profile.selected_tone || null,
        assistant_name: profile.assistant_name || null,
        opening_message: profile.opening_message || null,
        preferred_call_mode: profile.preferred_call_mode || null,
      };
      const res = await voiceSettingsAPI.updateMyProfile(payload);
      setProfile(res.data);
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err) {
      setProfileError(err.response?.data?.detail || 'Error al guardar perfil');
    } finally {
      setProfileSaving(false);
    }
  };

  // ── Template form helpers ───────────────────────────────────────────────────
  const emptyTemplate = {
    name: '',
    business_prompt: '',
    niche_instructions: '',
    language: 'es',
    max_duration_seconds: 600,
    max_silence_seconds: 30,
    recording_policy: 'enabled',
    available_voice_ids: [],
    available_tones: [],
    default_call_mode: 'transcriptor',
    is_active: true,
  };

  const handleSaveTemplate = async (e) => {
    e.preventDefault();
    if (!editingTemplate) return;
    setTemplateSaving(true);
    try {
      const isNew = editingTemplate.id == null;
      // Serialize available_voice_ids: split comma-separated string if text field
      let voiceIds = editingTemplate.available_voice_ids;
      if (typeof voiceIds === 'string') {
        voiceIds = voiceIds.split(',').map((s) => s.trim()).filter(Boolean);
      }
      let tones = editingTemplate.available_tones;
      if (typeof tones === 'string') {
        tones = tones.split(',').map((s) => s.trim()).filter(Boolean);
      }
      const payload = { ...editingTemplate, available_voice_ids: voiceIds, available_tones: tones };

      if (isNew) {
        await voiceSettingsAPI.createTemplate(payload);
      } else {
        await voiceSettingsAPI.updateTemplate(editingTemplate.id, payload);
      }
      setEditingTemplate(null);
      await loadTemplates();
    } catch (err) {
      setTemplateError(err.response?.data?.detail || 'Error al guardar plantilla');
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleDeleteTemplate = async (id) => {
    if (!window.confirm('¿Eliminar esta plantilla?')) return;
    try {
      await voiceSettingsAPI.deleteTemplate(id);
      await loadTemplates();
    } catch (err) {
      setTemplateError(err.response?.data?.detail || 'Error al eliminar plantilla');
    }
  };

  // ── Assign template to agent ────────────────────────────────────────────────
  const handleAssignTemplate = async (agentId, templateId) => {
    if (!templateId) return;
    setAssignState((s) => ({ ...s, [agentId]: { ...s[agentId], saving: true } }));
    try {
      await voiceSettingsAPI.assignTemplate(agentId, Number(templateId));
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al asignar plantilla');
    } finally {
      setAssignState((s) => ({ ...s, [agentId]: { ...s[agentId], saving: false } }));
    }
  };

  // ── Helpers ─────────────────────────────────────────────────────────────────
  /** Extracts a display-friendly voice ID string from a voice entry */
  const voiceEntryId = (entry) =>
    typeof entry === 'string' ? entry : entry?.voiceId || String(entry);

  const voiceEntryLabel = (entry) => {
    if (typeof entry === 'string') return entry;
    return entry?.voiceId
      ? `${entry.voiceId} (${entry.provider || 'azure'})`
      : String(entry);
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8">
      {/* ── Agent voice profile ── */}
      <section>
        <h2 className="text-base font-semibold text-gray-900 mb-4">🎙️ Mi perfil de voz</h2>

        {profileLoading && (
          <p className="text-sm text-gray-500">Cargando perfil…</p>
        )}

        {!profileLoading && profile === null && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes un perfil de voz configurado. Pide a un administrador que te asigne una
            plantilla de voz para poder realizar llamadas en modo Agente IA.
          </div>
        )}

        {!profileLoading && profile && (
          <form onSubmit={handleSaveProfile} className="space-y-4 max-w-xl">
            {/* Voice selector */}
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                Voz
              </label>
              <select
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={profile.selected_voice_id || ''}
                onChange={(e) => setProfile({ ...profile, selected_voice_id: e.target.value || null })}
              >
                <option value="">— Voz predeterminada —</option>
                {availableVoices.map((entry) => (
                  <option key={voiceEntryId(entry)} value={voiceEntryId(entry)}>
                    {voiceEntryLabel(entry)}
                  </option>
                ))}
              </select>
            </div>

            {/* Tone selector */}
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                Tono
              </label>
              <select
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={profile.selected_tone || ''}
                onChange={(e) => setProfile({ ...profile, selected_tone: e.target.value || null })}
              >
                <option value="">— Tono predeterminado —</option>
                {availableTones.map((tone) => (
                  <option key={tone} value={tone}>{tone}</option>
                ))}
              </select>
            </div>

            {/* Assistant name */}
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                Nombre del asistente de voz
              </label>
              <input
                type="text"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Ej: Sofía"
                value={profile.assistant_name || ''}
                onChange={(e) => setProfile({ ...profile, assistant_name: e.target.value || null })}
                maxLength={100}
              />
            </div>

            {/* Opening message */}
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                Mensaje de apertura
              </label>
              <textarea
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Ej: Hola, te llamo de parte de Inmobiliaria X…"
                rows={2}
                value={profile.opening_message || ''}
                onChange={(e) => setProfile({ ...profile, opening_message: e.target.value || null })}
              />
            </div>

            {/* Preferred mode */}
            <div>
              <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                Modo preferido
              </label>
              <select
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={profile.preferred_call_mode || ''}
                onChange={(e) => setProfile({ ...profile, preferred_call_mode: e.target.value || null })}
              >
                <option value="">— Usar predeterminado de la plantilla —</option>
                <option value="transcriptor">Transcriptor (tú hablas)</option>
                <option value="ai_agent">Agente IA (IA conduce)</option>
              </select>
            </div>

            {profileError && (
              <p className="text-sm text-red-600">{profileError}</p>
            )}
            {profileSuccess && (
              <p className="text-sm text-green-600">✓ Perfil guardado</p>
            )}

            <button
              type="submit"
              disabled={profileSaving}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {profileSaving ? 'Guardando…' : 'Guardar perfil'}
            </button>
          </form>
        )}
      </section>

      {/* ── Admin: voice templates ── */}
      {isAdmin && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">📋 Plantillas de voz</h2>
            <button
              onClick={() => setEditingTemplate({ ...emptyTemplate })}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
            >
              + Nueva plantilla
            </button>
          </div>

          {templatesLoading && <p className="text-sm text-gray-500">Cargando…</p>}
          {templateError && <p className="text-sm text-red-600 mb-3">{templateError}</p>}

          {/* Template list */}
          {!templatesLoading && templates.length === 0 && (
            <p className="text-sm text-gray-500">No hay plantillas. Crea una para que tus asesores puedan llamar.</p>
          )}

          <div className="space-y-3">
            {templates.map((t) => (
              <div
                key={t.id}
                className="flex items-start gap-4 border border-gray-200 rounded-lg p-4 bg-white"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{t.name}</p>
                    {!t.is_active && (
                      <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                        Inactiva
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Modo: <span className="font-medium">{t.default_call_mode}</span>
                    {' · '}Max {t.max_duration_seconds}s
                    {' · '}Grabación: {t.recording_policy}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t.available_voice_ids?.length || 0} voces · {t.available_tones?.length || 0} tonos
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() =>
                      setEditingTemplate({
                        ...t,
                        available_voice_ids: Array.isArray(t.available_voice_ids)
                          ? t.available_voice_ids
                              .map((v) => (typeof v === 'string' ? v : v?.voiceId || ''))
                              .join(', ')
                          : '',
                        available_tones: Array.isArray(t.available_tones)
                          ? t.available_tones.join(', ')
                          : '',
                      })
                    }
                    className="text-xs px-2 py-1 border border-gray-300 rounded hover:bg-gray-50"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => handleDeleteTemplate(t.id)}
                    className="text-xs px-2 py-1 border border-red-200 text-red-600 rounded hover:bg-red-50"
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Template edit form */}
          {editingTemplate && (
            <div className="mt-6 border border-blue-200 rounded-lg p-5 bg-blue-50">
              <h3 className="text-sm font-semibold text-blue-900 mb-4">
                {editingTemplate.id ? 'Editar plantilla' : 'Nueva plantilla'}
              </h3>
              <form onSubmit={handleSaveTemplate} className="space-y-4 max-w-xl">
                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                    Nombre *
                  </label>
                  <input
                    required
                    type="text"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    value={editingTemplate.name}
                    onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                    Prompt de negocio (contexto para la IA)
                  </label>
                  <textarea
                    rows={4}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    value={editingTemplate.business_prompt || ''}
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, business_prompt: e.target.value || null })
                    }
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                    IDs de voces permitidas (separadas por coma)
                  </label>
                  <input
                    type="text"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    placeholder="es-ES-ElviraNeural, en-US-JennyNeural"
                    value={
                      typeof editingTemplate.available_voice_ids === 'string'
                        ? editingTemplate.available_voice_ids
                        : (editingTemplate.available_voice_ids || []).join(', ')
                    }
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, available_voice_ids: e.target.value })
                    }
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                    Tonos disponibles (separados por coma)
                  </label>
                  <input
                    type="text"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    placeholder="profesional, amigable, formal"
                    value={
                      typeof editingTemplate.available_tones === 'string'
                        ? editingTemplate.available_tones
                        : (editingTemplate.available_tones || []).join(', ')
                    }
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, available_tones: e.target.value })
                    }
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                      Modo predeterminado
                    </label>
                    <select
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      value={editingTemplate.default_call_mode}
                      onChange={(e) =>
                        setEditingTemplate({ ...editingTemplate, default_call_mode: e.target.value })
                      }
                    >
                      <option value="transcriptor">Transcriptor</option>
                      <option value="ai_agent">Agente IA</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                      Política de grabación
                    </label>
                    <select
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      value={editingTemplate.recording_policy}
                      onChange={(e) =>
                        setEditingTemplate({ ...editingTemplate, recording_policy: e.target.value })
                      }
                    >
                      <option value="enabled">Siempre grabar</option>
                      <option value="optional">Opcional</option>
                      <option value="disabled">Sin grabación</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                      Duración máx. (seg)
                    </label>
                    <input
                      type="number"
                      min={60}
                      max={7200}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      value={editingTemplate.max_duration_seconds}
                      onChange={(e) =>
                        setEditingTemplate({
                          ...editingTemplate,
                          max_duration_seconds: Number(e.target.value),
                        })
                      }
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase text-gray-500 mb-1">
                      Silencio máx. (seg)
                    </label>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      value={editingTemplate.max_silence_seconds}
                      onChange={(e) =>
                        setEditingTemplate({
                          ...editingTemplate,
                          max_silence_seconds: Number(e.target.value),
                        })
                      }
                    />
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editingTemplate.is_active}
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, is_active: e.target.checked })
                    }
                  />
                  Plantilla activa
                </label>

                <div className="flex gap-3 pt-1">
                  <button
                    type="submit"
                    disabled={templateSaving}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {templateSaving ? 'Guardando…' : 'Guardar'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingTemplate(null)}
                    className="px-4 py-2 border border-gray-300 text-sm rounded-md hover:bg-gray-50"
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            </div>
          )}
        </section>
      )}

      {/* ── Admin: assign templates to agents ── */}
      {isAdmin && (
        <section>
          <h2 className="text-base font-semibold text-gray-900 mb-4">👥 Asignar plantilla a asesores</h2>

          {agents.length === 0 && !templatesLoading && (
            <p className="text-sm text-gray-500">No hay asesores activos.</p>
          )}

          <div className="space-y-3">
            {agents.map((agent) => {
              const state = assignState[agent.id] || {};
              return (
                <div
                  key={agent.id}
                  className="flex items-center gap-4 border border-gray-200 rounded-lg p-4 bg-white"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{agent.name}</p>
                    <p className="text-xs text-gray-500 truncate">{agent.email}</p>
                  </div>
                  <select
                    className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={state.templateId ?? ''}
                    onChange={(e) =>
                      setAssignState((s) => ({
                        ...s,
                        [agent.id]: { ...s[agent.id], templateId: e.target.value },
                      }))
                    }
                  >
                    <option value="">— Seleccionar plantilla —</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleAssignTemplate(agent.id, state.templateId)}
                    disabled={!state.templateId || state.saving}
                    className="px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 shrink-0"
                  >
                    {state.saving ? '…' : 'Asignar'}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
