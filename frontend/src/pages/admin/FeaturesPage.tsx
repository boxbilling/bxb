import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, ToggleLeft, ChevronDown, ChevronRight, Layers, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { TablePagination } from '@/components/TablePagination'
import { featuresApi, entitlementsApi, plansApi, ApiError } from '@/lib/api'
import type { Feature, FeatureCreate, Entitlement } from '@/types/billing'

const PAGE_SIZE = 20

interface FeatureFormState {
  code: string
  name: string
  description: string
  feature_type: 'boolean' | 'quantity' | 'custom'
}

const emptyFeatureForm: FeatureFormState = {
  code: '',
  name: '',
  description: '',
  feature_type: 'boolean',
}

interface EntitlementFormState {
  feature_id: string
  plan_id: string
  value: string
}

const emptyEntitlementForm: EntitlementFormState = {
  feature_id: '',
  plan_id: '',
  value: '',
}

function featureTypeBadgeVariant(type: string): 'default' | 'secondary' | 'outline' {
  switch (type) {
    case 'boolean':
      return 'default'
    case 'quantity':
      return 'secondary'
    default:
      return 'outline'
  }
}

export default function FeaturesPage() {
  const queryClient = useQueryClient()

  // Feature dialog state
  const [featureDialogOpen, setFeatureDialogOpen] = useState(false)
  const [editingFeature, setEditingFeature] = useState<Feature | null>(null)
  const [featureForm, setFeatureForm] = useState<FeatureFormState>(emptyFeatureForm)
  const [deleteFeature, setDeleteFeature] = useState<Feature | null>(null)

  // Entitlement dialog state
  const [entitlementDialogOpen, setEntitlementDialogOpen] = useState(false)
  const [entitlementForm, setEntitlementForm] = useState<EntitlementFormState>(emptyEntitlementForm)
  const [selectedPlanId, setSelectedPlanId] = useState<string>('')

  // Copy entitlements dialog state
  const [copyDialogOpen, setCopyDialogOpen] = useState(false)
  const [copySourcePlanId, setCopySourcePlanId] = useState<string>('')
  const [copyTargetPlanId, setCopyTargetPlanId] = useState<string>('')

  // Expandable rows state
  const [expandedFeatureIds, setExpandedFeatureIds] = useState<Set<string>>(new Set())

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)

  // Queries
  const { data: featuresData, isLoading: featuresLoading } = useQuery({
    queryKey: ['features', page, pageSize],
    queryFn: () => featuresApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize }),
  })

  const features = featuresData?.data
  const featuresTotalCount = featuresData?.totalCount ?? 0

  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  const { data: planCounts } = useQuery({
    queryKey: ['features', 'plan_counts'],
    queryFn: () => featuresApi.planCounts(),
  })

  const { data: entitlements, isLoading: entitlementsLoading } = useQuery({
    queryKey: ['entitlements', selectedPlanId || undefined],
    queryFn: () => entitlementsApi.list(selectedPlanId ? { plan_id: selectedPlanId } : undefined),
  })

  // Fetch all entitlements (unfiltered) for expandable rows
  const { data: allEntitlements } = useQuery({
    queryKey: ['entitlements', 'all'],
    queryFn: () => entitlementsApi.list(),
  })

  // Feature mutations
  const createFeatureMutation = useMutation({
    mutationFn: (data: FeatureCreate) => featuresApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features'] })
      toast.success('Feature created')
      setFeatureDialogOpen(false)
      setFeatureForm(emptyFeatureForm)
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create feature'
      toast.error(message)
    },
  })

  const updateFeatureMutation = useMutation({
    mutationFn: ({ code, data }: { code: string; data: { name?: string | null; description?: string | null } }) =>
      featuresApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features'] })
      toast.success('Feature updated')
      setFeatureDialogOpen(false)
      setEditingFeature(null)
      setFeatureForm(emptyFeatureForm)
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update feature'
      toast.error(message)
    },
  })

  const deleteFeatureMutation = useMutation({
    mutationFn: (code: string) => featuresApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features'] })
      queryClient.invalidateQueries({ queryKey: ['entitlements'] })
      toast.success('Feature deleted')
      setDeleteFeature(null)
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete feature'
      toast.error(message)
    },
  })

  // Entitlement mutations
  const createEntitlementMutation = useMutation({
    mutationFn: (data: { plan_id: string; feature_id: string; value: string }) =>
      entitlementsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entitlements'] })
      queryClient.invalidateQueries({ queryKey: ['features', 'plan_counts'] })
      toast.success('Entitlement created')
      setEntitlementDialogOpen(false)
      setEntitlementForm(emptyEntitlementForm)
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create entitlement'
      toast.error(message)
    },
  })

  const deleteEntitlementMutation = useMutation({
    mutationFn: (id: string) => entitlementsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entitlements'] })
      queryClient.invalidateQueries({ queryKey: ['features', 'plan_counts'] })
      toast.success('Entitlement removed')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to remove entitlement'
      toast.error(message)
    },
  })

  const copyEntitlementsMutation = useMutation({
    mutationFn: (data: { source_plan_id: string; target_plan_id: string }) =>
      entitlementsApi.copy(data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['entitlements'] })
      queryClient.invalidateQueries({ queryKey: ['features', 'plan_counts'] })
      toast.success(`Copied ${created.length} entitlement${created.length !== 1 ? 's' : ''}`)
      setCopyDialogOpen(false)
      setCopySourcePlanId('')
      setCopyTargetPlanId('')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to copy entitlements'
      toast.error(message)
    },
  })

  // Plan map for name lookups
  const planMap = new Map(plans?.map((p) => [p.id, p]) ?? [])

  // Feature helpers
  const featureMap = new Map(features?.map((f) => [f.id, f]) ?? [])

  // Build a map of feature_id -> list of entitlements (from all entitlements)
  const featureEntitlementsMap = new Map<string, Entitlement[]>()
  if (allEntitlements) {
    for (const e of allEntitlements) {
      const list = featureEntitlementsMap.get(e.feature_id) ?? []
      list.push(e)
      featureEntitlementsMap.set(e.feature_id, list)
    }
  }

  const toggleExpandFeature = (featureId: string) => {
    setExpandedFeatureIds((prev) => {
      const next = new Set(prev)
      if (next.has(featureId)) {
        next.delete(featureId)
      } else {
        next.add(featureId)
      }
      return next
    })
  }

  const openCreateFeature = () => {
    setEditingFeature(null)
    setFeatureForm(emptyFeatureForm)
    setFeatureDialogOpen(true)
  }

  const openEditFeature = (feature: Feature) => {
    setEditingFeature(feature)
    setFeatureForm({
      code: feature.code,
      name: feature.name,
      description: feature.description ?? '',
      feature_type: feature.feature_type as 'boolean' | 'quantity' | 'custom',
    })
    setFeatureDialogOpen(true)
  }

  const handleFeatureSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingFeature) {
      updateFeatureMutation.mutate({
        code: editingFeature.code,
        data: {
          name: featureForm.name,
          description: featureForm.description || null,
        },
      })
    } else {
      createFeatureMutation.mutate({
        code: featureForm.code,
        name: featureForm.name,
        description: featureForm.description || null,
        feature_type: featureForm.feature_type,
      })
    }
  }

  const openAddEntitlement = () => {
    setEntitlementForm({
      ...emptyEntitlementForm,
      plan_id: selectedPlanId,
    })
    setEntitlementDialogOpen(true)
  }

  const handleEntitlementSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createEntitlementMutation.mutate({
      plan_id: entitlementForm.plan_id,
      feature_id: entitlementForm.feature_id,
      value: entitlementForm.value,
    })
  }

  const handleCopySubmit = (e: React.FormEvent) => {
    e.preventDefault()
    copyEntitlementsMutation.mutate({
      source_plan_id: copySourcePlanId,
      target_plan_id: copyTargetPlanId,
    })
  }

  // Find feature type for selected feature in entitlement form
  const selectedEntitlementFeature = features?.find((f) => f.id === entitlementForm.feature_id)

  const isMutating = createFeatureMutation.isPending || updateFeatureMutation.isPending

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight flex items-center gap-2">
            <ToggleLeft className="h-5 w-5" />
            Features & Entitlements
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage feature flags and plan entitlements
          </p>
        </div>
        <Button onClick={openCreateFeature}>
          <Plus className="mr-2 h-4 w-4" />
          Create Feature
        </Button>
      </div>

      {/* Tabbed Layout */}
      <Tabs defaultValue="features">
        <TabsList>
          <TabsTrigger value="features">Features</TabsTrigger>
          <TabsTrigger value="entitlements">Plan Entitlements</TabsTrigger>
        </TabsList>

        {/* Features Tab */}
        <TabsContent value="features">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]"></TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Plans</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {featuresLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    </TableRow>
                  ))
                ) : !features?.length ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                      No features defined yet. Create one to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  features.map((feature) => {
                    const isExpanded = expandedFeatureIds.has(feature.id)
                    const featureEntitlements = featureEntitlementsMap.get(feature.id) ?? []
                    const featurePlanCount = planCounts?.[feature.id] ?? 0

                    return (
                      <ExpandableFeatureRow
                        key={feature.id}
                        feature={feature}
                        isExpanded={isExpanded}
                        onToggle={() => toggleExpandFeature(feature.id)}
                        planCount={featurePlanCount}
                        entitlements={featureEntitlements}
                        planMap={planMap}
                        featureMap={featureMap}
                        onEdit={() => openEditFeature(feature)}
                        onDelete={() => setDeleteFeature(feature)}
                        onDeleteEntitlement={(id) => deleteEntitlementMutation.mutate(id)}
                        deleteEntitlementPending={deleteEntitlementMutation.isPending}
                      />
                    )
                  })
                )}
              </TableBody>
            </Table>
            <TablePagination
              page={page}
              pageSize={pageSize}
              totalCount={featuresTotalCount}
              onPageChange={setPage}
              onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
            />
          </div>
        </TabsContent>

        {/* Entitlements Tab */}
        <TabsContent value="entitlements">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
                  <SelectTrigger className="w-[240px]">
                    <SelectValue placeholder="Select a plan..." />
                  </SelectTrigger>
                  <SelectContent>
                    {plans?.map((plan) => (
                      <SelectItem key={plan.id} value={plan.id}>
                        {plan.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={() => setCopyDialogOpen(true)}>
                  <Copy className="mr-2 h-4 w-4" />
                  Copy from Plan
                </Button>
                <Button variant="outline" onClick={openAddEntitlement} disabled={!selectedPlanId}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Entitlement
                </Button>
              </div>
            </div>

            {!selectedPlanId ? (
              <p className="text-sm text-muted-foreground">Select a plan to view and manage its entitlements.</p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Feature</TableHead>
                      <TableHead>Code</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Value</TableHead>
                      <TableHead className="w-[60px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entitlementsLoading ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <TableRow key={i}>
                          <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                          <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                          <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                        </TableRow>
                      ))
                    ) : !entitlements?.filter((e) => e.plan_id === selectedPlanId).length ? (
                      <TableRow>
                        <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                          No entitlements for this plan.
                        </TableCell>
                      </TableRow>
                    ) : (
                      entitlements
                        .filter((e) => e.plan_id === selectedPlanId)
                        .map((entitlement) => {
                          const feature = featureMap.get(entitlement.feature_id)
                          return (
                            <TableRow key={entitlement.id}>
                              <TableCell className="font-medium">{feature?.name ?? 'Unknown'}</TableCell>
                              <TableCell>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                  {feature?.code ?? entitlement.feature_id}
                                </code>
                              </TableCell>
                              <TableCell>
                                {feature ? (
                                  <Badge variant={featureTypeBadgeVariant(feature.feature_type)}>
                                    {feature.feature_type}
                                  </Badge>
                                ) : (
                                  '\u2014'
                                )}
                              </TableCell>
                              <TableCell>{formatEntitlementValue(entitlement.value, feature?.feature_type)}</TableCell>
                              <TableCell>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => deleteEntitlementMutation.mutate(entitlement.id)}
                                  disabled={deleteEntitlementMutation.isPending}
                                >
                                  <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          )
                        })
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Create/Edit Feature Dialog */}
      <Dialog open={featureDialogOpen} onOpenChange={setFeatureDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingFeature ? 'Edit Feature' : 'Create Feature'}</DialogTitle>
            <DialogDescription>
              {editingFeature ? 'Update the feature details.' : 'Define a new feature for your plans.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleFeatureSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="feature_code">Code *</Label>
                <Input
                  id="feature_code"
                  value={featureForm.code}
                  onChange={(e) => setFeatureForm({ ...featureForm, code: e.target.value })}
                  placeholder="e.g., advanced_analytics"
                  required
                  disabled={!!editingFeature}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="feature_name">Name *</Label>
                <Input
                  id="feature_name"
                  value={featureForm.name}
                  onChange={(e) => setFeatureForm({ ...featureForm, name: e.target.value })}
                  placeholder="e.g., Advanced Analytics"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="feature_description">Description</Label>
                <Input
                  id="feature_description"
                  value={featureForm.description}
                  onChange={(e) => setFeatureForm({ ...featureForm, description: e.target.value })}
                  placeholder="Optional description"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="feature_type">Type *</Label>
                <Select
                  value={featureForm.feature_type}
                  onValueChange={(value: 'boolean' | 'quantity' | 'custom') =>
                    setFeatureForm({ ...featureForm, feature_type: value })
                  }
                  disabled={!!editingFeature}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="quantity">Quantity</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFeatureDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isMutating}>
                {isMutating ? 'Saving...' : editingFeature ? 'Update' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Feature Confirmation */}
      <AlertDialog open={!!deleteFeature} onOpenChange={(open) => !open && setDeleteFeature(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Feature</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deleteFeature?.name}&quot;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteFeature && deleteFeatureMutation.mutate(deleteFeature.code)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Add Entitlement Dialog */}
      <Dialog open={entitlementDialogOpen} onOpenChange={setEntitlementDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Entitlement</DialogTitle>
            <DialogDescription>
              Assign a feature to a plan with a value.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEntitlementSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="entitlement_feature">Feature *</Label>
                <Select
                  value={entitlementForm.feature_id}
                  onValueChange={(value) => {
                    const feature = features?.find((f) => f.id === value)
                    setEntitlementForm({
                      ...entitlementForm,
                      feature_id: value,
                      value: feature?.feature_type === 'boolean' ? 'true' : '',
                    })
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a feature..." />
                  </SelectTrigger>
                  <SelectContent>
                    {features?.map((feature) => (
                      <SelectItem key={feature.id} value={feature.id}>
                        {feature.name} ({feature.feature_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="entitlement_plan">Plan *</Label>
                <Select
                  value={entitlementForm.plan_id}
                  onValueChange={(value) => setEntitlementForm({ ...entitlementForm, plan_id: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a plan..." />
                  </SelectTrigger>
                  <SelectContent>
                    {plans?.map((plan) => (
                      <SelectItem key={plan.id} value={plan.id}>
                        {plan.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="entitlement_value">Value *</Label>
                <EntitlementValueInput
                  featureType={selectedEntitlementFeature?.feature_type}
                  value={entitlementForm.value}
                  onChange={(value) => setEntitlementForm({ ...entitlementForm, value })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEntitlementDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createEntitlementMutation.isPending}>
                {createEntitlementMutation.isPending ? 'Adding...' : 'Add Entitlement'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Copy Entitlements Dialog */}
      <Dialog open={copyDialogOpen} onOpenChange={setCopyDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Copy Entitlements from Plan</DialogTitle>
            <DialogDescription>
              Copy all feature entitlements from one plan to another. Existing entitlements on the target plan will not be overwritten.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCopySubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="copy_source">Source Plan *</Label>
                <Select value={copySourcePlanId} onValueChange={setCopySourcePlanId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Copy from..." />
                  </SelectTrigger>
                  <SelectContent>
                    {plans?.map((plan) => (
                      <SelectItem key={plan.id} value={plan.id}>
                        {plan.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="copy_target">Target Plan *</Label>
                <Select value={copyTargetPlanId} onValueChange={setCopyTargetPlanId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Copy to..." />
                  </SelectTrigger>
                  <SelectContent>
                    {plans
                      ?.filter((p) => p.id !== copySourcePlanId)
                      .map((plan) => (
                        <SelectItem key={plan.id} value={plan.id}>
                          {plan.name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCopyDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!copySourcePlanId || !copyTargetPlanId || copyEntitlementsMutation.isPending}
              >
                {copyEntitlementsMutation.isPending ? 'Copying...' : 'Copy Entitlements'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function EntitlementValueInput({
  featureType,
  value,
  onChange,
}: {
  featureType?: string
  value: string
  onChange: (value: string) => void
}) {
  if (featureType === 'boolean') {
    return (
      <div className="flex items-center gap-2">
        <Switch
          id="entitlement_value"
          checked={value === 'true'}
          onCheckedChange={(checked) => onChange(checked ? 'true' : 'false')}
        />
        <span className="text-sm">{value === 'true' ? 'Enabled' : 'Disabled'}</span>
      </div>
    )
  }

  if (featureType === 'quantity') {
    const numValue = parseInt(value, 10)
    const isValidNumber = !isNaN(numValue) && numValue >= 0
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Slider
            min={0}
            max={1000}
            step={1}
            value={isValidNumber ? [numValue] : [0]}
            onValueChange={([v]) => onChange(String(v))}
            className="flex-1"
          />
          <Input
            id="entitlement_value"
            type="number"
            min={0}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-24"
            placeholder="0"
            required
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Set the quantity limit for this feature
        </p>
      </div>
    )
  }

  return (
    <Input
      id="entitlement_value"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Enter value"
      required
    />
  )
}

interface ExpandableFeatureRowProps {
  feature: Feature
  isExpanded: boolean
  onToggle: () => void
  planCount: number
  entitlements: Entitlement[]
  planMap: Map<string, { id: string; name: string }>
  featureMap: Map<string, Feature>
  onEdit: () => void
  onDelete: () => void
  onDeleteEntitlement: (id: string) => void
  deleteEntitlementPending: boolean
}

function ExpandableFeatureRow({
  feature,
  isExpanded,
  onToggle,
  planCount,
  entitlements,
  planMap,
  onEdit,
  onDelete,
  onDeleteEntitlement,
  deleteEntitlementPending,
}: ExpandableFeatureRowProps) {
  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={onToggle}
      >
        <TableCell>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onToggle() }}>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        </TableCell>
        <TableCell>
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{feature.code}</code>
        </TableCell>
        <TableCell className="font-medium">{feature.name}</TableCell>
        <TableCell>
          <Badge variant={featureTypeBadgeVariant(feature.feature_type)}>
            {feature.feature_type}
          </Badge>
        </TableCell>
        <TableCell className="text-muted-foreground max-w-[200px] truncate">
          {feature.description ?? '\u2014'}
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1 text-muted-foreground">
            <Layers className="h-3.5 w-3.5" />
            <span className="text-sm">{planCount} {planCount === 1 ? 'plan' : 'plans'}</span>
          </div>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="icon"
              onClick={onEdit}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onDelete}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/30 p-0">
            <div className="px-8 py-3">
              {entitlements.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">No plan entitlements for this feature.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Plan</TableHead>
                      <TableHead>Value</TableHead>
                      <TableHead className="w-[60px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entitlements.map((ent) => {
                      const plan = planMap.get(ent.plan_id)
                      return (
                        <TableRow key={ent.id}>
                          <TableCell className="font-medium">{plan?.name ?? ent.plan_id}</TableCell>
                          <TableCell>{formatEntitlementValue(ent.value, feature.feature_type)}</TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => onDeleteEntitlement(ent.id)}
                              disabled={deleteEntitlementPending}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

function formatEntitlementValue(value: string, featureType?: string): string {
  if (featureType === 'boolean') {
    return value === 'true' ? 'Enabled' : 'Disabled'
  }
  return value
}
