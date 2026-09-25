import { useEffect, useRef, useState } from 'react'
import type { Connectome, Edge, Node, Visual } from './types'

type Props = { structure: Connectome | null; active: Visual | null }

function color(node: Node, active: boolean) {
  if (active) return '#a5ffcc'
  if (node.cell_type.startsWith('DN')) return '#3b968d'
  if (node.cell_type.startsWith('LC') || node.cell_type.startsWith('LPLC')) return '#816fa3'
  return '#566a77'
}

export default function BrainView({ structure, active }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const angle = useRef(0.25)
  const dragging = useRef(false)
  const [hover, setHover] = useState<Node | null>(null)
  const projected = useRef<{ x: number; y: number; node: Node }[]>([])

  useEffect(() => {
    const element = canvas.current
    if (!element || !structure) return
    const ctx = element.getContext('2d')!
    let frame = 0, last = 0
    const draw = (now: number) => {
      frame = requestAnimationFrame(draw)
      if (now - last < 33) return
      last = now
      const width = element.clientWidth, height = element.clientHeight
      const scale = window.devicePixelRatio || 1
      if (element.width !== Math.round(width * scale) || element.height !== Math.round(height * scale)) {
        element.width = Math.round(width * scale); element.height = Math.round(height * scale)
      }
      ctx.setTransform(scale, 0, 0, scale, 0, 0)
      ctx.clearRect(0, 0, width, height)
      const gradient = ctx.createRadialGradient(width * .5, height * .48, 20, width * .5, height * .48, width * .6)
      gradient.addColorStop(0, '#143038'); gradient.addColorStop(1, '#09161f')
      ctx.fillStyle = gradient; ctx.fillRect(0, 0, width, height)
      if (!dragging.current) angle.current += .0006
      const cos = Math.cos(angle.current), sin = Math.sin(angle.current)
      const project = (node: Node) => {
        const [x, y, z] = node.position
        const rotatedX = x * cos + z * sin
        const depth = z * cos - x * sin
        const factor = Math.min(width * .41, height * .42) / (1 + .12 * depth)
        return { x: width * .5 + rotatedX * factor, y: height * .51 - y * factor, node }
      }
      const staticPoints = structure.nodes.map(project)
      const staticByIndex = new Map(staticPoints.map(p => [p.node.index, p]))
      const drawEdges = (edges: Edge[], points: Map<number, ReturnType<typeof project>>, opacity: number) => {
        ctx.strokeStyle = `rgba(86,195,182,${opacity})`; ctx.lineWidth = .55
        ctx.beginPath()
        for (const edge of edges) {
          const a = points.get(edge.source), b = points.get(edge.target)
          if (a && b) { ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y) }
        }
        ctx.stroke()
      }
      drawEdges(structure.edges, staticByIndex, .09)
      for (const point of staticPoints) {
        ctx.fillStyle = color(point.node, false)
        ctx.globalAlpha = .42
        ctx.beginPath(); ctx.arc(point.x, point.y, 1.05, 0, Math.PI * 2); ctx.fill()
      }
      ctx.globalAlpha = 1
      const activePoints = (active?.nodes || []).map(project)
      const activeByIndex = new Map(activePoints.map(p => [p.node.index, p]))
      drawEdges(active?.edges || [], activeByIndex, .32)
      for (const point of activePoints) {
        ctx.shadowBlur = 13; ctx.shadowColor = '#65f4bd'
        ctx.fillStyle = color(point.node, true)
        ctx.beginPath(); ctx.arc(point.x, point.y, 2.3, 0, Math.PI * 2); ctx.fill()
      }
      ctx.shadowBlur = 0
      projected.current = [...activePoints, ...staticPoints]
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [structure, active])

  return <div className="brain-visual" onPointerDown={e => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId) }}
    onPointerUp={() => { dragging.current = false }}
    onPointerMove={e => {
      if (dragging.current) angle.current += e.movementX * .007
      const rect = e.currentTarget.getBoundingClientRect()
      const x = e.clientX - rect.left, y = e.clientY - rect.top
      let best: Node | null = null, distance = 100
      for (const p of projected.current) { const d = (p.x - x) ** 2 + (p.y - y) ** 2; if (d < distance) { distance = d; best = p.node } }
      setHover(best)
    }} onPointerLeave={() => setHover(null)}>
    <canvas ref={canvas} aria-label="Projected MaleCNS neuron positions and active sample" />
    <div className="brain-corner top-left"><span className="tiny-label">DATASET</span><strong>MaleCNS v1.0</strong></div>
    <div className="brain-corner top-right"><span className="tiny-label">ACTIVE THIS WINDOW</span><strong>{active?.total_active?.toLocaleString() ?? '—'}</strong></div>
    <div className="brain-corner bottom-left"><span className="tiny-label">ANATOMICAL SAMPLE</span><strong>{structure?.sampled_neurons.toLocaleString() ?? '—'} / {structure?.source_neurons.toLocaleString() ?? '—'}</strong></div>
    <div className="brain-corner bottom-right"><span className="tiny-label">ACTIVE DISPLAY</span><strong>{active?.sampled_active ?? 0} neurons</strong></div>
    {hover && <div className="brain-tooltip">ID {hover.neuron_id} · {hover.cell_type || 'untyped'} · {hover.side || 'unassigned'}</div>}
  </div>
}
