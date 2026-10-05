import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorState } from '@/components/ErrorState'

describe('ErrorState', () => {
  it('shows the default title and backend hint', () => {
    render(<ErrorState message="HTTP 500" />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText(/backend running/)).toBeInTheDocument()
  })

  it('can show a custom title and hide the hint (rate limiting)', () => {
    render(<ErrorState message="Try again in 5 seconds." title="You're searching too quickly" hint={null} />)
    expect(screen.getByText("You're searching too quickly")).toBeInTheDocument()
    expect(screen.queryByText(/backend running/)).not.toBeInTheDocument()
  })
})
