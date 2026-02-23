import { costsAPI } from '../../../services/api';
import type {
  CostSummary,
  CostDailyResponse,
  CostOutliersResponse,
  CostPeriod,
  CostByBrokerResponse,
  CostCallsPage,
} from '../types/costs.types';

export type { CostSummary, CostDailyResponse, CostOutliersResponse, CostPeriod };

export interface CostSummaryParams {
  period?: CostPeriod;
  broker_id?: number | null;
}

export interface CostDailyParams {
  period?: CostPeriod;
  broker_id?: number | null;
}

export interface CostOutliersParams {
  period?: CostPeriod;
  broker_id?: number | null;
  limit?: number;
}

/** Fetch cost summary for the given period and optional broker */
export async function getSummary(
  params: CostSummaryParams = {}
): Promise<CostSummary> {
  const { data } = await costsAPI.getSummary(params);
  return data as CostSummary;
}

/** Fetch daily cost breakdown for charts */
export async function getDaily(
  params: CostDailyParams = {}
): Promise<CostDailyResponse> {
  const { data } = await costsAPI.getDaily(params);
  return data as CostDailyResponse;
}

/** Fetch top expensive leads (outliers) */
export async function getOutliers(
  params: CostOutliersParams = {}
): Promise<CostOutliersResponse> {
  const { data } = await costsAPI.getOutliers(params);
  return data as CostOutliersResponse;
}

/** Download CSV export; returns blob and suggested filename */
export async function exportCsv(
  period: CostPeriod = 'month',
  brokerId?: number | null
): Promise<{ blob: Blob; filename: string }> {
  const params: Record<string, string | number> = { period };
  if (brokerId != null) params.broker_id = brokerId;
  const { data, headers } = await costsAPI.exportCsv(params);
  const blob = data as Blob;
  const disposition = headers?.['content-disposition'];
  const filename =
    (typeof disposition === 'string' &&
      /filename=(?:"([^"]+)"|([^;\s]+))/.exec(disposition)?.[1]?.replace(/^"|"$/g, '')) ||
    `llm_costs_${period}.csv`;
  return { blob, filename };
}

/** Fetch cost by broker (SUPERADMIN only) */
export async function getByBroker(
  period: CostPeriod = 'month'
): Promise<CostByBrokerResponse> {
  const { data } = await costsAPI.getByBroker({ period });
  return data as CostByBrokerResponse;
}

/** Fetch paginated calls */
export async function getCalls(params: {
  page?: number;
  limit?: number;
  provider?: string;
  broker_id?: number | null;
  from?: string;
  to?: string;
  lead_id?: number | null;
  status?: string;
}): Promise<CostCallsPage> {
  const { data } = await costsAPI.getCalls(params);
  return data as CostCallsPage;
}
