import { QueryUnderstanding, SearchFilters, SearchMethod, SortOrder } from './product'

/** 1 = good result, -1 = bad result, 0 = no vote */
export type Vote = 1 | -1 | 0

export interface FeedbackContext {
  position: number
  method?: SearchMethod
  sort?: SortOrder
  filters?: SearchFilters
  understanding?: QueryUnderstanding | null
}

export interface QueryFeedback {
  query: string
  helpful: number
  not_helpful: number
}

export interface RecentFeedback {
  query: string
  product_id: string
  product_name: string
  vote: number
  position: number
  llm_used: boolean | null
  updated_at: string
}

export interface FeedbackSummary {
  total_votes: number
  helpful: number
  not_helpful: number
  helpful_rate: number | null
  queries: number
  clients: number
  most_not_helpful: QueryFeedback[]
  recent: RecentFeedback[]
}
