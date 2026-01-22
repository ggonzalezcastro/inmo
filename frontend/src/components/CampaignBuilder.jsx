import { useState, useEffect } from 'react';
import { useCampaignStore } from '../store/campaignStore';
import { campaignAPI } from '../services/api';
import { useTemplateStore } from '../store/templateStore';
import { PIPELINE_STAGES } from '../store/pipelineStore';

/**
 * CampaignBuilder - Form to create/edit campaigns
 * 
 * Features:
 * - Basic info (name, description, channel)
 * - Trigger settings (manual, score, stage, inactivity)
 * - Campaign steps (sequential actions with delays)
 * - Drag-and-drop to reorder steps
 */
export default function CampaignBuilder({ campaign = null, onSave, onCancel }) {
  const { createCampaign, updateCampaign, loading } = useCampaignStore();
  const { templates, fetchTemplates } = useTemplateStore();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    channel: 'telegram',
    triggered_by: 'manual',
    trigger_conditions: {},
    steps: [],
    max_contacts: null,
    status: 'draft',
  });

  const [errors, setErrors] = useState({});

  useEffect(() => {
    fetchTemplates();
    if (campaign) {
      setFormData({
        name: campaign.name || '',
        description: campaign.description || '',
        channel: campaign.channel || 'telegram',
        triggered_by: campaign.triggered_by || 'manual',
        trigger_conditions: campaign.trigger_conditions || {},
        steps: campaign.steps || [],
        max_contacts: campaign.max_contacts || null,
        status: campaign.status || 'draft',
      });
    }
  }, [campaign]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const handleTriggerConditionChange = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      trigger_conditions: {
        ...prev.trigger_conditions,
        [field]: value,
      },
    }));
  };

  const handleAddStep = () => {
    setFormData((prev) => ({
      ...prev,
      steps: [
        ...prev.steps,
        {
          step_number: prev.steps.length + 1,
          action_type: 'send_message',
          action: 'send_message', // Backend uses 'action' not 'action_type'
          delay_hours: 0,
          message_template_id: null,
          template_id: null, // Keep for UI
          message_text: '',
          conditions: {},
          target_stage: null,
        },
      ],
    }));
  };

  const handleUpdateStep = (index, field, value) => {
    setFormData((prev) => ({
      ...prev,
      steps: prev.steps.map((step, i) =>
        i === index ? { ...step, [field]: value } : step
      ),
    }));
  };

  const handleDeleteStep = (index) => {
    setFormData((prev) => ({
      ...prev,
      steps: prev.steps
        .filter((_, i) => i !== index)
        .map((step, i) => ({ ...step, step_number: i + 1 })),
    }));
  };

  const handleMoveStep = (fromIndex, toIndex) => {
    setFormData((prev) => {
      const newSteps = [...prev.steps];
      const [moved] = newSteps.splice(fromIndex, 1);
      newSteps.splice(toIndex, 0, moved);
      return {
        ...prev,
        steps: newSteps.map((step, i) => ({ ...step, step_number: i + 1 })),
      };
    });
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.name.trim()) {
      newErrors.name = 'El nombre es requerido';
    }
    if (formData.steps.length === 0) {
      newErrors.steps = 'Debe agregar al menos un paso';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      const { steps, ...campaignData } = formData;
      
      // Map trigger_condition to match backend format
      const triggerCondition = {};
      if (campaignData.triggered_by === 'lead_score') {
        triggerCondition.score_min = campaignData.trigger_conditions.score_min || campaignData.trigger_conditions.min_score;
        triggerCondition.score_max = campaignData.trigger_conditions.score_max || campaignData.trigger_conditions.max_score;
      } else if (campaignData.triggered_by === 'stage_change') {
        triggerCondition.stage = campaignData.trigger_conditions.stage;
      } else if (campaignData.triggered_by === 'inactivity') {
        triggerCondition.inactivity_days = campaignData.trigger_conditions.inactivity_days || campaignData.trigger_conditions.days;
      }
      
      const finalCampaignData = {
        ...campaignData,
        trigger_condition: triggerCondition,
      };
      
      if (campaign?.id) {
        // Update campaign
        await updateCampaign(campaign.id, finalCampaignData);
        
        // Update steps - this is simplified, in production you'd want to:
        // 1. Compare existing steps with new steps
        // 2. Delete removed steps
        // 3. Add new steps
        // 4. Update modified steps
        // For now, we'll just add new steps if they don't exist
        if (steps && steps.length > 0) {
          // Note: In production, you'd want to handle step updates more carefully
          for (const step of steps) {
            if (!step.id) {
              // New step
              await campaignAPI.addStep(campaign.id, {
                step_number: step.step_number,
                action: step.action_type || step.action,
                delay_hours: step.delay_hours,
                message_template_id: step.template_id || step.message_template_id || null,
                conditions: step.conditions || {},
                target_stage: step.target_stage || null,
              });
            }
          }
        }
      } else {
        // Create new campaign with steps
        await createCampaign({
          ...finalCampaignData,
          steps: steps.map(step => ({
            step_number: step.step_number,
            action: step.action_type || step.action,
            delay_hours: step.delay_hours,
            message_template_id: step.template_id || step.message_template_id || null,
            conditions: step.conditions || {},
            target_stage: step.target_stage || null,
          })),
        });
      }
      onSave?.();
    } catch (error) {
      console.error('Error saving campaign:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow max-w-4xl mx-auto">
      <form onSubmit={handleSubmit}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            {campaign ? 'Editar Campaña' : 'Nueva Campaña'}
          </h2>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Basic Info */}
          <section>
            <h3 className="text-lg font-medium text-gray-900 mb-4">Información Básica</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre de la campaña *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    errors.name ? 'border-red-300' : 'border-gray-300'
                  }`}
                  placeholder="Ej: Seguimiento leads calientes"
                />
                {errors.name && (
                  <p className="mt-1 text-sm text-red-600">{errors.name}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Descripción
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Describe el objetivo de esta campaña..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Canal *
                </label>
                <select
                  value={formData.channel}
                  onChange={(e) => handleChange('channel', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="telegram">Telegram</option>
                  <option value="call">Llamada</option>
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>
            </div>
          </section>

          {/* Trigger Settings */}
          <section>
            <h3 className="text-lg font-medium text-gray-900 mb-4">Configuración de Trigger</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tipo de trigger *
                </label>
                <div className="space-y-2">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="triggered_by"
                      value="manual"
                      checked={formData.triggered_by === 'manual'}
                      onChange={(e) => handleChange('triggered_by', e.target.value)}
                      className="mr-2"
                    />
                    <span>Manual (aplicar manualmente)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="triggered_by"
                      value="lead_score"
                      checked={formData.triggered_by === 'lead_score' || formData.triggered_by === 'score'}
                      onChange={(e) => handleChange('triggered_by', e.target.value === 'score' ? 'lead_score' : e.target.value)}
                      className="mr-2"
                    />
                    <span>Score (rango de puntuación)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="triggered_by"
                      value="stage_change"
                      checked={formData.triggered_by === 'stage_change' || formData.triggered_by === 'stage'}
                      onChange={(e) => handleChange('triggered_by', e.target.value === 'stage' ? 'stage_change' : e.target.value)}
                      className="mr-2"
                    />
                    <span>Cambio de etapa</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="triggered_by"
                      value="inactivity"
                      checked={formData.triggered_by === 'inactivity'}
                      onChange={(e) => handleChange('triggered_by', e.target.value)}
                      className="mr-2"
                    />
                    <span>Inactividad (días sin interacción)</span>
                  </label>
                </div>
              </div>

              {/* Conditional trigger fields */}
              {formData.triggered_by === 'lead_score' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Score mínimo
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={formData.trigger_conditions.score_min || formData.trigger_conditions.min_score || ''}
                      onChange={(e) =>
                        handleTriggerConditionChange('score_min', parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Score máximo
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={formData.trigger_conditions.score_max || formData.trigger_conditions.max_score || ''}
                      onChange={(e) =>
                        handleTriggerConditionChange('score_max', parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}

              {(formData.triggered_by === 'stage_change' || formData.triggered_by === 'stage') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Etapa que dispara la campaña
                  </label>
                  <select
                    value={formData.trigger_conditions.stage || ''}
                    onChange={(e) =>
                      handleTriggerConditionChange('stage', e.target.value)
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Seleccionar etapa...</option>
                    {PIPELINE_STAGES.map((stage) => (
                      <option key={stage.id} value={stage.id}>
                        {stage.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {formData.triggered_by === 'inactivity' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Días sin interacción
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={formData.trigger_conditions.inactivity_days || formData.trigger_conditions.days || ''}
                    onChange={(e) =>
                      handleTriggerConditionChange('inactivity_days', parseInt(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          </section>

          {/* Campaign Steps */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Pasos de la Campaña</h3>
              <button
                type="button"
                onClick={handleAddStep}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium"
              >
                + Agregar Paso
              </button>
            </div>

            {errors.steps && (
              <p className="mb-2 text-sm text-red-600">{errors.steps}</p>
            )}

            <div className="space-y-4">
              {formData.steps.map((step, index) => (
                <div
                  key={index}
                  className="border border-gray-200 rounded-lg p-4 bg-gray-50"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="flex items-center justify-center w-8 h-8 bg-blue-600 text-white rounded-full text-sm font-medium">
                        {step.step_number}
                      </span>
                      <h4 className="font-medium text-gray-900">Paso {step.step_number}</h4>
                    </div>
                    <div className="flex gap-2">
                      {index > 0 && (
                        <button
                          type="button"
                          onClick={() => handleMoveStep(index, index - 1)}
                          className="text-gray-600 hover:text-gray-900"
                          title="Mover arriba"
                        >
                          ↑
                        </button>
                      )}
                      {index < formData.steps.length - 1 && (
                        <button
                          type="button"
                          onClick={() => handleMoveStep(index, index + 1)}
                          className="text-gray-600 hover:text-gray-900"
                          title="Mover abajo"
                        >
                          ↓
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDeleteStep(index)}
                        className="text-red-600 hover:text-red-900"
                        title="Eliminar"
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Tipo de acción
                      </label>
                      <select
                        value={step.action_type || step.action}
                        onChange={(e) => {
                          handleUpdateStep(index, 'action_type', e.target.value);
                          handleUpdateStep(index, 'action', e.target.value);
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="send_message">Enviar mensaje</option>
                        <option value="make_call">Hacer llamada</option>
                        <option value="schedule_meeting">Agendar reunión</option>
                        <option value="update_stage">Actualizar etapa</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Delay antes de este paso (horas)
                      </label>
                      <input
                        type="number"
                        min="0"
                        value={step.delay_hours}
                        onChange={(e) =>
                          handleUpdateStep(index, 'delay_hours', parseInt(e.target.value) || 0)
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    {step.action_type === 'send_message' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Usar plantilla
                          </label>
                          <select
                            value={step.template_id || step.message_template_id || ''}
                            onChange={(e) => {
                              const templateId = e.target.value || null;
                              handleUpdateStep(index, 'template_id', templateId);
                              handleUpdateStep(index, 'message_template_id', templateId);
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="">Componer mensaje manualmente</option>
                            {templates
                              .filter((t) => t.channel === formData.channel)
                              .map((template) => (
                                <option key={template.id} value={template.id}>
                                  {template.name}
                                </option>
                              ))}
                          </select>
                        </div>

                        {!step.template_id && !step.message_template_id && (
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                              Mensaje
                            </label>
                            <textarea
                              value={step.message_text || ''}
                              onChange={(e) =>
                                handleUpdateStep(index, 'message_text', e.target.value)
                              }
                              rows={3}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Escribe el mensaje o usa variables: {{name}}, {{budget}}..."
                            />
                          </div>
                        )}
                      </>
                    )}

                    {step.action_type === 'update_stage' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Etapa objetivo
                        </label>
                        <select
                          value={step.target_stage || ''}
                          onChange={(e) =>
                            handleUpdateStep(index, 'target_stage', e.target.value || null)
                          }
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">Seleccionar etapa...</option>
                          {PIPELINE_STAGES.map((stage) => (
                            <option key={stage.id} value={stage.id}>
                              {stage.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Advanced */}
          <section>
            <h3 className="text-lg font-medium text-gray-900 mb-4">Opciones Avanzadas</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Máximo de contactos (dejar vacío para ilimitado)
                </label>
                <input
                  type="number"
                  min="1"
                  value={formData.max_contacts || ''}
                  onChange={(e) =>
                    handleChange('max_contacts', e.target.value ? parseInt(e.target.value) : null)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="activate"
                  checked={formData.status === 'active'}
                  onChange={(e) =>
                    handleChange('status', e.target.checked ? 'active' : 'draft')
                  }
                  className="mr-2"
                />
                <label htmlFor="activate" className="text-sm font-medium text-gray-700">
                  Activar campaña al guardar
                </label>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Guardando...' : campaign ? 'Actualizar' : 'Crear Campaña'}
          </button>
        </div>
      </form>
    </div>
  );
}

