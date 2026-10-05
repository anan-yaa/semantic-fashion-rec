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
  article_type: 'Shirts',
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

  it('renders the product type on the tile', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText('Shirts')).toBeInTheDocument()
  })

  it('falls back to subcategory when product type is missing', () => {
    render(<ProductCard product={{ ...mockProduct, article_type: null }} />)
    expect(screen.getByText('Topwear')).toBeInTheDocument()
  })

  it('renders gender, color and season on one line', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText('Men · Blue · Summer')).toBeInTheDocument()
  })

  it('renders style', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText('Casual')).toBeInTheDocument()
  })

  it('renders price when present', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.getByText(/USD 45.99/)).toBeInTheDocument()
  })

  it('does not label available products', () => {
    render(<ProductCard product={mockProduct} />)
    expect(screen.queryByText('Available')).not.toBeInTheDocument()
  })

  it('shows unavailable when availability is false', () => {
    render(<ProductCard product={{ ...mockProduct, availability: false }} />)
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
  })

  it('handles missing optional fields', () => {
    const minimalProduct: Product = {
      ...mockProduct,
      article_type: null,
      gender: null,
      color: null,
      style: null,
      season: null,
      price: null,
    }
    render(<ProductCard product={minimalProduct} />)
    expect(screen.getByText('Blue Cotton Shirt')).toBeInTheDocument()
    expect(screen.queryByText(/Price/)).not.toBeInTheDocument()
  })
})
