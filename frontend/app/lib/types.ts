export interface Airport {
  code: string
  name: string
  city: string
  country: string
}

export interface TravelOption {
  id: number
  airline: string
  price: number
  depart_time: string
  arrival_time: string
  duration: string
  stops: number
  source_url?: string
  source_type?: SourceType
  depart_date?: string
  return_date?: string
}

export type SourceType = 'airline' | 'aggregator' | 'search'

export interface SearchParams {
  origin: string
  destination: string
  departDate: string
  returnDate: string
}

export interface SearchRequest {
  origin: string
  destination: string
  depart_date: string
  return_date: string
}

export interface SearchState {
  origin: string
  destination: string
  departDate: string
  returnDate: string
  results: TravelOption[]
  loading: boolean
  error: string
}