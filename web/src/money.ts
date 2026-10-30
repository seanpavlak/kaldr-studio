import { toast } from 'sonner'

export const UNLIMITED_KEY = 'This OpenRouter key does not have a usage limit.'
export const UNKNOWN_LIMIT = 'Could not check whether this key has a spending limit. Confirm it is limited before you make a sprite.'
export const SHORT_BUDGET = 'This key does not have enough budget left for this run.'
export const UNKNOWN_BUDGET = 'Could not check the remaining budget.'

export function money(usd: number, estimate: boolean) {
  const shown = usd < 1 ? usd.toFixed(3) : usd.toFixed(2)
  return estimate ? `about $${shown}` : `$${shown}`
}

type Budget = { limited?: boolean | null; remaining?: number | null }

export async function budgetAllows(usd: number) {
  let body: Budget | null = null
  try {
    const res = await fetch('/openrouter-key/limit')
    body = res.ok ? await res.json() as Budget : null
  } catch {
    body = null
  }
  if (!body || body.limited == null) {
    toast.warning(UNKNOWN_BUDGET)
    return true
  }
  if (body.limited === false) {
    toast.warning(UNLIMITED_KEY)
    return true
  }
  if (typeof body.remaining !== 'number') {
    toast.warning(UNKNOWN_BUDGET)
    return true
  }
  if (usd > body.remaining) {
    toast.warning(SHORT_BUDGET)
    return false
  }
  return true
}
