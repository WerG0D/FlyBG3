export type Node = { index: number; neuron_id: number; cell_type: string; side: string; position: [number, number, number]; activity?: number }
export type Edge = { source: number; target: number; weight_abs: number }
export type Connectome = { dataset: string; layout: string; nodes: Node[]; edges: Edge[]; source_neurons: number; sampled_neurons: number }
export type Visual = { layout: string; nodes: Node[]; edges: Edge[]; total_active: number; sampled_active: number }
export type Activity = { hz: number; spikes: number; neurons: number }
export type Event = { schema_version: number; event: string; episode_id: number; request_id: number; timestamp: string; payload: Record<string, any> }
