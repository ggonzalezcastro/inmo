import { useEffect, useState } from 'react';
import { useTicketStore } from '../store/ticketStore';

/**
 * CallWidget - Modal for managing voice calls
 * 
 * Features:
 * - Show call duration
 * - Real-time transcript
 * - AI summary after call
 * - Extracted data display
 * - Score change
 * - Option to advance stage
 */
export default function CallWidget({ leadId, callId, onClose, onComplete }) {
  const { currentTicket } = useTicketStore();
  const [callData, setCallData] = useState(null);
  const [duration, setDuration] = useState(0);
  const [isActive, setIsActive] = useState(true);
  const [transcript, setTranscript] = useState([]);
  const [summary, setSummary] = useState(null);
  const [extractedData, setExtractedData] = useState(null);
  const [scoreChange, setScoreChange] = useState(null);
  const [autoAdvance, setAutoAdvance] = useState(false);

  useEffect(() => {
    // Simulate call progress
    if (isActive) {
      const interval = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [isActive]);

  useEffect(() => {
    // Fetch call data
    // This would be a real API call
    if (callId) {
      // Simulate fetching call data
      setTimeout(() => {
        setCallData({
          id: callId,
          status: 'completed',
          transcript: [
            { speaker: 'bot', text: 'Hola, ¿cómo estás?', timestamp: new Date() },
            { speaker: 'customer', text: 'Bien, gracias', timestamp: new Date() },
          ],
          summary: 'Cliente interesado en propiedad de 3 habitaciones, presupuesto $150k',
          extracted_data: {
            budget: '$150,000',
            timeline: '30 días',
            preferences: '3 habitaciones, zona norte',
          },
          score_change: 15,
        });
        setIsActive(false);
      }, 5000);
    }
  }, [callId]);

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleComplete = () => {
    onComplete?.({
      autoAdvance,
      newStage: autoAdvance ? 'calificacion_financiera' : null,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Llamada en Progreso</h3>
            {!isActive && (
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            )}
          </div>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Call Status */}
          {isActive ? (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                <svg
                  className="w-8 h-8 text-green-600 animate-pulse"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                </svg>
              </div>
              <p className="text-lg font-medium text-gray-900">Llamada en curso...</p>
              <p className="text-2xl font-bold text-blue-600 mt-2">
                {formatDuration(duration)}
              </p>
            </div>
          ) : (
            <div className="text-center py-4">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
                <svg
                  className="w-8 h-8 text-gray-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <p className="text-lg font-medium text-gray-900">Llamada finalizada</p>
              <p className="text-sm text-gray-600 mt-1">Duración: {formatDuration(duration)}</p>
            </div>
          )}

          {/* Transcript */}
          {transcript.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Transcripción</h4>
              <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto space-y-3">
                {transcript.map((entry, index) => (
                  <div
                    key={index}
                    className={`flex ${
                      entry.speaker === 'customer' ? 'justify-start' : 'justify-end'
                    }`}
                  >
                    <div
                      className={`max-w-xs px-3 py-2 rounded-lg ${
                        entry.speaker === 'customer'
                          ? 'bg-white border border-gray-200'
                          : 'bg-blue-100 text-blue-900'
                      }`}
                    >
                      <p className="text-sm">{entry.text}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Summary */}
          {summary && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Resumen IA</h4>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-gray-900">{summary}</p>
              </div>
            </div>
          )}

          {/* Extracted Data */}
          {extractedData && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Datos Extraídos</h4>
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(extractedData).map(([key, value]) => (
                    <div key={key}>
                      <span className="text-xs font-medium text-gray-700 capitalize">
                        {key}:
                      </span>{' '}
                      <span className="text-sm text-gray-900">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Score Change */}
          {scoreChange !== null && (
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-3">Cambio de Score</h4>
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">Score anterior:</span>
                <span className="text-sm font-medium text-gray-900">
                  {currentTicket?.lead?.lead_score || 0}%
                </span>
                <span className="text-sm text-gray-600">→</span>
                <span className="text-sm font-medium text-green-600">
                  {(currentTicket?.lead?.lead_score || 0) + scoreChange}%
                </span>
                <span className={`text-sm font-medium ${scoreChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  ({scoreChange >= 0 ? '+' : ''}{scoreChange})
                </span>
              </div>
            </div>
          )}

          {/* Auto Advance Option */}
          {!isActive && (
            <div className="border-t border-gray-200 pt-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={autoAdvance}
                  onChange={(e) => setAutoAdvance(e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm text-gray-700">
                  Avanzar automáticamente a la siguiente etapa
                </span>
              </label>
            </div>
          )}

          {/* Actions */}
          {!isActive && (
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cerrar
              </button>
              <button
                onClick={handleComplete}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Completar
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


