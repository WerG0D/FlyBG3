import { useEffect, useMemo, useRef, useState } from 'react'
import BrainView from './BrainView'
import type { Activity, Connectome, Event, Visual } from './types'

const MAX_EVENTS = 1200
const label: Record<string, string> = {
  steer_left: 'STEER LEFT', steer_right: 'STEER RIGHT', escape: 'ESCAPE',
  grooming: 'GROOMING', pam: 'PAM', ppl1: 'PPL1'
}
const scales: Record<string, number> = { steer_left: 10, steer_right: 10, escape: 50, grooming: 10, pam: 50, ppl1: 50 }
const number = (value: unknown, decimals = 1) => typeof value === 'number' ? value.toFixed(decimals) : '—'

function latest(events: Event[], kind: string) {
  return [...events].reverse().find(e => e.event === kind)
}

function LineChart({ values, color, label }: { values: number[]; color: string; label: string }) {
  const min = Math.min(0, ...values), max = Math.max(1, ...values), span = Math.max(max - min, .01)
  const points = values.map((value, i) => `${(i / Math.max(1, values.length - 1)) * 100},${37 - ((value - min) / span) * 30}`).join(' ')
  return <div className="chart"><div className="chart-title"><span>{label}</span><strong>{values.length ? number(values[values.length - 1], 2) : '—'}</strong></div>
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-label={`${label} raw values by episode`}>
      <line x1="0" x2="100" y1="37" y2="37" stroke="#27414b" strokeWidth=".5" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
    </svg><span className="chart-caption">UNSMOOTHED · {values.length} EPISODES</span></div>
}

function Bar({ name, value, max }: { name: string; value: Activity; max: number }) {
  const width = Math.min(100, Math.max(0, value.hz / max * 100))
  return <div className="activity-row" title={`${name}: ${value.spikes} spikes / ${value.neurons} neurons in decision window; ${value.hz.toFixed(2)} Hz per neuron. Experimental functional label.`}>
    <span>{label[name] || name.toUpperCase()}</span><div className="activity-track"><div style={{ width: `${width}%` }} /></div>
    <strong>{number(value.hz, 2)} <small>Hz</small></strong>
  </div>
}

export default function App() {
  const [events, setEvents] = useState<Event[]>([])
  const [structure, setStructure] = useState<Connectome | null>(null)
  const [connected, setConnected] = useState(false)
  const [run, setRun] = useState<string | null>(null)
  const runRef = useRef<string | null>(null)
  const [view, setView] = useState<'live' | 'replay'>('live')
  const [selectedEpisode, setSelectedEpisode] = useState<number | null>(null)
  const [controlMessage, setControlMessage] = useState('')

  useEffect(() => {
    fetch('/connectome.json').then(r => r.json()).then(setStructure).catch(() => {})
    fetch('/api/history').then(r => r.json()).then((history: Event[]) => {
      if (Array.isArray(history)) setEvents(history.slice(-MAX_EVENTS))
    }).catch(() => {})
    const source = new EventSource('/events')
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
    source.onmessage = message => {
      try {
        const event = JSON.parse(message.data) as Event
        if (event.event === 'system_status' && event.payload.run !== undefined) {
          const nextRun = event.payload.run || null
          if (nextRun !== runRef.current) {
            runRef.current = nextRun
            setRun(nextRun)
            setEvents([event])
            return
          }
        }
        setEvents(previous => [...previous, event].slice(-MAX_EVENTS))
      } catch { /* a broken dashboard event cannot affect the bridge */ }
    }
    return () => source.close()
  }, [])

  const visible = useMemo(() => view === 'replay' && selectedEpisode !== null
    ? events.filter(e => e.episode_id === selectedEpisode)
    : events, [events, view, selectedEpisode])
  const neural = latest(visible, 'neural_state')?.payload
  const combat = latest(visible, 'combat_state')?.payload
  const policy = latest(visible, 'policy_decision')?.payload
  const execution = latest(visible, 'action_result')?.payload
  const reward = latest(visible, 'reward')?.payload
  const metrics = latest(visible, 'training_metrics')?.payload
  const episode = latest(visible, 'episode_end')?.payload
  const visualization = neural?.visualization as Visual | null
  const groups = (neural?.telemetry?.groups || {}) as Record<string, Activity>
  const summary = metrics?.summary || {}
  const wins = (metrics?.win_series || []) as number[]
  let winsSoFar = 0
  const cumulativeWinRate = wins.map((value, index) => { winsSoFar += value; return winsSoFar / (index + 1) })
  const results = [...new Set(events.filter(e => e.event === 'episode_end').map(e => e.episode_id))].sort((a, b) => b - a)
  const timeline = visible.filter(e => !['neural_state', 'combat_state', 'training_metrics'].includes(e.event)).slice(-9).reverse()
  const mode = metrics?.phase === 'eval' ? 'EVALUATION'
    : metrics?.policy === 'random' || metrics?.policy === 'frozen' || metrics?.phase === 'control' ? 'CONTROL'
    : metrics?.phase === 'train' ? 'TRAINING' : 'OBSERVE'
  const physical = combat?.source === 'synthetic_arena' ? 'SYNTHETIC ARENA' : 'BG3 GAME STATE'
  const paused = latest(events, 'system_status')?.payload?.status === 'paused'
  const sendControl = async (command: string) => {
    try {
      const response = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command }) })
      const body = await response.json()
      setControlMessage(response.ok ? `${command.toUpperCase()} ACCEPTED` : body.error)
    } catch { setControlMessage('CONTROL UNAVAILABLE') }
  }

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark">F<span>·</span></div><div><strong>FlyBG3</strong><small>COMBAT LEARNING LAB</small></div></div>
      <div className="top-status"><span className={`status-dot ${connected ? 'online' : ''}`} /> {connected ? 'STREAM CONNECTED' : 'WAITING FOR STREAM'} <span className="divider" /> MaleCNS v1.0 <span className="divider" /> {mode}</div>
      <div className="top-clock">EPISODE <strong>{latest(events, 'episode_end')?.episode_id ?? '—'}</strong><span className="top-clock-line">{run ? run.split(/[\\/]/).pop() : 'NO RUN SELECTED'}</span></div>
    </header>

    <main className="dashboard-grid">
      <section className="card brain-card"><div className="card-head"><div><span className="eyebrow">01 / CONNECTOME</span><h2>Neural field</h2></div><span className="head-note">ANATOMICAL PROJECTION · DRAG TO ROTATE</span></div>
        <BrainView structure={structure} active={visualization} />
        <div className="brain-footer"><span><i className="legend-dot basal" /> STRUCTURAL SAMPLE</span><span><i className="legend-dot active" /> SPIKED IN WINDOW</span><span><i className="legend-dot edge" /> SAMPLED CONNECTIONS</span></div>
      </section>

      <section className="card combat-card"><div className="card-head"><div><span className="eyebrow">02 / ENVIRONMENT</span><h2>Combat state</h2></div><span className="section-tag">{physical}</span></div>
        <div className="hp-block"><div><span>FLYMAN</span><strong>{combat?.npc_hp ?? '—'} <small>HP</small></strong></div><div className="hp-bar"><div style={{ width: `${Math.max(0, Math.min(100, (combat?.npc_hp || 0) / 22 * 100))}%` }} /></div></div>
        <div className="hp-block hostile"><div><span>HOSTILE</span><strong>{combat?.enemy_hp ?? '—'} <small>HP</small></strong></div><div className="hp-bar"><div style={{ width: `${Math.max(0, Math.min(100, (combat?.enemy_hp || 0) / 20 * 100))}%` }} /></div></div>
        <div className="metric-grid"><div><span>SEPARATION</span><strong>{number(combat?.distance)} <small>m</small></strong></div><div><span>TURN</span><strong>{combat?.my_turn ? 'FLYMAN' : '—'}</strong></div><div><span>DATA SOURCE</span><strong>{combat?.source === 'synthetic_arena' ? 'SIMULATED' : 'BG3 / NONE'}</strong></div><div><span>DECISION WINDOW</span><strong>{number(neural?.telemetry?.window_seconds, 2)} <small>s</small></strong></div></div>
        <div className="mode-warning">GAME STATE IS DISPLAY ONLY. THE POLICY RECEIVES NEURAL RATES.</div>
      </section>

      <section className="card activity-card"><div className="card-head"><div><span className="eyebrow">03 / DESCENDING OUTPUT</span><h2>Neural activity</h2></div><span className="head-note">SPIKES / NEURON / SECOND</span></div>
        <div className="activities">{Object.entries(groups).length ? Object.entries(groups).map(([key, value]) =>
          <Bar key={key} name={key} value={value} max={scales[key] || 10} />) : <div className="empty">Waiting for MaleCNS telemetry…</div>}</div>
        <div className="activity-foot"><span>ACTIVE NEURONS <strong>{neural?.telemetry?.active_neurons?.toLocaleString() ?? '—'}</strong></span><span>TOTAL SPIKES <strong>{neural?.telemetry?.total_spikes?.toLocaleString() ?? '—'}</strong></span></div>
      </section>

      <section className="card action-card"><div className="card-head"><div><span className="eyebrow">04 / NEURAL READOUT</span><h2>Action & outcome</h2></div><span className="section-tag cyan">{policy?.explore ? 'EXPLORE' : 'EXPLOIT'}</span></div>
        <div className="hero-action">{policy?.action?.replace('_', ' ').toUpperCase() ?? 'WAITING'}</div>
        <div className="action-details"><div><span>EXECUTION</span><strong className={execution?.status === 'invalid' ? 'danger' : ''}>{execution?.status?.toUpperCase() ?? 'PENDING'}</strong></div><div><span>ε / EXPLORATION</span><strong>{number(policy?.epsilon, 3)}</strong></div><div><span>POLICY LATENCY</span><strong>{number(policy?.policy_ms, 2)} ms</strong></div><div><span>BRAIN LATENCY</span><strong>{number(neural?.brain_ms, 1)} ms</strong></div></div>
        {execution?.reason && <div className="invalid-reason">{execution.reason}</div>}
      </section>

      <section className="card learning-card"><div className="card-head"><div><span className="eyebrow">05 / LEARNING</span><h2>Episode metrics</h2></div><span className={`section-tag ${mode === 'TRAINING' ? 'amber' : ''}`}>{mode}</span></div>
        <div className="learning-stats"><div><span>EPISODES</span><strong>{summary.episodes ?? '—'}</strong></div><div><span>WIN RATE</span><strong>{typeof summary.win_rate === 'number' ? `${(summary.win_rate * 100).toFixed(0)}%` : '—'}</strong></div><div><span>ROLLING / 20</span><strong>{typeof summary.rolling_win_rate_20 === 'number' ? `${(summary.rolling_win_rate_20 * 100).toFixed(0)}%` : '—'}</strong></div><div><span>MEAN REWARD</span><strong>{number(summary.mean_reward, 2)}</strong></div></div>
        <div className="charts"><LineChart label="REWARD × EPISODE" values={metrics?.reward_series || []} color="#86e9b7" /><LineChart label="CUMULATIVE WIN RATE" values={cumulativeWinRate} color="#f2b775" /></div>
        <div className="controls"><div className="tiny-label">ARENA CONTROLS · NEVER CHANGE MALECNS WEIGHTS</div><div className="control-buttons"><button onClick={() => sendControl(paused ? 'resume' : 'pause')}>{paused ? 'RESUME' : 'PAUSE'}</button><button onClick={() => sendControl('checkpoint')}>SAVE CHECKPOINT</button><button onClick={() => sendControl('reset_episode')}>RESET EPISODE</button></div><small>{controlMessage || 'Commands apply before the next arena decision.'}</small></div>
      </section>

      <section className="card reward-card"><div className="card-head"><div><span className="eyebrow">06 / CONSEQUENCE</span><h2>Reward breakdown</h2></div><strong className="reward-total">{typeof reward?.total === 'number' ? `${reward.total >= 0 ? '+' : ''}${reward.total.toFixed(2)}` : '—'}</strong></div>
        <div className="reward-rows">{['damage_dealt', 'damage_received', 'kill', 'death', 'victory', 'defeat', 'invalid', 'timeout'].map(key => <div key={key}><span>{key.replace('_', ' ').toUpperCase()}</span><strong className={reward?.[key] < 0 ? 'danger' : ''}>{typeof reward?.[key] === 'number' ? `${reward[key] >= 0 ? '+' : ''}${number(reward[key], 2)}` : '—'}</strong></div>)}</div>
        <div className="episode-total"><span>EPISODE TOTAL</span><strong>{number(episode?.total_reward, 2)}</strong></div>
      </section>

      <section className="card timeline-card"><div className="card-head"><div><span className="eyebrow">07 / EVENT JOURNAL</span><h2>Timeline</h2></div><div className="view-switch"><button className={view === 'live' ? 'selected' : ''} onClick={() => setView('live')}>LIVE</button><button className={view === 'replay' ? 'selected' : ''} onClick={() => { setView('replay'); setSelectedEpisode(results[0] ?? null) }}>REPLAY</button></div></div>
        {view === 'replay' && <select value={selectedEpisode ?? ''} onChange={e => setSelectedEpisode(Number(e.target.value))}><option value="">SELECT EPISODE</option>{results.map(id => <option key={id} value={id}>Episode {id}</option>)}</select>}
        <div className="timeline">{timeline.length ? timeline.map((e, i) => <div className="timeline-row" key={`${e.timestamp}-${i}`}><span className="timeline-time">{e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}</span><span className={`timeline-mark ${e.event}`} /><span className="timeline-name">{e.event.replaceAll('_', ' ').toUpperCase()}</span><span className="timeline-value">{e.event === 'policy_decision' ? e.payload.action : e.event === 'reward' ? number(e.payload.total, 2) : e.event === 'episode_end' ? e.payload.result : e.event === 'action_result' ? e.payload.status : ''}</span></div>) : <div className="empty">No combat events yet.</div>}</div>
      </section>
    </main>
    <footer>FLYBG3 · FIXED MALECNS / TRAINABLE LINEAR READOUT <span>Neural rates are simulated signals, not thoughts or biological reward.</span></footer>
  </div>
}
