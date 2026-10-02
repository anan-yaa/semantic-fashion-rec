/**
 * ProductGrid: Displays multiple products in a responsive grid
 */

import { Product } from '@/types/product'
import { ProductCard } from './ProductCard'

interface ProductGridProps {
  products: Product[]
  isLoading?: boolean
}

export function ProductGrid({ products, isLoading = false }: ProductGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 24 }).map((_, i) => (
          <div key={i} className="border border-border rounded-lg overflow-hidden animate-pulse">
            <div className="w-full h-48 bg-hover"></div>
            <div className="p-4 space-y-2">
              <div className="h-4 bg-hover rounded w-3/4"></div>
              <div className="h-3 bg-hover rounded w-1/2"></div>
              <div className="h-3 bg-hover rounded w-2/3"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (products.length === 0) {
    return (
      <div className="py-12 text-center">
        <p className="text-secondary text-lg">No products found</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}
