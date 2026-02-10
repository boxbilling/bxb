import { config } from "@/lib/config"

export interface FaqItem {
  question: string
  answer: string
  image?: string
}

export const faqs: FaqItem[] = [
    {
        question: `What is ${config.VITE_APP_TITLE}?`,
        answer:
            `${config.VITE_APP_TITLE} is a template for AI builders.`,
        image: "/opengraph-image.png"
    },
]