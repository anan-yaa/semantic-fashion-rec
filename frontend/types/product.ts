/**
 * Product types for API responses and component props
 */

export interface Product {
  id: string
  external_product_id: string
  name: string
  category: string | null
  subcategory: string | null
  gender: string | null
  color: string | null
  style: string | null
  season: string | null
  price: number | null
  currency: string
  availability: boolean
}

export interface PaginatedProductResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
