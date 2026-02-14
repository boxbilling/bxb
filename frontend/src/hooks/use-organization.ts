import { useQuery } from '@tanstack/react-query'
import { organizationsApi } from '@/lib/api'

export function useOrganization() {
  return useQuery({
    queryKey: ['organization'],
    queryFn: () => organizationsApi.getCurrent(),
    staleTime: 5 * 60 * 1000,
  })
}
