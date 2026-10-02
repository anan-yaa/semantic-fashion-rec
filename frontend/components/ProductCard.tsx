/**
 * ProductCard: Individual product display
 * Shows product details in a card format
 */

import { Product } from '@/types/product'

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <div className="border border-border rounded-lg overflow-hidden hover:shadow-md hover:border-gray-400 transition-shadow">
      {/* Image Placeholder */}
      <div className="w-full h-48 bg-hover flex items-center justify-center">
        <span className="text-secondary text-sm">No image</span>
      </div>

      {/* Product Details */}
      <div className="p-4">
        <h3 className="font-semibold text-primary mb-2 line-clamp-2">{product.name}</h3>

        {/* Category */}
        {product.category && (
          <p className="text-sm text-secondary mb-2">
            {product.category}
            {product.subcategory && ` / ${product.subcategory}`}
          </p>
        )}

        {/* Attributes */}
        <div className="text-xs text-secondary space-y-1 mb-3">
          {product.gender && <p>Gender: {product.gender}</p>}
          {product.color && <p>Color: {product.color}</p>}
          {product.style && <p>Style: {product.style}</p>}
          {product.season && <p>Season: {product.season}</p>}
        </div>

        {/* Price */}
        {product.price !== null ? (
          <p className="font-semibold text-primary mb-2">
            {product.currency} {Number(product.price).toFixed(2)}
          </p>
        ) : (
          <p className="text-sm text-secondary mb-2">Price not available</p>
        )}

        {/* Availability */}
        <div className="text-xs">
          <span
            className={`px-2 py-1 rounded ${
              product.availability ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}
          >
            {product.availability ? 'Available' : 'Unavailable'}
          </span>
        </div>

        {/* Product ID */}
        <p className="text-xs text-gray-400 mt-2">ID: {product.external_product_id}</p>
      </div>
    </div>
  )
}
