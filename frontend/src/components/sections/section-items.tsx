import { useState } from "react"
import { Plus, Pencil, Trash2, Loader2, Package } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useItems, useCreateItem, useUpdateItem, useDeleteItem } from "@/hooks/useItems"
import type { components } from "@/lib/schema"

type ItemResponse = components["schemas"]["ItemResponse"]

function ItemForm({
  item,
  onSubmit,
  onCancel,
  isLoading,
}: {
  item?: ItemResponse
  onSubmit: (data: { name: string; description: string; price: number; quantity: number }) => void
  onCancel: () => void
  isLoading: boolean
}) {
  const [name, setName] = useState(item?.name ?? "")
  const [description, setDescription] = useState(item?.description ?? "")
  const [price, setPrice] = useState(item?.price?.toString() ?? "")
  const [quantity, setQuantity] = useState(item?.quantity?.toString() ?? "0")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !price.trim()) return
    onSubmit({
      name: name.trim(),
      description: description.trim(),
      price: parseFloat(price),
      quantity: parseInt(quantity, 10) || 0,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="price">Price</Label>
          <Input
            id="price"
            type="number"
            step="0.01"
            min="0"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="quantity">Quantity</Label>
          <Input
            id="quantity"
            type="number"
            min="0"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading || !name.trim() || !price.trim()}>
          {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {item ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  )
}

export function SectionItems() {
  const { data: items = [], isLoading } = useItems()
  const createItem = useCreateItem()
  const updateItem = useUpdateItem()
  const deleteItem = useDeleteItem()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ItemResponse | undefined>()

  const openCreate = () => {
    setEditingItem(undefined)
    setDialogOpen(true)
  }

  const openEdit = (item: ItemResponse) => {
    setEditingItem(item)
    setDialogOpen(true)
  }

  const handleSubmit = async (data: { name: string; description: string; price: number; quantity: number }) => {
    if (editingItem) {
      await updateItem.mutateAsync({ id: editingItem.id, body: data })
      toast.success("Item updated")
    } else {
      await createItem.mutateAsync(data)
      toast.success("Item created")
    }
    setDialogOpen(false)
  }

  const handleDelete = async (item: ItemResponse) => {
    await deleteItem.mutateAsync(item.id)
    toast.success("Item deleted")
  }

  return (
    <section className="container mx-auto px-6 py-12">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-foreground">Items</h2>
        <Button onClick={openCreate} className="gap-2">
          <Plus className="w-4 h-4" />
          Add Item
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <Package className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-xl font-semibold text-foreground mb-2">No items yet</h3>
          <p className="text-muted-foreground mb-6">Create your first item to get started.</p>
          <Button onClick={openCreate} className="gap-2">
            <Plus className="w-4 h-4" />
            Add Item
          </Button>
        </div>
      ) : (
        <div className="border border-border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead className="w-[100px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.name}</TableCell>
                  <TableCell className="text-muted-foreground max-w-[300px] truncate">
                    {item.description || "-"}
                  </TableCell>
                  <TableCell className="text-right">${item.price.toFixed(2)}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(item)}
                        disabled={deleteItem.isPending}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingItem ? "Edit Item" : "New Item"}</DialogTitle>
          </DialogHeader>
          <ItemForm
            item={editingItem}
            onSubmit={handleSubmit}
            onCancel={() => setDialogOpen(false)}
            isLoading={createItem.isPending || updateItem.isPending}
          />
        </DialogContent>
      </Dialog>
    </section>
  )
}
