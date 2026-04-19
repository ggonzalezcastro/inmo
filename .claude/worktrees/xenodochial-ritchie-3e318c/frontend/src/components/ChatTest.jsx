import { useState, useEffect, useRef } from 'react';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

export default function ChatTest() {
  const { isLoggedIn } = useAuthStore();
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [leadId, setLeadId] = useState(null);
  const [leadScore, setLeadScore] = useState(0);
  const [leadStatus, setLeadStatus] = useState('cold');
  const [capturedData, setCapturedData] = useState({
    name: null,
    phone: null,
    email: null,
    budget: null,
    location: null,
    timeline: null,
    property_type: null,
    rooms: null,
    monthly_income: null,
    dicom_status: null,
    morosidad_amount: null,
  });
  const [leadInfo, setLeadInfo] = useState(null);
  const [humanMode, setHumanMode] = useState(false);
  const [agentName, setAgentName] = useState(null);
  const messagesEndRef = useRef(null);
  const lastHumanMsgIdRef = useRef(0);
  const pollingRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Poll for human agent messages as soon as leadId is known.
  // Runs at 3s intervals regardless of humanMode — detects mode change from the
  // server response so the lead's chat shows advisor messages without needing to
  // send a message first.
  useEffect(() => {
    if (!leadId) {
      clearInterval(pollingRef.current);
      return;
    }
    const poll = async () => {
      try {
        const res = await api.get(
          `/api/v1/chat/${leadId}/pending-messages?after_id=${lastHumanMsgIdRef.current}`
        );
        const { messages: newMsgs, agent_name, human_mode: serverHumanMode } = res.data;
        if (agent_name && !agentName) setAgentName(agent_name);
        // Detect human_mode transition from server (no need to wait for a send)
        if (serverHumanMode && !humanMode) setHumanMode(true);
        if (newMsgs && newMsgs.length > 0) {
          setMessages(prev => [
            ...prev,
            ...newMsgs.map(m => ({ type: 'agent', text: m.message_text, id: m.id, agentName: agent_name })),
          ]);
          lastHumanMsgIdRef.current = newMsgs[newMsgs.length - 1].id;
        }
      } catch (_) {}
    };
    poll(); // llamada inmediata
    pollingRef.current = setInterval(poll, 3000);
    return () => clearInterval(pollingRef.current);
  }, [leadId]);

  // Fetch lead data when leadId changes or after messages
  useEffect(() => {
    if (leadId) {
      fetchLeadData();
    }
  }, [leadId, messages.length]);

  const isFakePhone = (phone, leadInfo) => {
    if (!phone) return true;

    // Detectar números ficticios generados por el backend
    // 1. Placeholders de telegram/web/whatsapp
    if (phone.startsWith('telegram_')) return true;
    if (phone.startsWith('web_chat_')) return true;
    if (phone.startsWith('whatsapp_')) return true;

    // 2. Números que empiezan con +569999 (usados como placeholder)
    if (phone.startsWith('+569999')) return true;

    // 3. Si el lead tiene nombre "Test User" y tags de test, es probablemente ficticio
    if (leadInfo?.name === 'Test User' && leadInfo?.tags?.includes('test')) {
      // Verificar si el número parece aleatorio (todos los dígitos después de +569 son similares)
      const digits = phone.replace('+569', '');
      if (digits.length === 8) {
        // Si todos los dígitos son iguales o muy similares, probablemente es ficticio
        const uniqueDigits = new Set(digits.split(''));
        if (uniqueDigits.size <= 2) return true; // Muy pocos dígitos únicos = probablemente aleatorio
      }
    }

    return false;
  };

  const fetchLeadData = async () => {
    if (!leadId) return;

    try {
      const response = await api.get(`/api/v1/leads/${leadId}`);
      const lead = response.data;

      console.log('📥 Lead data received:', {
        id: lead.id,
        name: lead.name,
        phone: lead.phone,
        email: lead.email,
        metadata: lead.lead_metadata || lead.metadata,
        fullLead: lead
      });

      setLeadInfo(lead);

      // Extract captured data from lead
      // El backend puede devolver lead_metadata o metadata
      const metadata = lead.lead_metadata || lead.metadata || {};

      // También buscar en last_analysis dentro de metadata
      const lastAnalysis = metadata.last_analysis || {};

      console.log('🔍 Extracted metadata:', metadata);
      console.log('🔍 Last analysis:', lastAnalysis);

      // Detectar teléfono real (no placeholder)
      let phone = lead.phone || null;
      if (phone && isFakePhone(phone, lead)) {
        phone = null;
      }
      // Si hay un teléfono en el análisis, usarlo
      if (!phone && lastAnalysis.phone) {
        phone = lastAnalysis.phone;
      }

      // Detectar nombre real (no "Test User")
      let name = lead.name || null;
      if (name === 'Test User' || name === 'User') {
        name = null;
      }
      // Si hay un nombre en el análisis, usarlo
      if (!name && lastAnalysis.name) {
        name = lastAnalysis.name;
      }

      // Email
      let email = lead.email || null;
      if (!email && lastAnalysis.email) {
        email = lastAnalysis.email;
      }

      // Budget - buscar en metadata y last_analysis
      const budget = metadata.budget || metadata.presupuesto || lastAnalysis.budget || null;

      // Location - buscar en metadata y last_analysis
      const location = metadata.location || metadata.ubicacion || lastAnalysis.location || null;

      // Timeline
      const timeline = metadata.timeline || metadata.tiempo || lastAnalysis.timeline || null;

      // Property type
      const property_type = metadata.property_type || metadata.tipo_inmueble || lastAnalysis.property_type || null;

      // Rooms
      const rooms = metadata.rooms || metadata.habitaciones || lastAnalysis.rooms || null;

      // Financial Data
      const monthly_income = metadata.monthly_income || metadata.salary || metadata.sueldo || lastAnalysis.salary || lastAnalysis.monthly_income || null;
      const dicom_status = metadata.dicom_status || lastAnalysis.dicom_status || null;
      const morosidad_amount = metadata.morosidad_amount || lastAnalysis.morosidad_amount || null;

      const capturedDataObj = {
        name: name,
        phone: phone,
        email: email,
        budget: budget,
        location: location,
        timeline: timeline,
        property_type: property_type,
        rooms: rooms,
        monthly_income: monthly_income,
        dicom_status: dicom_status,
        morosidad_amount: morosidad_amount,
      };

      console.log('✅ Final captured data:', capturedDataObj);

      setCapturedData(capturedDataObj);

      setLeadScore(lead.lead_score || 0);
      setLeadStatus(lead.status || 'cold');
    } catch (error) {
      console.error('❌ Error fetching lead data:', error);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || loading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');

    // Add user message to chat
    setMessages(prev => [...prev, { type: 'user', text: userMessage }]);
    setLoading(true);

    try {
      const response = await api.post('/api/v1/chat/test', {
        message: userMessage,
        lead_id: leadId
      });

      const { response: aiResponse, lead_id, lead_score, lead_status, debug_info } = response.data;

      // Update lead info
      if (!leadId && lead_id) {
        setLeadId(lead_id);
        // Refresh leads list if new lead was created
        window.dispatchEvent(new CustomEvent('leadCreated'));
      }

      // Update scores immediately
      if (lead_score !== undefined) setLeadScore(lead_score);
      if (lead_status) setLeadStatus(lead_status);

      // Detect human_mode — activate polling, suppress [human_mode] marker
      if (debug_info?.human_mode) setHumanMode(true);

      // Add AI response to chat (skip internal [human_mode] marker)
      if (aiResponse && aiResponse.trim() !== '[human_mode]') {
        setMessages(prev => [...prev, { type: 'bot', text: aiResponse }]);
      }

      // Fetch updated lead data to see captured fields
      if (lead_id) {
        // Esperar un poco más para que el backend termine de procesar y guardar
        setTimeout(() => {
          console.log('🔄 Fetching updated lead data after message...');
          fetchLeadData();
        }, 1000); // 1 segundo para asegurar que el backend guardó los datos
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        type: 'bot',
        text: 'Lo siento, hubo un error procesando tu mensaje. Por favor intenta de nuevo.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      cold: 'bg-blue-100 text-blue-800',
      warm: 'bg-yellow-100 text-yellow-800',
      hot: 'bg-red-100 text-red-800',
    };
    return colors[status] || colors.cold;
  };

  const getDataStatus = (value) => {
    return value ? '✅' : '❌';
  };

  const getDataValue = (value) => {
    return value || 'No capturado';
  };

  return (
    <div className="flex h-full bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header — WhatsApp style */}
        <div className="flex items-center gap-3 px-4 py-3 flex-shrink-0" style={{ background: '#075E54' }}>
          {/* Avatar */}
          <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-base flex-shrink-0"
               style={{ background: '#128C7E' }}>
            {humanMode ? '👤' : '🤖'}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-white font-semibold text-base leading-tight truncate">
              {humanMode ? (agentName || 'Agente Humano') : 'Sofía — Asesora IA'}
            </h3>
            <p className="text-xs leading-tight" style={{ color: '#ACE2DC' }}>
              {humanMode ? '🟢 Agente en línea' : '🤖 Asistente inmobiliario'}
            </p>
          </div>
          {leadId && (
            <div className="flex gap-2 flex-shrink-0">
              <span className="text-xs px-2 py-1 rounded-full font-medium" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff' }}>
                #{leadId}
              </span>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${getStatusColor(leadStatus)}`}>
                {Math.round(leadScore)}/100
              </span>
            </div>
          )}
        </div>

        {/* Human mode banner */}
        {humanMode && (
          <div className="flex items-center gap-2 px-4 py-2 text-xs font-medium flex-shrink-0"
               style={{ background: '#FFF3CD', borderBottom: '1px solid #FFEAA7', color: '#856404' }}>
            <span>👤</span>
            <span>
              <strong>{agentName || 'Un agente'}</strong> tomó el control de la conversación
            </span>
          </div>
        )}

        {/* Messages — WhatsApp background */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1"
             style={{ background: '#ECE5DD', backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")" }}>
          {messages.length === 0 && (
            <div className="text-center mt-8">
              <div className="inline-block px-4 py-2 rounded-lg text-sm" style={{ background: 'rgba(255,255,255,0.7)', color: '#667781' }}>
                🔒 Los mensajes son seguros con cifrado de extremo a extremo
              </div>
              <p className="text-sm mt-4" style={{ color: '#667781' }}>Escribe un mensaje para comenzar</p>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isUser = msg.type === 'user';
            const isAgent = msg.type === 'agent';
            const isBot = msg.type === 'bot';
            const displayName = isAgent ? (msg.agentName || agentName || 'Agente') : 'Sofía';

            // Date separator (simplified — show once)
            return (
              <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-1`}>
                {/* Avatar for bot/agent messages */}
                {!isUser && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold mr-1 mt-auto"
                       style={{ background: isAgent ? '#128C7E' : '#25D366', fontSize: '14px' }}>
                    {isAgent ? displayName.charAt(0).toUpperCase() : '🤖'}
                  </div>
                )}

                <div style={{ maxWidth: '70%' }}>
                  {/* Sender name for non-user messages */}
                  {!isUser && (
                    <p className="text-xs font-semibold mb-0.5 ml-1" style={{ color: isAgent ? '#075E54' : '#128C7E' }}>
                      {isAgent ? displayName : 'Sofía'}
                    </p>
                  )}

                  {/* Bubble */}
                  <div className="relative px-3 py-2 rounded-lg shadow-sm"
                       style={{
                         background: isUser ? '#DCF8C6' : '#FFFFFF',
                         borderRadius: isUser ? '12px 2px 12px 12px' : '2px 12px 12px 12px',
                         ...(isAgent && { borderLeft: '3px solid #128C7E' }),
                       }}>
                    {/* Agent badge */}
                    {isAgent && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold mb-1 px-1.5 py-0.5 rounded"
                            style={{ background: '#E7F8F5', color: '#128C7E' }}>
                        👤 Agente
                      </span>
                    )}
                    <p className="text-sm leading-relaxed" style={{ color: '#111B21', wordBreak: 'break-word' }}>
                      {msg.text}
                    </p>
                    {/* Timestamp tail */}
                    <p className="text-right text-xs mt-0.5" style={{ color: '#667781', fontSize: '10px' }}>
                      {new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}
                      {isUser && <span className="ml-1 text-blue-500">✓✓</span>}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex justify-start mb-1">
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs mr-1 mt-auto flex-shrink-0"
                   style={{ background: '#25D366', fontSize: '14px' }}>
                🤖
              </div>
              <div className="px-3 py-2 rounded-lg shadow-sm" style={{ background: '#FFFFFF', borderRadius: '2px 12px 12px 12px' }}>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#90A4AE', animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#90A4AE', animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: '#90A4AE', animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input — WhatsApp style */}
        <form onSubmit={sendMessage} className="flex items-end gap-2 p-3 flex-shrink-0" style={{ background: '#F0F2F5' }}>
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Escribe un mensaje..."
            className="flex-1 px-4 py-2.5 text-sm rounded-full focus:outline-none"
            style={{ background: '#FFFFFF', border: 'none', boxShadow: '0 1px 2px rgba(0,0,0,0.1)', color: '#111B21' }}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !inputMessage.trim()}
            className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all disabled:opacity-40"
            style={{ background: '#075E54' }}
            title="Enviar"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5" fill="white">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </form>
      </div>

      {/* Sidebar - Datos Capturados */}
      <div className="w-80 border-l border-gray-200 bg-gray-50 flex-shrink-0 flex flex-col overflow-hidden">
        <div className="bg-blue-50 border-b border-gray-200 p-3 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-semibold text-gray-900 text-sm">📊 Datos Capturados</h4>
              <p className="text-xs text-gray-600 mt-1">
                {leadId ? 'Actualizado en tiempo real' : 'Inicia una conversación para capturar datos'}
              </p>
            </div>
            {leadId && (
              <button
                onClick={() => {
                  console.log('🔍 DEBUG: Refreshing lead data manually...');
                  fetchLeadData();
                }}
                className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                title="Refrescar datos"
              >
                🔄
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {leadId ? (
            <>
              {/* Datos Básicos */}
              <div>
                <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase">Datos Básicos</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Nombre:</span>
                    <span className={`text-right ${capturedData.name ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.name)} {capturedData.name || 'Esperando que el cliente lo proporcione'}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Teléfono:</span>
                    <span className={`text-right ${capturedData.phone ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.phone)} {capturedData.phone || 'Esperando que el cliente lo proporcione'}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Email:</span>
                    <span className={`text-right ${capturedData.email ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.email)} {getDataValue(capturedData.email)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Datos Financieros */}
              <div>
                <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase">Datos Financieros</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Renta Mensual:</span>
                    <span className={`text-right ${capturedData.monthly_income ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.monthly_income)} {capturedData.monthly_income ? `$${parseInt(capturedData.monthly_income).toLocaleString('es-CL')}` : 'No capturado'}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">DICOM:</span>
                    <span className={`text-right ${capturedData.dicom_status ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.dicom_status)} {capturedData.dicom_status === 'clean' ? '✅ Limpio' : capturedData.dicom_status === 'has_debt' ? '⚠️ Con Deuda' : capturedData.dicom_status === 'unknown' ? '❓ Desconocido' : 'No capturado'}
                    </span>
                  </div>
                  {capturedData.morosidad_amount && (
                    <div className="flex items-start justify-between p-2 bg-white rounded border">
                      <span className="text-gray-600 font-medium">Monto Mora:</span>
                      <span className="text-right text-red-600 font-semibold">
                        ⚠️ ${parseInt(capturedData.morosidad_amount).toLocaleString('es-CL')}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Datos del Inmueble */}
              <div>
                <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase">Datos del Inmueble</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Presupuesto:</span>
                    <span className={`text-right ${capturedData.budget ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.budget)} {getDataValue(capturedData.budget)}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Ubicación:</span>
                    <span className={`text-right ${capturedData.location ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.location)} {getDataValue(capturedData.location)}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Timeline:</span>
                    <span className={`text-right ${capturedData.timeline ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.timeline)} {getDataValue(capturedData.timeline)}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Tipo:</span>
                    <span className={`text-right ${capturedData.property_type ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.property_type)} {getDataValue(capturedData.property_type)}
                    </span>
                  </div>
                  <div className="flex items-start justify-between p-2 bg-white rounded border">
                    <span className="text-gray-600 font-medium">Habitaciones:</span>
                    <span className={`text-right ${capturedData.rooms ? 'text-green-700 font-semibold' : 'text-gray-400'}`}>
                      {getDataStatus(capturedData.rooms)} {getDataValue(capturedData.rooms)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Progreso de Captura */}
              <div>
                <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase">Progreso de Captura</h5>
                <div className="bg-white rounded border p-3">
                  {(() => {
                    // Campos importantes para el progreso (excluyendo campos opcionales)
                    const importantFields = ['name', 'phone', 'email', 'budget', 'location', 'monthly_income', 'dicom_status'];
                    const totalImportantFields = importantFields.length;
                    const capturedImportantFields = importantFields.filter(field => {
                      const value = capturedData[field];
                      return value !== null && value !== '' && value !== undefined;
                    }).length;
                    const percentage = totalImportantFields > 0
                      ? Math.round((capturedImportantFields / totalImportantFields) * 100)
                      : 0;

                    return (
                      <>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">
                            {capturedImportantFields} de {totalImportantFields} campos principales
                          </span>
                          <span className="text-sm font-semibold text-blue-600">{percentage}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                        <div className="mt-2 text-xs text-gray-500">
                          Campos principales: Nombre, Teléfono, Email, Presupuesto, Ubicación, Renta, DICOM
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>

              {/* Metadata Raw (para debug) */}
              {leadInfo && (
                <div>
                  <h5 className="text-xs font-semibold text-gray-700 mb-2 uppercase">Debug Info</h5>
                  <div className="bg-white rounded border p-3 space-y-2">
                    <div>
                      <span className="text-xs font-semibold text-gray-700">Lead completo:</span>
                      <pre className="text-xs text-gray-600 overflow-auto max-h-40 mt-1 bg-gray-50 p-2 rounded">
                        {JSON.stringify(leadInfo, null, 2)}
                      </pre>
                    </div>
                    {leadInfo.lead_metadata || leadInfo.metadata ? (
                      <div>
                        <span className="text-xs font-semibold text-gray-700">Metadata:</span>
                        <pre className="text-xs text-gray-600 overflow-auto max-h-32 mt-1 bg-gray-50 p-2 rounded">
                          {JSON.stringify(leadInfo.lead_metadata || leadInfo.metadata, null, 2)}
                        </pre>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-500">No hay metadata</div>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-gray-500 py-8">
              <p className="text-sm">Inicia una conversación</p>
              <p className="text-xs mt-2">Los datos capturados aparecerán aquí</p>
            </div>
          )}
        </div>
      </div>
    </div >
  );
}

