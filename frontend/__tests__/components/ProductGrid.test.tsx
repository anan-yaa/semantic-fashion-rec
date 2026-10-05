import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProductGrid } from '@/components/ProductGrid'
import { Product } from '@/types/product'

const mockProducts: Product[] = [
  {
    id: '1',
    external_product_id: '1',
    name: 'Product 1',
    category: 'Category A',
    subcategory: null,
    article_type: null,
    gender: null,
    color: null,
    style: null,
    season: null,
    price: null,
    currency: 'USD',
    availability: true,
  },
  {
    id: '2',
    external_product_id: '2',
    name: 'Product 2',
    category: 'Category B',
    subcategory: null,
    article_type: null,
    gender: null,
    color: null,
    style: null,
    season: null,
    price: null,
    currency: 'USD',
    availability: false,
  },
]

describe('ProductGrid', () => {
  it('renders multiple products', () => {
    render(<ProductGrid products={mockProducts} />)
    expect(screen.getByText('Product 1')).toBeInTheDocument()
    expect(screen.getByText('Product 2')).toBeInTheDocument()
  })

  it('shows loading skeletons when isLoading is true', () => {
    const { container } = render(<ProductGrid products={[]} isLoading={true} />)
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows empty state when no products', () => {
    render(<ProductGrid products={[]} />)
    expect(screen.getByText('No products found')).toBeInTheDocument()
  })

  it('renders correct number of product cards', () => {
    render(<ProductGrid products={mockProducts} />)
    expect(screen.getAllByRole('article')).toHaveLength(mockProducts.length)
  })
})
