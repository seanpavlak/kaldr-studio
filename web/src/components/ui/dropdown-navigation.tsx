import { useState, type ElementType } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'

export type DropdownItem = {
  label: string
  description: string
  icon: ElementType
  href?: string
}

export type DropdownMenu = {
  title: string
  items: DropdownItem[]
}

export type DropdownNavItem = {
  id: number
  label: string
  subMenus?: DropdownMenu[]
  link?: string
}

type Props = {
  navItems: DropdownNavItem[]
}

function herePath() {
  return window.location.pathname.replace(/\/$/, '') || '/'
}

export function DropdownNavigation({ navItems }: Props) {
  const [openMenu, setOpenMenu] = useState<string | null>(null)
  const [isHover, setIsHover] = useState<number | null>(null)

  function handleHover(menuLabel: string | null) {
    setOpenMenu(menuLabel)
  }

  return (
    <nav aria-label="Builders" className="builder-menu relative">
      <ul className="relative m-0 flex list-none items-center p-0">
        {navItems.map((navItem) => (
          <li
            key={navItem.label}
            className="relative"
            onMouseEnter={() => handleHover(navItem.subMenus ? navItem.label : null)}
            onMouseLeave={() => handleHover(null)}
            onBlur={(event) => {
              const next = event.relatedTarget
              if (!(next instanceof Node) || !event.currentTarget.contains(next)) handleHover(null)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') handleHover(null)
            }}
          >
            {navItem.link && !navItem.subMenus ? (
              <a
                href={navItem.link}
                className="relative flex cursor-pointer items-center justify-center gap-1 px-4 py-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground"
                onMouseEnter={() => setIsHover(navItem.id)}
                onMouseLeave={() => setIsHover(null)}
              >
                <span className="relative z-10">{navItem.label}</span>
                {isHover === navItem.id && (
                  <motion.div
                    layoutId="hover-bg"
                    className="absolute inset-0 size-full bg-primary/10"
                    style={{ borderRadius: 99 }}
                  />
                )}
              </a>
            ) : (
              <button
                type="button"
                className="relative flex cursor-pointer items-center justify-center gap-1 border-0 bg-transparent py-0.5 pr-2 pl-0 text-xs text-muted-foreground transition-colors duration-300 hover:text-foreground"
                aria-expanded={openMenu === navItem.label}
                aria-haspopup={navItem.subMenus ? 'menu' : undefined}
                onMouseEnter={() => setIsHover(navItem.id)}
                onMouseLeave={() => setIsHover(null)}
                onFocus={() => handleHover(navItem.subMenus ? navItem.label : null)}
              >
                <span className="relative z-10">{navItem.label}</span>
                {navItem.subMenus && (
                  <ChevronDown
                    className="relative z-10 h-3 w-3"
                  />
                )}
                {(isHover === navItem.id || openMenu === navItem.label) && (
                  <motion.div
                    layoutId="hover-bg"
                    className="absolute inset-0 size-full bg-primary/10"
                    style={{ borderRadius: 99 }}
                  />
                )}
              </button>
            )}

            <AnimatePresence>
              {openMenu === navItem.label && navItem.subMenus && (
                <div className="absolute top-full left-0 z-30 w-auto pt-2">
                  <motion.div
                    className="w-max max-w-[calc(100vw-2rem)] overflow-x-auto border border-border bg-background p-4"
                    style={{ borderRadius: 16 }}
                    layoutId="menu"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 4 }}
                    transition={{ duration: 0.16 }}
                  >
                    <div className="menu-columns">
                      {navItem.subMenus.map((sub) => (
                        <motion.div layout className="menu-column" key={sub.title}>
                          <h3 className="mx-0 mt-0 mb-4 text-sm font-medium text-muted-foreground capitalize">
                            {sub.title}
                          </h3>
                          <ul className="m-0 list-none space-y-6 p-0">
                            {sub.items.map((item) => {
                              const Icon = item.icon
                              const current = item.href ? herePath() === (item.href.replace(/\/$/, '') || '/') : false
                              return (
                                <li key={item.label}>
                                  <a
                                    href={item.href ?? '#'}
                                    aria-current={current ? 'page' : undefined}
                                    className="flex items-start gap-3 no-underline"
                                    onClick={(event) => {
                                      if (!item.href || current) event.preventDefault()
                                    }}
                                  >
                                    <div className={`menu-icon flex size-9 shrink-0 items-center justify-center rounded-md border border-border text-foreground transition-colors duration-300 ${current ? 'bg-accent text-accent-foreground' : ''}`}>
                                      <Icon className="h-5 w-5 flex-none" />
                                    </div>
                                    <div className="w-max leading-5">
                                      <p className="m-0 shrink-0 text-sm font-medium text-foreground">
                                        {item.label}
                                      </p>
                                      <p className="menu-note m-0 shrink-0 text-xs text-muted-foreground transition-colors duration-300">
                                        {item.description}
                                      </p>
                                    </div>
                                  </a>
                                </li>
                              )
                            })}
                          </ul>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>
          </li>
        ))}
      </ul>
    </nav>
  )
}
