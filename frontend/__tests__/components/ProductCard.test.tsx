import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProductCard } from '@/components/ProductCard'
import { Product } from '@/types/product'

const mockProduct: Product = {
  id: '1',
  external_product_id: '12345',
  name: 'Blue Cotton Shirt',
  category: 'Apparel',
  subcategory: 'Topwear',
  gender: 'Men',
  color: 'Blue',
  style: 'Casual',
  season: 'Summer',
  price: 45.99,
  currency: 'USD',
  availability: true,
}

describe('ProductCard', () => {
  it('renders product name', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText('Blue Cotton Shirt')).toBeInTheDocument()
  })

  it('renders category and subcategory', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText(/Apparel \/ Topwear/)).toBeInTheDocument()
  })

  it('renders gender', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText(/Gender: Men/)).toBeInTheDocument()
  })

  it('renders color', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText(/Color: Blue/)).toBeInTheDocument()
  })

  it('renders price', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText(/USD 45.99/)).toBeInTheDocument()
  })

  it('renders availability badge', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText('Available')).toBeInTheDocument()
  })

  it('shows unavailable when availability is false', () => {
    const unavailableProduct = { ...mockProduct, availability: false }
    render(<ProductCard product={unavailableProduct} />)
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
  })

  it('handles missing optional fields', () => {
    const minimalProduct: Product = {
      ...mockProduct,
      gender: null,
      color: null,
      style: null,
      season: null,
      price: null,
    }
    render(<ProductCard product={minimalProduct} />)
    expect(screen.getByText('Blue Cotton Shirt')).toBeInTheDocument()
  })
})
