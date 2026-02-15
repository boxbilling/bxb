const brandColors: Record<string, string> = {
  visa: '#1A1F71',
  mastercard: '#EB001B',
  amex: '#006FCF',
  american_express: '#006FCF',
  discover: '#FF6000',
  diners: '#0079BE',
  diners_club: '#0079BE',
  jcb: '#0B7B3E',
  unionpay: '#D50032',
}

function getBrandKey(brand: string): string {
  return brand.toLowerCase().replace(/[\s-]+/g, '_')
}

function VisaIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="4" fill="#1A1F71" />
      <path d="M10.2 15.5L11.5 8.5H13.2L11.9 15.5H10.2Z" fill="white" />
      <path d="M17.6 8.7C17.2 8.5 16.5 8.3 15.7 8.3C14 8.3 12.8 9.2 12.8 10.4C12.8 11.3 13.6 11.8 14.2 12.1C14.8 12.4 15 12.6 15 12.9C15 13.3 14.5 13.5 14 13.5C13.3 13.5 12.9 13.4 12.3 13.1L12.1 13L11.8 14.7C12.3 14.9 13.1 15.1 13.9 15.1C15.7 15.1 16.9 14.2 16.9 12.9C16.9 12.2 16.4 11.7 15.5 11.2C14.9 10.9 14.6 10.7 14.6 10.4C14.6 10.1 14.9 9.9 15.5 9.9C16.1 9.9 16.5 10 16.9 10.2L17.1 10.3L17.6 8.7Z" fill="white" />
      <path d="M19.8 8.5H18.5C18.1 8.5 17.8 8.6 17.6 9L15.2 15.5H17C17 15.5 17.3 14.7 17.3 14.5H19.5C19.5 14.7 19.7 15.5 19.7 15.5H21.3L19.8 8.5ZM17.9 13C18 12.7 18.7 10.8 18.7 10.8L19.2 13H17.9Z" fill="white" />
      <path d="M9.2 8.5L7.5 13.3L7.3 12.3C6.9 11.1 5.8 9.8 4.5 9.1L6 15.5H7.8L11 8.5H9.2Z" fill="white" />
      <path d="M6.5 8.5H3.8L3.8 8.7C5.9 9.2 7.3 10.5 7.8 12L7.2 9C7.1 8.6 6.8 8.5 6.5 8.5Z" fill="#F9A533" />
    </svg>
  )
}

function MastercardIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="4" fill="#252525" />
      <circle cx="9.5" cy="12" r="5" fill="#EB001B" />
      <circle cx="14.5" cy="12" r="5" fill="#F79E1B" />
      <path d="M12 8.3C13.1 9.2 13.8 10.5 13.8 12C13.8 13.5 13.1 14.8 12 15.7C10.9 14.8 10.2 13.5 10.2 12C10.2 10.5 10.9 9.2 12 8.3Z" fill="#FF5F00" />
    </svg>
  )
}

function AmexIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="4" fill="#006FCF" />
      <path d="M3.5 10.5L4.5 8H5.5L6.5 10.5V8H8L8.8 10L9.5 8H11V12H9.8L8.8 9.5L7.8 12H6.5V9.2L5.5 12H4.5L3.5 9.2V12H2V8L3.5 10.5Z" fill="white" />
      <path d="M11.5 12V8H15.5V9.2H13V9.5H15.4V10.6H13V10.9H15.5V12H11.5Z" fill="white" />
      <path d="M2 16V12.5H4L4.5 13.5L5 12.5H22V15.5C22 15.5 21.5 16 21 16H12.5L12 15L11.5 16H8.5V14.5L8 16H6.8L6.3 14.5V16H3.5L3 15L2 16Z" fill="white" />
      <path d="M2.5 15.5L3.5 13H4.5L5.5 15.5V13H7L7.8 15L8.5 13H9.5V15.5H8.5L8.5 13.8L7.5 15.5H6.8L5.8 13.8V15.5H4L3.7 14.8H2.8L2.5 15.5Z" fill="#006FCF" />
      <path d="M10 15.5V13H13.5V13.8H11.2V13.9H13.4V14.6H11.2V14.8H13.5V15.5H10Z" fill="#006FCF" />
    </svg>
  )
}

function DiscoverIcon({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="4" fill="white" stroke="#E5E7EB" />
      <circle cx="14" cy="12" r="4" fill="#FF6000" />
      <text x="3" y="11" fontFamily="Arial" fontSize="5" fontWeight="bold" fill="#333">DISC</text>
      <text x="3" y="17" fontFamily="Arial" fontSize="4" fill="#333">VER</text>
    </svg>
  )
}

function GenericCardIcon({ size, brand }: { size: number; brand: string }) {
  const key = getBrandKey(brand)
  const color = brandColors[key] ?? '#6B7280'
  const initial = brand.charAt(0).toUpperCase()

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="4" fill={color} />
      <text x="12" y="15" fontFamily="Arial" fontSize="10" fontWeight="bold" fill="white" textAnchor="middle">{initial}</text>
    </svg>
  )
}

export function CardBrandIcon({
  brand,
  size = 24,
}: {
  brand: string | undefined | null
  size?: number
}) {
  if (!brand) return null

  const key = getBrandKey(brand)

  switch (key) {
    case 'visa':
      return <VisaIcon size={size} />
    case 'mastercard':
      return <MastercardIcon size={size} />
    case 'amex':
    case 'american_express':
      return <AmexIcon size={size} />
    case 'discover':
      return <DiscoverIcon size={size} />
    default:
      return <GenericCardIcon size={size} brand={brand} />
  }
}
