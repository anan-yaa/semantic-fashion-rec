/**
 * ProductCard: Individual product display
 * The catalogue has no images, so the top tile shows the product type on a
 * tint of the product's own color.
 */

import { Product } from '@/types/product'
import { swatchBackground, tileBackground } from '@/lib/colors'

interface ProductCardProps {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const typeLabel = product.article_type ?? product.subcategory ?? product.category
  const details = [product.gender, product.color, product.season].filter(Boolean).join(' · ')

  return (
    <article
      className="group flex flex-col bg-white border border-border rounded-xl overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg hover:border-stone-300"
      title={`Product ${product.external_product_id}`}
    >
      <div
        className="relative h-32 flex flex-col items-center justify-center gap-2"
        style={{ background: tileBackground(product.color) }}
      >
        <span
          className="h-8 w-8 rounded-full ring-1 ring-black/10 shadow-sm"
          style={{ background: swatchBackground(product.color) }}
          aria-hidden="true"
        />
        {typeLabel && (
          <span className="text-xs font-medium uppercase tracking-wider text-primary/70">{typeLabel}</span>
        )}
        {product.style && (
          <span className="absolute top-2 right-2 text-[11px] px-2 py-0.5 rounded-full bg-white/80 text-secondary">
            {product.style}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col p-4">
        {product.category && (
          <p className="text-[11px] uppercase tracking-wide text-muted mb-1">
            {product.category}
            {product.subcategory && ` / ${product.subcategory}`}
          </p>
        )}
        <h3 className="font-medium text-primary leading-snug line-clamp-2">{product.name}</h3>
        {details && <p className="mt-2 text-sm text-secondary">{details}</p>}

        {(product.price !== null || !product.availability) && (
          <div className="mt-auto pt-3 flex items-center justify-between">
            {product.price !== null && (
              <p className="font-semibold text-primary">
                {product.currency} {Number(product.price).toFixed(2)}
              </p>
            )}
            {!product.availability && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700">Unavailable</span>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
