import { useCostsStore } from '../store/costsStore';

export function AlertsPanel() {
  const { summary } = useCostsStore();

  if (!summary?.daily_alert) return null;

  const threshold = summary.daily_alert_threshold_usd;
  const today = summary.daily_cost_usd;

  return (
    <div
      className="mb-6 p-4 rounded-lg border bg-amber-50 border-amber-200"
      role="alert"
    >
      <p className="text-amber-800 font-medium">
        El costo de hoy (${today.toFixed(4)} USD) supera el umbral configurado (
        {threshold} USD).
      </p>
      <p className="text-amber-700 text-sm mt-1">
        Revisa el uso de llamadas LLM o ajusta el umbral en el backend (
        DAILY_COST_ALERT_USD).
      </p>
    </div>
  );
}
