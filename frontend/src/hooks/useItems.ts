import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import client from "@/lib/api"
import type { components } from "@/lib/schema"

type ItemResponse = components["schemas"]["ItemResponse"]
type ItemCreate = components["schemas"]["ItemCreate"]
type ItemUpdate = components["schemas"]["ItemUpdate"]

export function useItems() {
  return useQuery({
    queryKey: ["items"],
    queryFn: async () => {
      const { data } = await client.GET("/items/")
      return data ?? []
    },
  })
}

export function useCreateItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ItemCreate) => {
      const { data, error } = await client.POST("/items/", { body })
      if (error) throw error
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
  })
}

export function useUpdateItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ItemUpdate }) => {
      const { data, error } = await client.PUT("/items/{item_id}", {
        params: { path: { item_id: id } },
        body,
      })
      if (error) throw error
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
  })
}

export function useDeleteItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { error } = await client.DELETE("/items/{item_id}", {
        params: { path: { item_id: id } },
      })
      if (error) throw error
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
  })
}
