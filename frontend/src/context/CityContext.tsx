'use client'

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type { City } from '@/lib/types'
import { api } from '@/lib/api'

interface CityContextValue {
  city: City | null
  cities: City[]
  setCity: (city: City) => void
  loading: boolean
}

const CityContext = createContext<CityContextValue>({
  city: null,
  cities: [],
  setCity: () => {},
  loading: true,
})

const FALLBACK_CITIES: City[] = [
  { id: 'astana', name: 'Астана', center: [51.1801, 71.446], zoom: 12 },
]

export function CityProvider({ children }: { children: ReactNode }) {
  const [cities, setCities] = useState<City[]>(FALLBACK_CITIES)
  const [city, setCity] = useState<City | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    api.cities.list()
      .then(async (data) => {
        if (!data.length) return FALLBACK_CITIES
        const detailedCities = await Promise.all(
          data.map(async (item) => {
            try {
              return await api.cities.get(item.id)
            } catch {
              return null
            }
          })
        )
        return detailedCities.filter((item): item is City => item !== null)
      })
      .then((data) => {
        if (cancelled) return
        const nextCities = data.length ? data : FALLBACK_CITIES
        setCities(nextCities)
        setCity(nextCities[0] ?? FALLBACK_CITIES[0])
      })
      .catch(() => {
        if (cancelled) return
        setCities(FALLBACK_CITIES)
        setCity(FALLBACK_CITIES[0])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <CityContext.Provider value={{ city, cities, setCity, loading }}>
      {children}
    </CityContext.Provider>
  )
}

export function useCity() {
  return useContext(CityContext)
}
