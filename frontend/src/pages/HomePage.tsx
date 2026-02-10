import { Helmet } from "react-helmet-async"
import { config } from "@/lib/config"
import { SectionItems } from "@/components/sections/section-items.tsx"
import { SectionTestimonials } from "@/components/sections/section-testimonials.tsx"
import { SectionFaq } from "@/components/sections/section-faq.tsx"

export default function HomePage() {
  return (
    <>
      <Helmet>
        <title>{`${config.VITE_APP_TITLE}`}</title>
      </Helmet>
      <SectionItems />
      <SectionTestimonials />
      <SectionFaq />
    </>
  )
}
