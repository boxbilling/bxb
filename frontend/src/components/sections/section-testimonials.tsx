import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar.tsx"
import { Card, CardContent, CardHeader } from "@/components/ui/card.tsx"

const testimonials = [
  {
    name: "Sarah K.",
    role: "Engineering Manager",
    company: "Acme Corp",
    content: "This tool completely changed how our team collaborates. We shipped features twice as fast after adopting it.",
    initials: "SK",
  },
  {
    name: "Marcus R.",
    role: "Tech Lead",
    company: "Nebula Labs",
    content: "The developer experience is outstanding. Everything just works out of the box and the docs are excellent.",
    initials: "MR",
  },
  {
    name: "Emily W.",
    role: "Full Stack Developer",
    company: "Stratos",
    content: "I've tried many similar tools and this is by far the most intuitive. It fits perfectly into our existing workflow.",
    initials: "EW",
  },
]

export function SectionTestimonials() {
  return (
    <section className="w-full py-12 md:py-24 lg:py-32 bg-muted/50 relative overflow-hidden">
      <div className="container mx-auto px-4 md:px-6 relative z-10">
        <div className="flex flex-col items-center justify-center space-y-4 text-center">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">Loved by Developers</h2>
            <p className="max-w-[900px] text-muted-foreground md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              See what our users have to say
            </p>
          </div>
        </div>
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 py-12 md:grid-cols-3 lg:gap-12">
          {testimonials.map((testimonial, index) => (
            <Card key={index} className="flex flex-col justify-between">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-4">
                  <Avatar>
                    <AvatarFallback>{testimonial.initials}</AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="font-semibold leading-none">{testimonial.name}</h3>
                    <p className="text-sm text-muted-foreground">{testimonial.role} at {testimonial.company}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">{testimonial.content}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
