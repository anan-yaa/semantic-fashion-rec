/**
 * ProductGrid: Displays multiple products in a responsive grid
 */

import { Product } from '@/types/product'
import { ProductCard } from './ProductCard'

interface ProductGridProps {
  products: Product[]
  isLoading?: boolean
}

const GRID = 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4'

export function ProductGrid({ products, isLoading = false }: ProductGridProps) {
  if (isLoading) {
    return (
      <div className={GRID} aria-busy="true">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="border border-border rounded-xl overflow-hidden animate-pulse bg-white">
            <div className="h-32 bg-hover" />
            <div className="p-4 space-y-2">
              <div className="h-3 bg-hover rounded w-1/3" />
              <div className="h-4 bg-hover rounded w-5/6" />
              <div className="h-3 bg-hover rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (products.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-lg text-primary">No products found</p>
        <p className="mt-1 text-sm text-secondary">Try describing it differently, or pick one of the examples above.</p>
      </div>
    )
  }

  return (
    <div className={GRID}>
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}
