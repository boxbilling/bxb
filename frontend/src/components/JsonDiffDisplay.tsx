import { ArrowRight } from 'lucide-react'

type JsonValue = string | number | boolean | null | undefined | JsonValue[] | { [key: string]: JsonValue }

function isComplex(value: unknown): boolean {
  return value !== null && typeof value === 'object'
}

function tokenizeJson(value: unknown): React.ReactNode[] {
  const json = JSON.stringify(value, null, 2)
  if (!json) return [String(value)]

  const tokens: React.ReactNode[] = []
  // Match JSON tokens: strings, numbers, booleans, null, punctuation
  const regex = /("(?:[^"\\]|\\.)*")\s*:/g
  const lines = json.split('\n')

  for (let i = 0; i < lines.length; i++) {
    if (i > 0) tokens.push('\n')
    const line = lines[i]
    let lastIndex = 0
    // Tokenize each line
    const parts: React.ReactNode[] = []
    // Match keys, string values, numbers, booleans, null
    const lineRegex = /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|(\btrue\b|\bfalse\b)|(\bnull\b)|([[\]{},:])|\s+/g
    let match
    let partIndex = 0
    while ((match = lineRegex.exec(line)) !== null) {
      if (match[1] && match[2]) {
        // Key
        parts.push(
          <span key={partIndex++} className="text-sky-600 dark:text-sky-400">{match[1]}</span>,
          <span key={partIndex++}>{match[2]}</span>,
        )
      } else if (match[1]) {
        // String value
        parts.push(
          <span key={partIndex++} className="text-amber-600 dark:text-amber-400">{match[1]}</span>,
        )
      } else if (match[3]) {
        // Number
        parts.push(
          <span key={partIndex++} className="text-violet-600 dark:text-violet-400">{match[3]}</span>,
        )
      } else if (match[4]) {
        // Boolean
        parts.push(
          <span key={partIndex++} className="text-orange-600 dark:text-orange-400">{match[4]}</span>,
        )
      } else if (match[5]) {
        // Null
        parts.push(
          <span key={partIndex++} className="text-gray-500 dark:text-gray-400 italic">{match[5]}</span>,
        )
      } else {
        // Punctuation or whitespace
        parts.push(<span key={partIndex++}>{match[0]}</span>)
      }
    }
    tokens.push(<span key={`line-${i}`}>{parts}</span>)
  }

  return tokens
}

function JsonBlock({ value, variant }: { value: unknown; variant: 'old' | 'new' }) {
  const bg = variant === 'old'
    ? 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800'
    : 'bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800'
  const label = variant === 'old' ? 'Old value' : 'New value'
  const labelColor = variant === 'old'
    ? 'text-red-600 dark:text-red-400'
    : 'text-green-600 dark:text-green-400'

  return (
    <div className={`rounded-md border ${bg} overflow-hidden`}>
      <div className={`text-[10px] font-semibold uppercase tracking-wider px-3 py-1 ${labelColor} border-b ${variant === 'old' ? 'border-red-200 dark:border-red-800' : 'border-green-200 dark:border-green-800'}`}>
        {label}
      </div>
      <pre className="text-xs font-mono p-3 overflow-x-auto whitespace-pre">
        {tokenizeJson(value)}
      </pre>
    </div>
  )
}

function InlineValue({ value, variant }: { value: unknown; variant: 'old' | 'new' }) {
  const formatted = value === undefined || value === null ? 'null' : String(value)
  if (variant === 'old') {
    return (
      <span className="text-red-600 dark:text-red-400 line-through">{formatted}</span>
    )
  }
  return (
    <span className="text-green-600 dark:text-green-400">{formatted}</span>
  )
}

function FieldDiff({ fieldKey, change }: { fieldKey: string; change: { old?: unknown; new?: unknown } }) {
  const oldIsComplex = isComplex(change.old)
  const newIsComplex = isComplex(change.new)
  const useBlocks = oldIsComplex || newIsComplex

  if (useBlocks) {
    return (
      <div className="space-y-2">
        <span className="font-medium text-foreground font-mono text-sm">{fieldKey}</span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <JsonBlock value={change.old ?? null} variant="old" />
          <JsonBlock value={change.new ?? null} variant="new" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2 text-sm font-mono">
      <span className="font-medium text-foreground min-w-[120px]">{fieldKey}:</span>
      <InlineValue value={change.old} variant="old" />
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
      <InlineValue value={change.new} variant="new" />
    </div>
  )
}

export function ChangesDisplay({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes)
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No changes recorded</p>
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => {
        const change = value as { old?: unknown; new?: unknown } | undefined
        if (!change) return null
        return <FieldDiff key={key} fieldKey={key} change={change} />
      })}
    </div>
  )
}

export function ChangesSummary({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes)
  if (entries.length === 0) return null

  return (
    <div className="mt-1 space-y-0.5">
      {entries.map(([key, value]) => {
        const change = value as { old?: unknown; new?: unknown } | undefined
        const oldIsComplex = isComplex(change?.old)
        const newIsComplex = isComplex(change?.new)

        if (oldIsComplex || newIsComplex) {
          return (
            <div key={key} className="text-xs font-mono">
              <span className="text-muted-foreground">{key}:</span>
              <span className="ml-1 text-muted-foreground italic">object changed</span>
            </div>
          )
        }

        return (
          <div key={key} className="flex items-center gap-1 text-xs font-mono">
            <span className="text-muted-foreground">{key}:</span>
            <span className="text-red-600 dark:text-red-400 line-through">
              {change?.old !== undefined ? String(change.old) : 'null'}
            </span>
            <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="text-green-600 dark:text-green-400">
              {change?.new !== undefined ? String(change.new) : 'null'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
