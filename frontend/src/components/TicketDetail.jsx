import { useEffect, useState, useRef } from 'react';
import { useTicketStore } from '../store/ticketStore';
import { useCampaignStore } from '../store/campaignStore';
import { PIPELINE_STAGES } from '../store/pipelineStore';
import { useTicketRealtime } from '../hooks/useRealtime';

/**
 * TicketDetail - Complete ticket detail view with conversation and sidebar
 * 
 * Left panel: WhatsApp-like conversation
 * Right panel: Ticket info, custom fields, tags, actions
 * Tabs: Responder, Notas Internas, Tareas
 */
export default function TicketDetail({ leadId, onClose }) {
  const [activeTab, setActiveTab] = useState('responder');
  const [messageText, setMessageText] = useState('');
  const [noteText, setNoteText] = useState('');
  const [taskText, setTaskText] = useState('');
  const [taskDueDate, setTaskDueDate] = useState('');
  const [showVariableHints, setShowVariableHints] = useState(false);
  const [variableHintPosition, setVariableHintPosition] = useState({ top: 0, left: 0 });
  const messageInputRef = useRef(null);
  
  const {
    currentTicket,
    messages,
    notes,
    tasks,
    loading,
    error,
    fetchTicket,
    sendMessage,
    updateTicketField,
    moveToStage,
    initiateCall,
    addNote,
    addTask,
  } = useTicketStore();
  
  const { campaigns, fetchCampaigns } = useCampaignStore();

  useEffect(() => {
    if (leadId) {
      fetchTicket(leadId);
      fetchCampaigns();
    }
  }, [leadId]);

  // Real-time updates
  useTicketRealtime(leadId, (updates) => {
    if (updates) {
      // Refresh ticket data when updates are received
      fetchTicket(leadId);
    }
  });

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!messageText.trim()) return;
    
    await sendMessage(leadId, messageText, 'manual');
    setMessageText('');
  };


  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    
    await addNote(leadId, noteText);
    setNoteText('');
  };

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!taskText.trim()) return;
    
    await addTask(leadId, {
      title: taskText,
      due_date: taskDueDate || null,
      completed: false,
    });
    setTaskText('');
    setTaskDueDate('');
  };

  const handleUpdateField = async (field, value) => {
    await updateTicketField(leadId, field, value);
  };

  const handleInitiateCall = async () => {
    await initiateCall(leadId);
  };

  if (loading && !currentTicket) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-gray-500">Cargando ticket...</p>
      </div>
    );
  }

  if (error && !currentTicket) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-red-600 mb-2">Error: {error}</p>
          <button
            onClick={() => fetchTicket(leadId)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (!currentTicket) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-gray-500">No se encontró el ticket</p>
      </div>
    );
  }

  const lead = currentTicket.lead || currentTicket;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 p-4 flex-shrink-0 bg-white sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-900">
              {lead.name || 'Sin nombre'}
            </h2>
            <p className="text-sm text-gray-600">{lead.phone}</p>
            {lead.email && (
              <p className="text-xs text-gray-500">{lead.email}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="ml-4 text-gray-400 hover:text-gray-600 p-1 hover:bg-gray-100 rounded"
            aria-label="Cerrar"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Conversation (Chat completo) */}
        <div className="flex-1 flex flex-col">
          {/* Messages Thread - Chat completo con fondo mejorado */}
          <div className="flex-1 overflow-y-auto p-4 bg-gradient-to-b from-gray-50 to-gray-100">
            <div className="space-y-4 max-w-4xl mx-auto">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <p>No hay mensajes aún</p>
                  <p className="text-xs mt-2">Los mensajes aparecerán aquí cuando haya conversación con el lead</p>
                </div>
              ) : (
                messages.map((msg, index) => {
                  const isBot = msg.sender_type === 'bot' || msg.sender_type === 'ai';
                  const isAgent = msg.sender_type === 'agent' || msg.sender_type === 'manual';
                  const isCustomer = msg.sender_type === 'customer';
                  
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${isCustomer ? 'justify-start' : 'justify-end'} animate-fade-in-up`}
                      style={{
                        animationDelay: `${index * 0.05}s`,
                      }}
                    >
                      <div
                        className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl shadow-sm transition-all duration-200 hover:shadow-md ${
                          isCustomer
                            ? 'bg-white border border-gray-200 rounded-tl-sm'
                            : isBot
                            ? 'bg-gradient-to-br from-green-500 to-green-600 text-white rounded-tr-sm'
                            : 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-tr-sm'
                        }`}
                      >
                        <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.message_text || msg.text}</p>
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-opacity-20 border-current">
                          <span className={`text-xs ${isCustomer ? 'text-gray-500' : 'text-white text-opacity-80'}`}>
                            {new Date(msg.created_at || msg.timestamp).toLocaleTimeString('es-CL', {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </span>
                          <div className="flex items-center gap-2">
                            {isBot && (
                              <span className="text-xs bg-white bg-opacity-20 px-2 py-0.5 rounded-full flex items-center gap-1">
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                </svg>
                                IA
                              </span>
                            )}
                            {isAgent && (
                              <span className="text-xs bg-white bg-opacity-20 px-2 py-0.5 rounded-full flex items-center gap-1">
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                                </svg>
                                Agente
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Tabs - Mejorado con animaciones */}
          <div className="border-t border-gray-200 bg-white relative">
            <div className="flex relative">
              {/* Indicador animado de pestaña activa */}
              <div
                className="absolute bottom-0 h-0.5 bg-blue-600 transition-all duration-300 ease-in-out"
                style={{
                  width: '33.333%',
                  left: activeTab === 'responder' ? '0%' : activeTab === 'notas' ? '33.333%' : '66.666%',
                }}
              />
              
              <button
                onClick={() => setActiveTab('responder')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-all duration-200 relative ${
                  activeTab === 'responder'
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  Responder
                  {activeTab === 'responder' && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                  )}
                </span>
              </button>
              
              <button
                onClick={() => setActiveTab('notas')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-all duration-200 relative ${
                  activeTab === 'notas'
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Notas Internas
                  {activeTab === 'notas' && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                  )}
                </span>
              </button>
              
              <button
                onClick={() => setActiveTab('tareas')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-all duration-200 relative ${
                  activeTab === 'tareas'
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  Tareas
                  {activeTab === 'tareas' && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                  )}
                </span>
              </button>
            </div>
          </div>

          {/* Input Area - Con animación de entrada */}
          <div className="border-t border-gray-200 p-4 bg-white">
            <div
              key={activeTab}
              className="animate-fade-in"
              style={{ animation: 'fadeIn 0.2s ease-in' }}
            >
            {activeTab === 'responder' && (
              <form onSubmit={handleSendMessage} className="space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1 relative">
                    <textarea
                      ref={messageInputRef}
                      value={messageText}
                      onChange={(e) => {
                        setMessageText(e.target.value);
                        // Check for {{ variable pattern
                        const cursorPos = e.target.selectionStart;
                        const textBefore = e.target.value.substring(0, cursorPos);
                        const lastOpen = textBefore.lastIndexOf('{{');
                        if (lastOpen !== -1 && !textBefore.substring(lastOpen).includes('}}')) {
                          // Show variable hints
                          const rect = e.target.getBoundingClientRect();
                          setVariableHintPosition({
                            top: rect.top - 100,
                            left: rect.left + (lastOpen * 8), // Approximate
                          });
                          setShowVariableHints(true);
                        } else {
                          setShowVariableHints(false);
                        }
                      }}
                      placeholder="Escribe un mensaje o usa {{variable}}..."
                      rows={2}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    {showVariableHints && (
                      <div
                        className="absolute z-10 bg-white border border-gray-200 rounded-md shadow-lg p-2"
                        style={{
                          top: variableHintPosition.top,
                          left: variableHintPosition.left,
                        }}
                      >
                        <div className="text-xs font-medium text-gray-700 mb-1">Variables:</div>
                        <div className="space-y-1">
                          {['name', 'phone', 'email', 'budget', 'timeline', 'location'].map((varName) => (
                            <button
                              key={varName}
                              type="button"
                              onClick={() => {
                                const cursorPos = messageInputRef.current.selectionStart;
                                const textBefore = messageText.substring(0, cursorPos);
                                const lastOpen = textBefore.lastIndexOf('{{');
                                const textAfter = messageText.substring(cursorPos);
                                const newText =
                                  messageText.substring(0, lastOpen) +
                                  `{{${varName}}}` +
                                  textAfter;
                                setMessageText(newText);
                                setShowVariableHints(false);
                                messageInputRef.current.focus();
                              }}
                              className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 rounded"
                            >
                              {`{{${varName}}}`}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <button
                    type="submit"
                    disabled={!messageText.trim()}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Enviar
                  </button>
                </div>
              </form>
            )}

            {activeTab === 'notas' && (
              <form onSubmit={handleAddNote} className="space-y-2">
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Agregar nota interna..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  disabled={!noteText.trim()}
                  className="w-full px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Agregar Nota
                </button>
              </form>
            )}

            {activeTab === 'tareas' && (
              <form onSubmit={handleAddTask} className="space-y-2">
                <input
                  type="text"
                  value={taskText}
                  onChange={(e) => setTaskText(e.target.value)}
                  placeholder="Título de la tarea..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="date"
                  value={taskDueDate}
                  onChange={(e) => setTaskDueDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  disabled={!taskText.trim()}
                  className="w-full px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Agregar Tarea
                </button>
              </form>
            )}
            </div>
          </div>
        </div>

        {/* Right Panel - Sidebar (Opcional, puede ocultarse) */}
        <div className="w-80 flex-shrink-0 overflow-y-auto bg-gray-50 border-l border-gray-200 p-4 space-y-6">
          {/* Información del Ticket */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Información del Ticket</h3>
            
            <div className="space-y-3">
              {/* Estado de atención */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Estado de atención
                </label>
                <select
                  value={lead.treatment_type || ''}
                  onChange={(e) => handleUpdateField('treatment_type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Seleccionar...</option>
                  <option value="automated_telegram">Atendido por IA (Telegram)</option>
                  <option value="automated_call">Atendido por IA (Llamada)</option>
                  <option value="manual_follow_up">Atendido por Agente</option>
                  <option value="hold">No atendido</option>
                </select>
              </div>

              {/* Etapa actual */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Etapa actual
                </label>
                <select
                  value={lead.pipeline_stage || ''}
                  onChange={(e) => moveToStage(leadId, e.target.value, 'Cambio manual desde ticket')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PIPELINE_STAGES.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stage.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Puntuación */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Puntuación
                </label>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-1">
                  <div
                    className={`h-2 rounded-full ${
                      (lead.lead_score || 0) >= 70 ? 'bg-green-500' :
                      (lead.lead_score || 0) >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${lead.lead_score || 0}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>{Math.round(lead.lead_score || 0)}%</span>
                  {lead.lead_score_components && (
                    <span>
                      Base: {lead.lead_score_components.base || 0} | 
                      Comportamiento: {lead.lead_score_components.behavior || 0} | 
                      Engagement: {lead.lead_score_components.engagement || 0}
                    </span>
                  )}
                </div>
              </div>

              {/* Tipo de tratamiento */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Tipo de tratamiento
                </label>
                <select
                  value={lead.treatment_type || ''}
                  onChange={(e) => handleUpdateField('treatment_type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="automated_telegram">Automated Telegram</option>
                  <option value="automated_call">Automated Call</option>
                  <option value="manual_follow_up">Manual Follow Up</option>
                  <option value="hold">Hold</option>
                </select>
              </div>
            </div>
          </section>

          {/* Etiquetas */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Etiquetas</h3>
            <div className="flex flex-wrap gap-2">
              {(lead.tags || []).map((tag, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800"
                >
                  {tag}
                </span>
              ))}
            </div>
          </section>

          {/* Campos Personalizados */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Campos Personalizados</h3>
            <div className="space-y-2 text-sm">
              {lead.lead_metadata && Object.entries(lead.lead_metadata).map(([key, value]) => (
                <div key={key}>
                  <span className="font-medium text-gray-700 capitalize">{key}:</span>{' '}
                  <span className="text-gray-900">{String(value)}</span>
                </div>
              ))}
              {(!lead.lead_metadata || Object.keys(lead.lead_metadata).length === 0) && (
                <p className="text-gray-500 text-xs">No hay campos personalizados</p>
              )}
            </div>
          </section>

          {/* Resolución */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Resolución</h3>
            <div className="space-y-2">
              <select
                value={lead.status || ''}
                onChange={(e) => handleUpdateField('status', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="cold">En seguimiento</option>
                <option value="hot">Ganado</option>
                <option value="lost">Perdido</option>
              </select>
            </div>
          </section>

          {/* Acciones Rápidas */}
          <section>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Acciones Rápidas</h3>
            <div className="space-y-2">
              <button
                onClick={async () => {
                  const callResult = await handleInitiateCall();
                  if (callResult) {
                    // Show CallWidget - this would be managed by parent component
                    // For now, just log
                    console.log('Call initiated:', callResult);
                  }
                }}
                className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium"
              >
                Iniciar llamada IA
              </button>
              
              <select
                onChange={(e) => {
                  if (e.target.value) {
                    // Apply campaign
                    e.target.value = '';
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Enviar campaña...</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </div>
          </section>

          {/* Notas Internas */}
          {notes.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Notas Internas</h3>
              <div className="space-y-2">
                {notes.map((note) => (
                  <div key={note.id} className="p-2 bg-gray-50 rounded-md text-xs">
                    <p className="text-gray-900">{note.text || note.note}</p>
                    <p className="text-gray-500 mt-1">
                      {new Date(note.created_at || note.timestamp).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Tareas */}
          {tasks.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Tareas</h3>
              <div className="space-y-2">
                {tasks.map((task) => (
                  <div key={task.id} className="p-2 bg-gray-50 rounded-md text-xs">
                    <div className="flex items-start justify-between">
                      <p className="text-gray-900">{task.title || task.task}</p>
                      {task.completed && (
                        <span className="text-green-600">✓</span>
                      )}
                    </div>
                    {task.due_date && (
                      <p className="text-gray-500 mt-1">
                        Vence: {new Date(task.due_date).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
