import { useEffect, useState } from 'react';
import { agentsAPI } from '../services/api';

/**
 * AgentsCalendarTab — Configure per-agent Google Calendar for round-robin scheduling.
 *
 * How it works:
 *   1. Admin adds the service account email as a viewer/editor in each agent's Google Calendar.
 *   2. Admin enters the agent's Gmail/Workspace email here as the "calendar_id".
 *   3. When the AI schedules a meeting, it creates the event in the agent's calendar using
 *      the service account (no OAuth required from each agent).
 */
export default function AgentsCalendarTab({ serviceAccountEmail }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [error, setError] = useState(null);

  const saEmail = serviceAccountEmail || 'service-account@your-project.iam.gserviceaccount.com';

  useEffect(() => {
    loadAgents();
  }, []);

  async function loadAgents() {
    try {
      setLoading(true);
      const res = await agentsAPI.getAll();
      setAgents(res.data || []);
    } catch (e) {
      setError('Error al cargar asesores');
    } finally {
      setLoading(false);
    }
  }

  async function saveCalendar(agent, calendarId, connected) {
    setSaving((s) => ({ ...s, [agent.id]: true }));
    try {
      await agentsAPI.setCalendar(agent.id, { calendar_id: calendarId || null, connected });
      setAgents((prev) =>
        prev.map((a) =>
          a.id === agent.id ? { ...a, calendar_id: calendarId, calendar_connected: connected } : a
        )
      );
    } catch (e) {
      alert('Error al guardar el calendario');
    } finally {
      setSaving((s) => ({ ...s, [agent.id]: false }));
    }
  }

  async function disconnectCalendar(agent) {
    setSaving((s) => ({ ...s, [agent.id]: true }));
    try {
      await agentsAPI.disconnectCalendar(agent.id);
      setAgents((prev) =>
        prev.map((a) =>
          a.id === agent.id ? { ...a, calendar_id: null, calendar_connected: false } : a
        )
      );
    } catch (e) {
      alert('Error al desconectar el calendario');
    } finally {
      setSaving((s) => ({ ...s, [agent.id]: false }));
    }
  }

  if (loading) return <div className="p-6 text-sm text-gray-500">Cargando asesores…</div>;
  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="p-6 space-y-6">
      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        <p className="font-semibold mb-1">Cómo configurar calendarios individuales</p>
        <ol className="list-decimal list-inside space-y-1 text-blue-700">
          <li>
            Cada asesor debe compartir su Google Calendar con la cuenta de servicio:
            <code className="ml-1 px-1.5 py-0.5 bg-blue-100 rounded text-xs font-mono break-all">
              {saEmail}
            </code>
          </li>
          <li>En Google Calendar → Configuración → Compartir con personas específicas → agregar el email anterior como "Hacer cambios en eventos".</li>
          <li>Ingresa abajo el email Gmail o Workspace del asesor como "Calendar ID" y activa el toggle.</li>
        </ol>
      </div>

      {/* Agent list */}
      <div className="space-y-3">
        {agents.length === 0 && (
          <p className="text-sm text-gray-500">No hay asesores activos en el broker.</p>
        )}
        {agents.map((agent) => (
          <AgentCalendarRow
            key={agent.id}
            agent={agent}
            saving={!!saving[agent.id]}
            onSave={saveCalendar}
            onDisconnect={disconnectCalendar}
          />
        ))}
      </div>
    </div>
  );
}

function AgentCalendarRow({ agent, saving, onSave, onDisconnect }) {
  const [calendarId, setCalendarId] = useState(agent.calendar_id || '');
  const [connected, setConnected] = useState(agent.calendar_connected || false);
  const [dirty, setDirty] = useState(false);

  // Sync local state when parent updates the agent prop (e.g., after save/disconnect)
  useEffect(() => {
    setCalendarId(agent.calendar_id || '');
    setConnected(agent.calendar_connected || false);
    setDirty(false);
  }, [agent.calendar_id, agent.calendar_connected]);

  function handleChange(field, value) {
    if (field === 'calendarId') setCalendarId(value);
    if (field === 'connected') setConnected(value);
    setDirty(true);
  }

  return (
    <div className="flex items-center gap-4 bg-white border border-gray-200 rounded-lg p-4">
      {/* Agent info */}
      <div className="w-40 shrink-0">
        <p className="text-sm font-medium text-gray-900 truncate">{agent.name}</p>
        <p className="text-xs text-gray-500 truncate">{agent.email}</p>
      </div>

      {/* Status badge */}
      <div className="w-28 shrink-0">
        {agent.calendar_connected ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            Conectado
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            Sin configurar
          </span>
        )}
      </div>

      {/* Calendar ID input */}
      <input
        type="email"
        placeholder="juan@gmail.com"
        value={calendarId}
        onChange={(e) => handleChange('calendarId', e.target.value)}
        className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      {/* Round-robin toggle */}
      <label className="flex items-center gap-2 shrink-0 cursor-pointer">
        <input
          type="checkbox"
          checked={connected}
          onChange={(e) => handleChange('connected', e.target.checked)}
          className="w-4 h-4 rounded text-blue-600 border-gray-300"
        />
        <span className="text-xs text-gray-600 whitespace-nowrap">Round-robin</span>
      </label>

      {/* Actions */}
      <div className="flex gap-2 shrink-0">
        <button
          disabled={!dirty || saving}
          onClick={() => { onSave(agent, calendarId, connected); setDirty(false); }}
          className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? 'Guardando…' : 'Guardar'}
        </button>
        {agent.calendar_connected && (
          <button
            disabled={saving}
            onClick={() => onDisconnect(agent)}
            className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-md hover:bg-red-50 disabled:opacity-40"
          >
            Desconectar
          </button>
        )}
      </div>
    </div>
  );
}
