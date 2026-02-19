import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, userEvent } from '@/test/test-utils'

import { SubscriptionInvoicesTab } from './SubscriptionInvoicesTab'

vi.mock('@/lib/api', () => ({
  invoicesApi: { list: vi.fn() },
  paymentsApi: { list: vi.fn() },
  creditNotesApi: { list: vi.fn() },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

interface Invoice {
  id: string
  customer_id: string
  invoice_number: string
  invoice_type: string
  status: string
  issued_at: string | null
  due_date: string | null
  total: string
  currency: string
}

interface Payment {
  id: string
  invoice_id: string
  status: string
  provider: string
  completed_at: string | null
  failure_reason: string | null
  amount: number
  currency: string
}

interface CreditNote {
  id: string
  invoice_id: string
  number: string
  reason: string
  status: string
  total_amount_cents: string
  currency: string
}

let mockInvoices: Invoice[] | undefined
let mockInvoicesLoading: boolean
let mockPayments: Payment[] | undefined
let mockCreditNotes: CreditNote[] | undefined

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'subscription-invoices') {
        return { data: mockInvoices, isLoading: mockInvoicesLoading }
      }
      if (options.queryKey[0] === 'subscription-payments') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockPayments, isLoading: false }
      }
      if (options.queryKey[0] === 'subscription-credit-notes') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockCreditNotes, isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionInvoicesTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockInvoices = [
      {
        id: 'inv-1',
        customer_id: 'cust-1',
        invoice_number: 'INV-001',
        invoice_type: 'subscription',
        status: 'paid',
        issued_at: '2024-01-15T00:00:00Z',
        due_date: '2024-02-15T00:00:00Z',
        total: '9900',
        currency: 'usd',
      },
      {
        id: 'inv-2',
        customer_id: 'cust-1',
        invoice_number: 'INV-002',
        invoice_type: 'subscription',
        status: 'draft',
        issued_at: null,
        due_date: null,
        total: '5000',
        currency: 'usd',
      },
    ]
    mockInvoicesLoading = false
    mockPayments = [
      {
        id: 'pay-1',
        invoice_id: 'inv-1',
        status: 'succeeded',
        provider: 'stripe',
        completed_at: '2024-01-16T10:00:00Z',
        failure_reason: null,
        amount: 99.0,
        currency: 'usd',
      },
    ]
    mockCreditNotes = []
  })

  describe('loading state', () => {
    it('renders skeletons when invoices are loading', () => {
      mockInvoicesLoading = true
      const { container } = render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('empty state', () => {
    it('renders empty message when no invoices', () => {
      mockInvoices = []
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('No invoices generated for this subscription')).toBeInTheDocument()
    })

    it('renders empty message when invoices is undefined', () => {
      mockInvoices = undefined
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('No invoices generated for this subscription')).toBeInTheDocument()
    })
  })

  describe('invoices table', () => {
    it('renders Invoices & Payments heading', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('Invoices & Payments')).toBeInTheDocument()
    })

    it('renders View all link', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const link = screen.getByRole('link', { name: /View all/ })
      expect(link).toHaveAttribute('href', '/admin/invoices?subscription_id=sub-1')
    })

    it('renders invoice number', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('INV-001')).toBeInTheDocument()
      expect(screen.getByText('INV-002')).toBeInTheDocument()
    })

    it('renders invoice status badges', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('paid')).toBeInTheDocument()
      expect(screen.getByText('draft')).toBeInTheDocument()
    })

    it('renders invoice amounts', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('$99.00')).toBeInTheDocument()
      expect(screen.getByText('$50.00')).toBeInTheDocument()
    })

    it('renders dash for missing invoice number', () => {
      mockInvoices = [{
        id: 'inv-3',
        customer_id: 'cust-1',
        invoice_number: '',
        invoice_type: 'subscription',
        status: 'draft',
        issued_at: null,
        due_date: null,
        total: '1000',
        currency: 'usd',
      }]
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      // em dash appears for empty invoice number plus null dates
      const dashes = screen.getAllByText('\u2014')
      expect(dashes.length).toBeGreaterThanOrEqual(1)
    })

    it('renders dash for missing dates', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      // INV-002 has null issued_at and due_date
      const dashes = screen.getAllByText('\u2014')
      expect(dashes.length).toBeGreaterThanOrEqual(2)
    })

    it('navigates to invoice detail on row click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const rows = screen.getAllByRole('row')
      // rows[0] is the header, rows[1] is INV-001
      await user.click(rows[1])
      expect(mockNavigate).toHaveBeenCalledWith('/admin/invoices/inv-1')
    })
  })

  describe('payment expansion', () => {
    it('shows expand button when invoice has payments', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const expandButton = screen.getByRole('button', { name: /Expand payments/ })
      expect(expandButton).toBeInTheDocument()
    })

    it('does not show expand button when invoice has no payments', () => {
      mockPayments = []
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.queryByRole('button', { name: /Expand payments/ })).not.toBeInTheDocument()
    })

    it('expands payments on button click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const expandButton = screen.getByRole('button', { name: /Expand payments/ })
      await user.click(expandButton)
      expect(screen.getByText('succeeded')).toBeInTheDocument()
      expect(screen.getByText('Stripe')).toBeInTheDocument()
      // $99.00 appears for both the invoice amount and payment amount
      const amounts = screen.getAllByText('$99.00')
      expect(amounts.length).toBe(2)
    })

    it('collapses payments on second click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      const expandButton = screen.getByRole('button', { name: /Expand payments/ })
      await user.click(expandButton)
      expect(screen.getByText('succeeded')).toBeInTheDocument()
      const collapseButton = screen.getByRole('button', { name: /Collapse payments/ })
      await user.click(collapseButton)
      // Payment row should be gone (only the badge text "paid" from the invoice row should remain)
      expect(screen.queryByText('succeeded')).not.toBeInTheDocument()
    })

    it('shows failure reason on failed payment', async () => {
      mockPayments = [{
        id: 'pay-2',
        invoice_id: 'inv-1',
        status: 'failed',
        provider: 'stripe',
        completed_at: null,
        failure_reason: 'Card declined',
        amount: 99.0,
        currency: 'usd',
      }]
      const user = userEvent.setup()
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Expand payments/ }))
      expect(screen.getByText('Card declined')).toBeInTheDocument()
      expect(screen.getByText('Pending')).toBeInTheDocument()
    })
  })

  describe('credit notes card', () => {
    it('does not render credit notes card when no credit notes', () => {
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.queryByText('Credit Notes')).not.toBeInTheDocument()
    })

    it('renders credit notes card when credit notes exist', () => {
      mockCreditNotes = [{
        id: 'cn-1',
        invoice_id: 'inv-1',
        number: 'CN-001',
        reason: 'duplicated_charge',
        status: 'finalized',
        total_amount_cents: '5000',
        currency: 'usd',
      }]
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      expect(screen.getByText('Credit Notes')).toBeInTheDocument()
      expect(screen.getByText('CN-001')).toBeInTheDocument()
      expect(screen.getByText('Duplicated charge')).toBeInTheDocument()
      expect(screen.getByText('finalized')).toBeInTheDocument()
    })

    it('navigates to credit note detail on row click', async () => {
      mockCreditNotes = [{
        id: 'cn-1',
        invoice_id: 'inv-1',
        number: 'CN-001',
        reason: 'other',
        status: 'draft',
        total_amount_cents: '2000',
        currency: 'usd',
      }]
      const user = userEvent.setup()
      render(<SubscriptionInvoicesTab subscriptionId="sub-1" />)
      // Find the credit note row and click it
      const cnRow = screen.getByText('CN-001').closest('tr')
      await user.click(cnRow!)
      expect(mockNavigate).toHaveBeenCalledWith('/admin/credit-notes/cn-1')
    })
  })
})
