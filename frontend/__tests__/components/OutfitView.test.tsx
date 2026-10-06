import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { OutfitView } from '@/components/OutfitView'
import { OutfitSlot, Product } from '@/types/product'

const product = (id: string, name: string): Product => ({
  id,
  external_product_id: id,
  name,
  category: 'Apparel',
  subcategory: 'Topwear',
  article_type: 'Shirts',
  gender: 'Men',
  color: 'Blue',
  style: null,
  season: 'Summer',
  price: null,
  currency: 'USD',
  availability: true,
})

const slots: OutfitSlot[] = [
  { key: 'top', label: 'Top', products: [product('1', 'Beach Tee'), product('2', 'Linen Shirt')] },
  { key: 'bottom', label: 'Bottom', products: [product('3', 'Board Shorts')] },
  { key: 'footwear', label: 'Footwear', products: [] },
]

describe('OutfitView', () => {
  it('shows each filled slot with its products', () => {
    render(<OutfitView slots={slots} />)

    const top = screen.getByRole('region', { name: 'Top' })
    expect(within(top).getByText('Beach Tee')).toBeInTheDocument()
    expect(within(top).getByText('Linen Shirt')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Bottom' })).toBeInTheDocument()
  })

  it('marks only the first product of a slot as the pick', () => {
    render(<OutfitView slots={slots} />)

    const top = screen.getByRole('region', { name: 'Top' })
    expect(within(top).getAllByText('Our pick')).toHaveLength(1)
    expect(screen.getAllByText('Our pick')).toHaveLength(2)
  })

  it('leaves out slots with no products', () => {
    render(<OutfitView slots={slots} />)
    expect(screen.queryByRole('region', { name: 'Footwear' })).not.toBeInTheDocument()
  })

  it('explains when nothing matched', () => {
    render(<OutfitView slots={[{ key: 'top', label: 'Top', products: [] }]} />)
    expect(screen.getByText(/No matching items found/)).toBeInTheDocument()
  })
})
