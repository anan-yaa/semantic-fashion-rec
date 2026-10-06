/**
 * OutfitView: the slots of an outfit, each with a pick and alternatives
 */

import { OutfitSlot } from '@/types/product'
import { ProductCard } from './ProductCard'

interface OutfitViewProps {
  slots: OutfitSlot[]
}

export function OutfitView({ slots }: OutfitViewProps) {
  const filled = slots.filter((slot) => slot.products.length > 0)
  if (filled.length === 0) {
    return <p className="text-secondary">No matching items found. Try describing the occasion differently.</p>
  }

  return (
    <div className="space-y-10">
      {filled.map((slot) => {
        const [pick, ...alternatives] = slot.products
        return (
          <section key={slot.key} aria-label={slot.label}>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-secondary">{slot.label}</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="relative">
                <span className="absolute -top-2 left-3 z-[1] rounded-full bg-primary px-2.5 py-0.5 text-[11px] font-medium text-white">
                  Our pick
                </span>
                <div className="rounded-xl ring-2 ring-primary">
                  <ProductCard product={pick} />
                </div>
              </div>
              {alternatives.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
