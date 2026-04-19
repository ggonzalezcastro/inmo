import { apiClient } from '@/shared/lib/api-client'
import type { CalendarConnection } from '../types/calendar.types'

interface CalendarStatusResponse {
  google: { connected: boolean; email?: string }
  outlook: { connected: boolean; email?: string }
}

function statusToConnections(status: CalendarStatusResponse): CalendarConnection[] {
  return [
    {
      provider: 'google',
      connected: status.google.connected,
      email: status.google.email,
    },
    {
      provider: 'outlook',
      connected: status.outlook.connected,
      email: status.outlook.email,
    },
  ]
}

export const calendarProvidersService = {
  async getStatus(): Promise<CalendarConnection[]> {
    const data = await apiClient.get<CalendarStatusResponse>('/api/v1/agents/me/calendar/status')
    return statusToConnections(data)
  },

  async getGoogleAuthUrl(): Promise<string> {
    const data = await apiClient.get<{ auth_url: string }>(
      '/api/v1/agents/me/calendar/google/auth-url'
    )
    return data.auth_url
  },

  async getOutlookAuthUrl(): Promise<string> {
    const data = await apiClient.get<{ auth_url: string }>(
      '/api/v1/agents/me/calendar/outlook/auth-url'
    )
    return data.auth_url
  },

  async disconnectGoogle(): Promise<void> {
    return apiClient.delete('/api/v1/agents/me/calendar/google/disconnect')
  },

  async disconnectOutlook(): Promise<void> {
    return apiClient.delete('/api/v1/agents/me/calendar/outlook/disconnect')
  },
}
