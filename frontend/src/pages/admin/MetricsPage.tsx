import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Code, Hash, ArrowUp, CircleDot, BarChart3, Search, Layers, MoreHorizontal, Pencil, Trash2, ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import PageHeader from '@/components/PageHeader'
import { billableMetricsApi, ApiError } from '@/lib/api'
import type { BillableMetric, AggregationType } from '@/lib/api'

const aggregationTypes: { value: AggregationType; label: string; description: string; icon: React.ElementType }[] = [
  { value: 'count', label: 'Count', description: 'Count total events', icon: Hash },
  { value: 'sum', label: 'Sum', description: 'Sum a numeric field', icon: ArrowUp },
  { value: 'max', label: 'Max', description: 'Maximum value of a field', icon: ArrowUp },
  { value: 'unique_count', label: 'Unique Count', description: 'Count unique values', icon: CircleDot },
]

function AggregationBadge({ type }: { type: AggregationType }) {
  const config = aggregationTypes.find((a) => a.value === type)
  const Icon = config?.icon ?? Hash

  const colorClass = {
    count: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    sum: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    max: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
    unique_count: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
  }[type]

  return (
    <Badge variant="outline" className={colorClass}>
      <Icon className="mr-1 h-3 w-3" />
      {config?.label ?? type}
    </Badge>
  )
}

// --- Expandable Metric Row ---
function MetricExpandableRow({ metric, planCount }: { metric: BillableMetric; planCount: number }) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()
  const { setDeleteMetric } = useMetricsPageContext()

  const { data: plans, isLoading } = useQuery({
    queryKey: ['billable-metrics', metric.id, 'plans'],
    queryFn: () => billableMetricsApi.metricPlans(metric.id),
    enabled: expanded,
  })

  return (
    <>
      <TableRow>
        <TableCell className="font-medium">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
            {metric.name}
          </div>
        </TableCell>
        <TableCell>
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{metric.code}</code>
        </TableCell>
        <TableCell className="hidden md:table-cell max-w-[200px] truncate text-muted-foreground">
          {metric.description || <span className="text-muted-foreground">&mdash;</span>}
        </TableCell>
        <TableCell>
          <AggregationBadge type={metric.aggregation_type} />
        </TableCell>
        <TableCell className="hidden md:table-cell">
          {metric.field_name ? (
            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{metric.field_name}</code>
          ) : metric.expression ? (
            <code className="text-xs bg-muted px-1.5 py-0.5 rounded block max-w-[200px] truncate" title={metric.expression}>{metric.expression}</code>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )}
        </TableCell>
        <TableCell className="hidden md:table-cell">
          <div className="flex items-center gap-1 text-sm">
            <Layers className="h-3.5 w-3.5 text-muted-foreground" />
            {planCount}
          </div>
        </TableCell>
        <TableCell>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/admin/metrics/${metric.id}/edit`)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onClick={() => setDeleteMetric(metric)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell colSpan={7} className="py-3">
            <div className="pl-10">
              <p className="text-sm font-medium mb-2">Used by Plans</p>
              {isLoading ? (
                <div className="space-y-1">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-4 w-40" />
                </div>
              ) : !plans?.length ? (
                <p className="text-sm text-muted-foreground">
                  Not used by any plans yet.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {plans.map((plan) => (
                    <Badge key={plan.id} variant="outline" className="text-xs">
                      {plan.name}
                      <span className="mx-1 text-muted-foreground">&middot;</span>
                      <code className="text-xs">{plan.code}</code>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// --- Page context ---
import { createContext, useContext } from 'react'

type MetricsPageContextType = {
  setDeleteMetric: (metric: BillableMetric) => void
}

const MetricsPageContext = createContext<MetricsPageContextType>(null!)

function useMetricsPageContext() {
  return useContext(MetricsPageContext)
}

const PAGE_SIZE = 20

export default function MetricsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()
  const [deleteMetric, setDeleteMetric] = useState<BillableMetric | null>(null)
  const [search, setSearch] = useState('')
  const [aggregationFilter, setAggregationFilter] = useState<string>('all')

  // Fetch metrics from API
  const { data: metricsData, isLoading, error } = useQuery({
    queryKey: ['billable-metrics', page, pageSize, orderBy],
    queryFn: () => billableMetricsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })
  const metrics = metricsData?.data
  const totalCount = metricsData?.totalCount ?? 0

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['billable-metrics-stats'],
    queryFn: () => billableMetricsApi.stats(),
  })

  // Fetch plan counts per metric
  const { data: planCounts } = useQuery({
    queryKey: ['billable-metrics-plan-counts'],
    queryFn: () => billableMetricsApi.planCounts(),
  })

  const filteredMetrics = metrics?.filter((m) => {
    const matchesSearch = !search || (() => {
      const q = search.toLowerCase()
      return (
        m.name.toLowerCase().includes(q) ||
        m.code.toLowerCase().includes(q) ||
        m.description?.toLowerCase().includes(q)
      )
    })()
    const matchesAggregation = aggregationFilter === 'all' || m.aggregation_type === aggregationFilter
    return matchesSearch && matchesAggregation
  }) ?? []

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => billableMetricsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-stats'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-plan-counts'] })
      setDeleteMetric(null)
      toast.success('Billable metric deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete billable metric'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load billable metrics. Please try again.</p>
      </div>
    )
  }

  const pageContext: MetricsPageContextType = { setDeleteMetric }

  return (
    <MetricsPageContext.Provider value={pageContext}>
    <div className="space-y-6">
      <PageHeader
        title="Billable Metrics"
        description="Define how usage events are aggregated for billing"
        actions={
          <Button asChild>
            <Link to="/admin/metrics/new">
              <Plus className="mr-2 h-4 w-4" />
              Add Metric
            </Link>
          </Button>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Metrics</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total ?? 0}</div>
          </CardContent>
        </Card>
        {aggregationTypes.map((agg) => (
          <Card key={agg.value}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{agg.label}</CardTitle>
              <agg.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.by_aggregation_type[agg.value] ?? 0}
              </div>
              <p className="text-xs text-muted-foreground">{agg.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search metrics..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={aggregationFilter} onValueChange={setAggregationFilter}>
          <SelectTrigger className="w-full md:w-48">
            <SelectValue placeholder="Aggregation type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {aggregationTypes.map((agg) => (
              <SelectItem key={agg.value} value={agg.value}>
                {agg.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Metrics Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTableHead label="Name" sortKey="name" sort={sort} onSort={setSort} />
              <SortableTableHead label="Code" sortKey="code" sort={sort} onSort={setSort} />
              <TableHead className="hidden md:table-cell">Description</TableHead>
              <TableHead>Aggregation</TableHead>
              <TableHead className="hidden md:table-cell">Field / Expression</TableHead>
              <TableHead className="hidden md:table-cell">Plans</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(3)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                </TableRow>
              ))
            ) : filteredMetrics.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Code className="h-8 w-8 text-muted-foreground" />
                    <p className="text-muted-foreground">
                      {search || aggregationFilter !== 'all'
                        ? 'No metrics match your filters'
                        : 'No billable metrics'}
                    </p>
                    {!search && aggregationFilter === 'all' && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        asChild
                      >
                        <Link to="/admin/metrics/new">
                          <Plus className="mr-2 h-4 w-4" />
                          Create your first metric
                        </Link>
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredMetrics.map((metric) => (
                <MetricExpandableRow
                  key={metric.id}
                  metric={metric}
                  planCount={planCounts?.[metric.id] ?? 0}
                />
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteMetric}
        onOpenChange={(open) => !open && setDeleteMetric(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Billable Metric</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deleteMetric?.name}"? This will
              affect any plans using this metric.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMetric && deleteMutation.mutate(deleteMetric.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
    </MetricsPageContext.Provider>
  )
}
