import { useState, useEffect } from 'react';
import { brokerAPI } from '../services/api';

const FIELD_LABELS = {
  name: '👤 Nombre',
  phone: '📞 Teléfono',
  email: '✉️ Email',
  location: '📍 Ubicación',
  monthly_income: '💰 Ingresos Mensuales',
  dicom_status: '📊 Estado DICOM',
  budget: '💵 Presupuesto',
  property_type: '🏠 Tipo',
  bedrooms: '🛏️ Dormitorios',
  timeline: '📅 Plazo'
};

export default function LeadConfigTab({ config, onSave }) {
  const [weights, setWeights] = useState(config?.field_weights || {
    name: 10, phone: 15, email: 10, location: 15, 
    monthly_income: 25, dicom_status: 20, budget: 10
  });
  const [thresholds, setThresholds] = useState({
    cold_max: config?.cold_max_score || 20,
    warm_max: config?.warm_max_score || 50,
    hot_min: config?.hot_min_score || 50,
    qualified_min: config?.qualified_min_score || 75
  });
  
  // ⭐ Rangos de ingresos configurables
  const [incomeRanges, setIncomeRanges] = useState(config?.income_ranges || {
    insufficient: { min: 0, max: 500000, label: 'Insuficiente' },
    low: { min: 500000, max: 1000000, label: 'Bajo' },
    medium: { min: 1000000, max: 2000000, label: 'Medio' },
    good: { min: 2000000, max: 4000000, label: 'Bueno' },
    excellent: { min: 4000000, max: null, label: 'Excelente' },
  });
  
  // ⭐ Criterios de calificación configurables
  const [qualificationCriteria, setQualificationCriteria] = useState(
    config?.qualification_criteria || {
      calificado: {
        min_monthly_income: 1000000,
        dicom_status: ['clean'],
        max_debt_amount: 0
      },
      potencial: {
        min_monthly_income: 500000,
        dicom_status: ['clean', 'has_debt'],
        max_debt_amount: 500000
      },
      no_calificado: {
        conditions: [
          { monthly_income_below: 500000 },
          { debt_amount_above: 500000 }
        ]
      }
    }
  );
  
  const [priority, setPriority] = useState(config?.field_priority || [
    'name', 'phone', 'email', 'location', 'monthly_income', 'dicom_status', 'budget'
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  // Update form data when config prop changes
  useEffect(() => {
    if (config) {
      setWeights(config.field_weights || {
        name: 10, phone: 15, email: 10, location: 15, 
        monthly_income: 25, dicom_status: 20, budget: 10
      });
      setThresholds({
        cold_max: config.cold_max_score || 20,
        warm_max: config.warm_max_score || 50,
        hot_min: config.hot_min_score || 50,
        qualified_min: config.qualified_min_score || 75
      });
      setPriority(config.field_priority || [
        'name', 'phone', 'email', 'location', 'monthly_income', 'dicom_status', 'budget'
      ]);
      if (config.income_ranges) {
        setIncomeRanges(config.income_ranges);
      }
      if (config.qualification_criteria) {
        setQualificationCriteria(config.qualification_criteria);
      }
    }
  }, [config]);
  
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await brokerAPI.updateLeadConfig({
        field_weights: weights,
        cold_max_score: thresholds.cold_max,
        warm_max_score: thresholds.warm_max,
        hot_min_score: thresholds.hot_min,
        qualified_min_score: thresholds.qualified_min,
        field_priority: priority,
        income_ranges: incomeRanges,
        qualification_criteria: qualificationCriteria,
        max_acceptable_debt: qualificationCriteria.potencial.max_debt_amount
      });
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
  
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  
  const moveField = (index, direction) => {
    if (direction === 'up' && index > 0) {
      const newPriority = [...priority];
      [newPriority[index], newPriority[index - 1]] = 
        [newPriority[index - 1], newPriority[index]];
      setPriority(newPriority);
    } else if (direction === 'down' && index < priority.length - 1) {
      const newPriority = [...priority];
      [newPriority[index], newPriority[index + 1]] = 
        [newPriority[index + 1], newPriority[index]];
      setPriority(newPriority);
    }
  };
  
  return (
    <div className="space-y-8">
      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-md">
          ✅ Configuración guardada correctamente. Los cambios se aplicarán inmediatamente en el próximo mensaje del chat.
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md">
          ❌ {error}
        </div>
      )}
      
      {/* Pesos */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Importancia de Datos</h2>
        <p className="text-sm text-gray-500 mb-4">
          Ajusta el peso de cada dato en el score del lead
        </p>
        <div className="space-y-4 bg-gray-50 p-4 rounded-lg">
          {Object.entries(weights).map(([field, value]) => (
            <div key={field} className="flex items-center gap-4">
              <span className="w-40 text-sm font-medium text-gray-700">
                {FIELD_LABELS[field] || field}
              </span>
              <input
                type="range"
                min="0"
                max="50"
                value={value}
                onChange={e => setWeights({...weights, [field]: parseInt(e.target.value)})}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <span className="w-20 text-right text-sm font-medium text-gray-700">
                {value} pts
              </span>
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-500 mt-2">
          Total: <span className="font-semibold">{totalWeight} pts</span>
        </p>
      </section>
      
      {/* Umbrales */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Umbrales de Score (Temperatura del Lead)</h2>
        <div className="bg-gray-50 p-6 rounded-lg">
          <div className="flex items-center justify-between mb-6">
            <span className="text-blue-600 font-medium">🔵 COLD</span>
            <span className="text-yellow-600 font-medium">🟡 WARM</span>
            <span className="text-orange-600 font-medium">🟠 HOT</span>
            <span className="text-green-600 font-medium">🟢 QUALIFIED</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">COLD hasta:</label>
              <input
                type="number"
                min="0"
                max="100"
                value={thresholds.cold_max}
                onChange={e => setThresholds({...thresholds, cold_max: parseInt(e.target.value) || 0})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">WARM hasta:</label>
              <input
                type="number"
                min="0"
                max="100"
                value={thresholds.warm_max}
                onChange={e => setThresholds({...thresholds, warm_max: parseInt(e.target.value) || 0})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">HOT desde:</label>
              <input
                type="number"
                min="0"
                max="100"
                value={thresholds.hot_min}
                onChange={e => setThresholds({...thresholds, hot_min: parseInt(e.target.value) || 0})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">QUALIFIED desde:</label>
            <input
              type="number"
              min="0"
              max="100"
              value={thresholds.qualified_min}
              onChange={e => setThresholds({...thresholds, qualified_min: parseInt(e.target.value) || 0})}
              className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </section>
      
      {/* ⭐ Rangos de Ingresos */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">⭐ Rangos de Ingresos (Configurable)</h2>
        <p className="text-sm text-gray-500 mb-4">
          Define los rangos de ingreso mensual para tu mercado
        </p>
        <div className="space-y-3 bg-gray-50 p-4 rounded-lg">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-red-50 p-3 rounded border border-red-200">
            <span className="font-medium text-red-700">🔴 Insuficiente:</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">$0 - $</span>
              <input
                type="number"
                value={incomeRanges.insufficient.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  insufficient: {...incomeRanges.insufficient, max: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-yellow-50 p-3 rounded border border-yellow-200">
            <span className="font-medium text-yellow-700">🟡 Bajo:</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={incomeRanges.low.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  low: {...incomeRanges.low, min: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">- $</span>
              <input
                type="number"
                value={incomeRanges.low.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  low: {...incomeRanges.low, max: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-green-50 p-3 rounded border border-green-200">
            <span className="font-medium text-green-700">🟢 Medio:</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={incomeRanges.medium.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  medium: {...incomeRanges.medium, min: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">- $</span>
              <input
                type="number"
                value={incomeRanges.medium.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  medium: {...incomeRanges.medium, max: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-green-100 p-3 rounded border border-green-300">
            <span className="font-medium text-green-800">🟢 Bueno:</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={incomeRanges.good.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  good: {...incomeRanges.good, min: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">- $</span>
              <input
                type="number"
                value={incomeRanges.good.max}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  good: {...incomeRanges.good, max: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-blue-50 p-3 rounded border border-blue-200">
            <span className="font-medium text-blue-700">⭐ Excelente:</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={incomeRanges.excellent.min}
                onChange={e => setIncomeRanges({
                  ...incomeRanges,
                  excellent: {...incomeRanges.excellent, min: parseInt(e.target.value) || 0}
                })}
                className="w-32 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">+</span>
            </div>
          </div>
        </div>
      </section>
      
      {/* ⭐ Criterios de Calificación */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">⭐ Criterios de Calificación Financiera</h2>
        <p className="text-sm text-gray-500 mb-4">
          Define qué hace que un lead sea CALIFICADO, POTENCIAL o NO CALIFICADO
        </p>
        
        {/* CALIFICADO */}
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <h3 className="font-semibold text-green-700 mb-3">✅ CALIFICADO (Listo para agendar)</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Ingreso mínimo:</label>
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={qualificationCriteria.calificado.min_monthly_income}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  calificado: {
                    ...qualificationCriteria.calificado,
                    min_monthly_income: parseInt(e.target.value) || 0
                  }
                })}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">/ mes</span>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Estado DICOM:</label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={qualificationCriteria.calificado.dicom_status.includes('clean')}
                  onChange={e => {
                    const newStatuses = e.target.checked 
                      ? [...qualificationCriteria.calificado.dicom_status, 'clean']
                      : qualificationCriteria.calificado.dicom_status.filter(s => s !== 'clean');
                    setQualificationCriteria({
                      ...qualificationCriteria,
                      calificado: {...qualificationCriteria.calificado, dicom_status: newStatuses}
                    });
                  }}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Limpio</span>
              </label>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Deuda máxima:</label>
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={qualificationCriteria.calificado.max_debt_amount}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  calificado: {
                    ...qualificationCriteria.calificado,
                    max_debt_amount: parseInt(e.target.value) || 0
                  }
                })}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
        
        {/* POTENCIAL */}
        <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <h3 className="font-semibold text-yellow-700 mb-3">⚠️ POTENCIAL (Seguimiento futuro)</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Ingreso mínimo:</label>
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={qualificationCriteria.potencial.min_monthly_income}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  potencial: {
                    ...qualificationCriteria.potencial,
                    min_monthly_income: parseInt(e.target.value) || 0
                  }
                })}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">/ mes</span>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Estado DICOM:</label>
              <label className="flex items-center gap-2 mr-4">
                <input
                  type="checkbox"
                  checked={qualificationCriteria.potencial.dicom_status.includes('clean')}
                  onChange={e => {
                    const newStatuses = e.target.checked 
                      ? [...qualificationCriteria.potencial.dicom_status, 'clean']
                      : qualificationCriteria.potencial.dicom_status.filter(s => s !== 'clean');
                    setQualificationCriteria({
                      ...qualificationCriteria,
                      potencial: {...qualificationCriteria.potencial, dicom_status: newStatuses}
                    });
                  }}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Limpio</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={qualificationCriteria.potencial.dicom_status.includes('has_debt')}
                  onChange={e => {
                    const newStatuses = e.target.checked 
                      ? [...qualificationCriteria.potencial.dicom_status, 'has_debt']
                      : qualificationCriteria.potencial.dicom_status.filter(s => s !== 'has_debt');
                    setQualificationCriteria({
                      ...qualificationCriteria,
                      potencial: {...qualificationCriteria.potencial, dicom_status: newStatuses}
                    });
                  }}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Con deuda manejable</span>
              </label>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700">Deuda máxima:</label>
              <span className="text-sm text-gray-600">$</span>
              <input
                type="number"
                value={qualificationCriteria.potencial.max_debt_amount}
                onChange={e => setQualificationCriteria({
                  ...qualificationCriteria,
                  potencial: {
                    ...qualificationCriteria.potencial,
                    max_debt_amount: parseInt(e.target.value) || 0
                  }
                })}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
        
        {/* NO CALIFICADO */}
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <h3 className="font-semibold text-red-700 mb-3">❌ NO CALIFICADO (Condiciones de rechazo automático)</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-4">
              <input 
                type="checkbox" 
                checked 
                readOnly
                className="w-4 h-4 text-blue-600 border-gray-300 rounded"
              />
              <span className="text-sm text-gray-700">Ingreso menor a: $</span>
              <input
                type="number"
                value={qualificationCriteria.no_calificado.conditions[0]?.monthly_income_below || 500000}
                onChange={e => {
                  const newConditions = [...qualificationCriteria.no_calificado.conditions];
                  newConditions[0] = { monthly_income_below: parseInt(e.target.value) || 0 };
                  setQualificationCriteria({
                    ...qualificationCriteria,
                    no_calificado: { conditions: newConditions }
                  });
                }}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">/ mes</span>
            </label>
            
            <label className="flex items-center gap-4">
              <input 
                type="checkbox" 
                checked 
                readOnly
                className="w-4 h-4 text-blue-600 border-gray-300 rounded"
              />
              <span className="text-sm text-gray-700">Deuda mayor a: $</span>
              <input
                type="number"
                value={qualificationCriteria.no_calificado.conditions[1]?.debt_amount_above || 500000}
                onChange={e => {
                  const newConditions = [...qualificationCriteria.no_calificado.conditions];
                  newConditions[1] = { debt_amount_above: parseInt(e.target.value) || 0 };
                  setQualificationCriteria({
                    ...qualificationCriteria,
                    no_calificado: { conditions: newConditions }
                  });
                }}
                className="w-40 border border-gray-300 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </label>
          </div>
        </div>
      </section>
      
      {/* Prioridad */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Prioridad de Preguntas</h2>
        <p className="text-sm text-gray-500 mb-4">
          Orden en que el agente preguntará los datos (arrastra o usa las flechas)
        </p>
        <div className="space-y-2 bg-gray-50 p-4 rounded-lg">
          {priority.map((field, index) => (
            <div 
              key={field}
              className="flex items-center gap-3 bg-white p-3 rounded-md border border-gray-200"
            >
              <span className="text-gray-400 text-xl">≡</span>
              <span className="w-8 text-sm font-medium text-gray-600">{index + 1}.</span>
              <span className="flex-1 text-sm font-medium text-gray-900">
                {FIELD_LABELS[field] || field}
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => moveField(index, 'up')}
                  disabled={index === 0}
                  className="px-2 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Mover arriba"
                >
                  ↑
                </button>
                <button
                  onClick={() => moveField(index, 'down')}
                  disabled={index === priority.length - 1}
                  className="px-2 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="Mover abajo"
                >
                  ↓
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
      
      {/* Guardar */}
      <div className="pt-4 border-t border-gray-200">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Guardando...' : 'Guardar Cambios'}
        </button>
      </div>
    </div>
  );
}


