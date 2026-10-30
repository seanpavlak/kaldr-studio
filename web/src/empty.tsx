import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

export function EmptyState({ kicker, title, art, children }: { kicker?: string; title: string; art?: ReactNode; children: ReactNode }) {
  return (
    <motion.div
      className="empty-state"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26 }}
    >
      {art && <div className="empty-art">{art}</div>}
      {kicker && <p className="kicker">{kicker}</p>}
      <h2>{title}</h2>
      <div className="empty-copy">{children}</div>
    </motion.div>
  )
}
