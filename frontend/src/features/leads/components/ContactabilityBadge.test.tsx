import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ContactabilityBadge } from './ContactabilityBadge'

describe('ContactabilityBadge', () => {
  it('shows the risk level, score and evidence', () => {
    const view = render(
      <ContactabilityBadge
        showScore
        contactability={{
          score: 80,
          level: 'critical',
          reasons: ['3 intentos sin respuesta', 'Más de 7 días esperando respuesta'],
          suggested_action: 'Probar otro canal.',
          attempt_count: 3,
          unanswered_attempts: 3,
          no_answer_calls: 0,
          failed_messages: 0,
          no_shows: 0,
          last_attempt_at: '2026-08-15T12:00:00Z',
          last_response_at: null,
        }}
      />,
    )

    const badge = view.container.querySelector('[title]')
    expect(view.getByText('Crítico')).toBeTruthy()
    expect(badge?.getAttribute('title')).toContain('3 intentos sin respuesta')
  })
})
