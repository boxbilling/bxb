
import { useState } from "react"
import { Bot, Frown, Meh, SmilePlus, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import api from "@/lib/api"
import { toast } from "sonner"

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

interface FeedbackDialogProps {
  children: React.ReactNode
}

export function FeedbackDialog({ children }: FeedbackDialogProps) {
  const [open, setOpen] = useState(false)
  const [topic, setTopic] = useState("")
  const [feedback, setFeedback] = useState("")
  const [sentiment, setSentiment] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSend = async () => {
    if (!topic || !feedback.trim()) return

    setIsSubmitting(true)
    try {
      // @ts-expect-error endpoint not yet in backend schema
      const { error } = await api.POST("/feedback", {
        body: {
          topic: topic as "bug" | "feature" | "schema" | "ux" | "other",
          feedback,
          sentiment: sentiment as "frustrated" | "confused" | "neutral" | "happy" | null,
        },
      })

      if (error) {
        toast.error("Failed to send feedback")
        return
      }

      toast.success("Feedback sent!")
      setTopic("")
      setFeedback("")
      setSentiment(null)
      setOpen(false)
    } catch {
      toast.error("Failed to send feedback")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md p-0">
        <DialogHeader className="px-4 pt-4 pb-0">
          <DialogTitle>Send Feedback</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-3">
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
        <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-muted/30">
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
            disabled={!topic || !feedback.trim() || isSubmitting}
            className="bg-foreground text-background hover:bg-foreground/90 text-xs px-4"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                Sending...
              </>
            ) : (
              "Send"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
