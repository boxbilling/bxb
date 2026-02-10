
import { useState } from "react"
import { MessageSquare, Bot, Frown, Meh, SmilePlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const topics = [
  { value: "bug", label: "Bug Report" },
  { value: "feature", label: "Feature Request" },
  { value: "schema", label: "Schema Suggestion" },
  { value: "ux", label: "UX Improvement" },
  { value: "other", label: "Other" },
]

const sentiments = [
  { value: "frustrated", icon: Bot, label: "Frustrated" },
  { value: "confused", icon: Frown, label: "Confused" },
  { value: "neutral", icon: Meh, label: "Neutral" },
  { value: "happy", icon: SmilePlus, label: "Happy" },
]

export function FeedbackPopover() {
  const [open, setOpen] = useState(false)
  const [topic, setTopic] = useState("")
  const [feedback, setFeedback] = useState("")
  const [sentiment, setSentiment] = useState<string | null>(null)

  const handleSend = () => {
    // Handle feedback submission
    console.log({ topic, feedback, sentiment })
    setTopic("")
    setFeedback("")
    setSentiment(null)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="text-muted-foreground hover:text-foreground border-border hover:border-primary/50 gap-2 bg-transparent"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span className="text-xs">Feedback</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 p-0 bg-card border-primary/50 shadow-xl shadow-primary/5"
        align="end"
        sideOffset={8}
      >
        <div className="p-3 space-y-3">
          {/* Topic selector */}
          <Select value={topic} onValueChange={setTopic}>
            <SelectTrigger className="w-full bg-background border-border focus:border-primary focus:ring-1 focus:ring-primary">
              <SelectValue placeholder="Select a topic..." />
            </SelectTrigger>
            <SelectContent className="bg-card border-border">
              {topics.map((t) => (
                <SelectItem key={t.value} value={t.value} className="focus:bg-muted">
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Feedback textarea */}
          <Textarea
            placeholder="Your feedback..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="min-h-[120px] bg-background border-border focus:border-primary focus:ring-1 focus:ring-primary resize-none text-sm"
          />

          {/* Markdown hint */}
          <div className="flex justify-end">
            <span className="text-[10px] text-muted-foreground/60 font-mono flex items-center gap-1">
              <span className="px-1 py-0.5 bg-muted/50 rounded text-[9px]">M↓</span>
              supported.
            </span>
          </div>
        </div>

        {/* Footer with sentiment and send */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
          <div className="flex items-center gap-1">
            {sentiments.map((s) => (
              <button
                key={s.value}
                onClick={() => setSentiment(s.value)}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  sentiment === s.value
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted",
                )}
                title={s.label}
              >
                <s.icon className="w-4 h-4" />
              </button>
            ))}
          </div>
          <Button
            size="sm"
            onClick={handleSend}
            disabled={!feedback.trim()}
            className="bg-foreground text-background hover:bg-foreground/90 text-xs px-4"
          >
            Send
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
