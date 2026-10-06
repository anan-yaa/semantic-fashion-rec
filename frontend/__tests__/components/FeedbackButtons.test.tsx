import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FeedbackButtons } from '@/components/FeedbackButtons'

describe('FeedbackButtons', () => {
  it('votes good or bad', () => {
    const onVote = vi.fn()
    render(<FeedbackButtons vote={0} onVote={onVote} />)
    fireEvent.click(screen.getByRole('button', { name: 'Good result' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bad result' }))
    expect(onVote.mock.calls).toEqual([[1], [-1]])
  })

  it('clicking the active vote removes it', () => {
    const onVote = vi.fn()
    render(<FeedbackButtons vote={1} onVote={onVote} />)
    expect(screen.getByRole('button', { name: 'Good result' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Good result' }))
    expect(onVote).toHaveBeenCalledWith(0)
  })

  it('switches from bad to good', () => {
    const onVote = vi.fn()
    render(<FeedbackButtons vote={-1} onVote={onVote} />)
    fireEvent.click(screen.getByRole('button', { name: 'Good result' }))
    expect(onVote).toHaveBeenCalledWith(1)
  })
})
