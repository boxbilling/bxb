import {clsx, type ClassValue} from 'clsx'
import {twMerge} from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function formatCents(cents: number | string, currency: string = 'USD'): string {
    const value = (typeof cents === 'string' ? parseFloat(cents) : cents) / 100
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: (currency || 'USD').toUpperCase(),
    }).format(value)
}

export function formatCurrency(amount: number | string, currency: string = 'USD'): string {
    const value = typeof amount === 'string' ? parseFloat(amount) : amount
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: (currency || 'USD').toUpperCase(),
    }).format(value)
}
