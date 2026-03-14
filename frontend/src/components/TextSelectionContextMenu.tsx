import { useState, useEffect, useCallback, type RefObject } from 'react'

interface TextSelectionContextMenuProps {
  containerRef: RefObject<HTMLDivElement | null>
  onAddNote: (text: string) => void
  onGenerateStudyGuide: (text: string) => void
  onGenerateSampleTest: (text: string) => void
  aiAvailable?: boolean
}

export function TextSelectionContextMenu({
  containerRef,
  onAddNote,
  onGenerateStudyGuide,
  onGenerateSampleTest,
  aiAvailable = true,
}: TextSelectionContextMenuProps) {
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [selectedText, setSelectedText] = useState('')

  const hideMenu = useCallback(() => {
    setVisible(false)
    setSelectedText('')
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleContextMenu = (e: MouseEvent) => {
      const selection = window.getSelection()
      const text = selection?.toString().trim() ?? ''
      if (!text) return

      e.preventDefault()
      setSelectedText(text)
      setPosition({ x: e.clientX, y: e.clientY })
      setVisible(true)
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') hideMenu()
    }

    container.addEventListener('contextmenu', handleContextMenu)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      container.removeEventListener('contextmenu', handleContextMenu)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [containerRef, hideMenu])

  if (!visible) return null

  return (
    <div
      className="text-selection-context-menu"
      style={{ position: 'fixed', left: position.x, top: position.y }}
    >
      <button onClick={() => { onAddNote(selectedText); hideMenu() }}>
        Add Note
      </button>
      <button
        disabled={!aiAvailable}
        onClick={() => { onGenerateStudyGuide(selectedText); hideMenu() }}
      >
        Generate Study Guide
      </button>
      <button
        disabled={!aiAvailable}
        onClick={() => { onGenerateSampleTest(selectedText); hideMenu() }}
      >
        Generate Sample Test
      </button>
    </div>
  )
}
