import { useState, useEffect } from 'react';
import { brokerAPI } from '../services/api';

/**
 * AgentConfigTab - Configuration tab for AI Agent settings
 */
export default function AgentConfigTab({ config, onSave }) {
  const [useCustomPrompt, setUseCustomPrompt] = useState(!!config?.full_custom_prompt);
  const [formData, setFormData] = useState({
    agent_name: config?.agent_name || 'Sofía',
    agent_role: config?.agent_role || 'asesora inmobiliaria',
    identity_prompt: config?.identity_prompt || '',
    business_context: config?.business_context || '',
    agent_objective: config?.agent_objective || '',
    data_collection_prompt: config?.data_collection_prompt || '',
    behavior_rules: config?.behavior_rules || '',
    restrictions: config?.restrictions || '',
    full_custom_prompt: config?.full_custom_prompt || '',
    tools_instructions: config?.tools_instructions || '',
    enable_appointment_booking: config?.enable_appointment_booking ?? true
  });
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  // Update form data when config prop changes
  useEffect(() => {
    if (config) {
      setUseCustomPrompt(!!config.full_custom_prompt);
      setFormData({
        agent_name: config.agent_name || 'Sofía',
        agent_role: config.agent_role || 'asesora inmobiliaria',
        identity_prompt: config.identity_prompt || '',
        business_context: config.business_context || '',
        agent_objective: config.agent_objective || '',
        data_collection_prompt: config.data_collection_prompt || '',
        behavior_rules: config.behavior_rules || '',
        restrictions: config.restrictions || '',
        full_custom_prompt: config.full_custom_prompt || '',
        tools_instructions: config.tools_instructions || '',
        enable_appointment_booking: config.enable_appointment_booking ?? true
      });
    }
  }, [config]);
  
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      // Si usa custom prompt, solo enviar full_custom_prompt y enable_appointment_booking
      // Si no, enviar las secciones individuales y limpiar full_custom_prompt
      const dataToSend = useCustomPrompt 
        ? {
            full_custom_prompt: formData.full_custom_prompt,
            enable_appointment_booking: formData.enable_appointment_booking,
            // Limpiar las demás secciones ya que no se usarán
            identity_prompt: null,
            business_context: null,
            agent_objective: null,
            data_collection_prompt: null,
            behavior_rules: null,
            restrictions: null,
            tools_instructions: null
          }
        : {
            agent_name: formData.agent_name,
            agent_role: formData.agent_role,
            identity_prompt: formData.identity_prompt || null,
            business_context: formData.business_context || null,
            agent_objective: formData.agent_objective || null,
            data_collection_prompt: formData.data_collection_prompt || null,
            behavior_rules: formData.behavior_rules || null,
            restrictions: formData.restrictions || null,
            tools_instructions: formData.tools_instructions || null,
            enable_appointment_booking: formData.enable_appointment_booking,
            // Limpiar full_custom_prompt para que use las secciones
            full_custom_prompt: null
          };
      
      await brokerAPI.updatePromptConfig(dataToSend);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
      onSave?.();
    } catch (error) {
      console.error('Error saving config:', error);
      setError(error.response?.data?.detail || 'Error al guardar configuración');
    } finally {
      setSaving(false);
    }
  };
  
  const handlePreview = async () => {
    try {
      const response = await brokerAPI.getPromptPreview();
      setPreview(response.data.prompt);
      setShowPreview(true);
    } catch (error) {
      console.error('Error getting preview:', error);
      setError('Error al generar vista previa');
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-md">
          ✅ Configuración guardada correctamente
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md">
          ❌ {error}
        </div>
      )}
      
      {/* Modo de configuración */}
      <section className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">📝 Modo de Configuración</h2>
        <div className="space-y-3">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              checked={!useCustomPrompt}
              onChange={() => setUseCustomPrompt(false)}
              className="mt-1 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Usar Prompt por Defecto (Recomendado)</div>
              <p className="text-sm text-gray-600">El sistema usa el prompt profesional configurado con todas las mejores prácticas</p>
            </div>
          </label>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              checked={useCustomPrompt}
              onChange={() => setUseCustomPrompt(true)}
              className="mt-1 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <div>
              <div className="font-medium text-gray-900">Prompt Personalizado Completo</div>
              <p className="text-sm text-gray-600">Escribe tu propio prompt desde cero (solo para usuarios avanzados)</p>
            </div>
          </label>
        </div>
      </section>
      
      {useCustomPrompt ? (
        /* Modo Prompt Personalizado Completo */
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">✏️ Prompt Personalizado Completo</h2>
          <textarea
            value={formData.full_custom_prompt}
            onChange={e => setFormData({...formData, full_custom_prompt: e.target.value})}
            placeholder="Escribe tu prompt completo aquí. Este reemplazará completamente el prompt por defecto."
            rows={20}
            className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-sm text-gray-500 mt-2">
            ⚠️ Al usar un prompt personalizado, se ignoran todas las demás configuraciones de abajo.
          </p>
        </section>
      ) : (
        /* Modo Configuración por Secciones */
        <>
          {/* Identidad */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">1️⃣ Identidad del Agente</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del agente</label>
                <input
                  type="text"
                  value={formData.agent_name}
                  onChange={e => setFormData({...formData, agent_name: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: Sofía"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
                <input
                  type="text"
                  value={formData.agent_role}
                  onChange={e => setFormData({...formData, agent_role: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: asesora inmobiliaria"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Descripción de Identidad (Opcional)
              </label>
              <textarea
                value={formData.identity_prompt}
                onChange={e => setFormData({...formData, identity_prompt: e.target.value})}
                placeholder="Si quieres personalizar cómo se presenta el agente, escríbelo aquí. Si lo dejas vacío, usará: 'Eres [nombre], [rol] de tu corredora.'"
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </section>
          
          {/* Contexto */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">2️⃣ Contexto del Negocio</h2>
            <textarea
              value={formData.business_context}
              onChange={e => setFormData({...formData, business_context: e.target.value})}
              placeholder="Describe qué ofrece tu inmobiliaria, en qué zonas trabajan, qué tipo de propiedades manejan...&#10;&#10;Ej: 'Trabajamos en las principales comunas de Santiago. Nos especializamos en propiedades residenciales (casas y departamentos). Contamos con un equipo de asesores especializados.'"
              rows={5}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </section>
          
          {/* Objetivo */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">3️⃣ Objetivo del Agente</h2>
            <textarea
              value={formData.agent_objective}
              onChange={e => setFormData({...formData, agent_objective: e.target.value})}
              placeholder="Define qué debe lograr el agente en la conversación...&#10;&#10;Ej: 'Tu objetivo es completar el proceso de calificación en 5-7 intercambios, recopilando ubicación, capacidad financiera, situación crediticia y datos de contacto.'"
              rows={5}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </section>
          
          {/* Datos a Recopilar */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">4️⃣ Datos a Recopilar</h2>
            <textarea
              value={formData.data_collection_prompt}
              onChange={e => setFormData({...formData, data_collection_prompt: e.target.value})}
              placeholder="Lista los datos que el agente debe recopilar...&#10;&#10;Ej:&#10;1. NOMBRE COMPLETO&#10;2. TELÉFONO (+569...)&#10;3. EMAIL (Requerido para enviar link)&#10;4. UBICACIÓN PREFERIDA&#10;5. CAPACIDAD FINANCIERA (renta líquida mensual)"
              rows={6}
              className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </section>
          
          {/* Reglas */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">5️⃣ Reglas de Comunicación</h2>
            <textarea
              value={formData.behavior_rules}
              onChange={e => setFormData({...formData, behavior_rules: e.target.value})}
              placeholder="- Conversacional pero profesional&#10;- Directo: Máximo 2-3 oraciones por mensaje&#10;- Empático: Reconoce que hablar de dinero es sensible&#10;- NUNCA preguntes información ya recopilada&#10;- Confirma brevemente lo que ya tienes y pregunta lo que FALTA"
              rows={6}
              className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </section>
          
          {/* Restricciones */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">6️⃣ Restricciones</h2>
            <textarea
              value={formData.restrictions}
              onChange={e => setFormData({...formData, restrictions: e.target.value})}
              placeholder="- NUNCA menciones competidores&#10;- NO des precios exactos sin autorización&#10;- NO hagas promesas de aprobación&#10;- NO des asesoría legal o financiera"
              rows={5}
              className="w-full border border-gray-300 rounded-md px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </section>
          
          {/* Herramientas */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">7️⃣ Herramientas</h2>
            <label className="flex items-center gap-2 cursor-pointer mb-3">
              <input
                type="checkbox"
                checked={formData.enable_appointment_booking}
                onChange={e => setFormData({...formData, enable_appointment_booking: e.target.checked})}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm font-medium text-gray-700">
                Permitir agendar citas automáticamente
              </span>
            </label>
            
            {formData.enable_appointment_booking && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Instrucciones de Herramientas (Opcional)
                </label>
                <textarea
                  value={formData.tools_instructions}
                  onChange={e => setFormData({...formData, tools_instructions: e.target.value})}
                  placeholder="Instrucciones adicionales sobre cómo usar las herramientas de agendamiento...&#10;&#10;Ej: 'Solo agenda reuniones virtuales (Google Meet), no presenciales.'"
                  rows={3}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </section>
        </>
      )}
      
      {/* Acciones */}
      <div className="flex gap-4 pt-4 border-t border-gray-200">
        <button
          onClick={handlePreview}
          className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
        >
          👁️ Vista Previa del Prompt
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Guardando...' : '💾 Guardar Cambios'}
        </button>
      </div>
      
      {/* Modal de Preview */}
      {showPreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] overflow-auto shadow-xl">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold text-gray-900">Preview del System Prompt</h3>
                <button
                  onClick={() => setShowPreview(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <pre className="bg-gray-100 p-4 rounded text-sm whitespace-pre-wrap font-mono overflow-auto">
                {preview}
              </pre>
              <button
                onClick={() => setShowPreview(false)}
                className="mt-4 px-4 py-2 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


