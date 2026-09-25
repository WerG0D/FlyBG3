# Painel web neural

O backend HTTP local em `127.0.0.1:8765` segue o `events.jsonl` do run sintético mais recente em `runtime/lab-runs`. Ele transmite eventos `schema_version=1` via **Server-Sent Events** (`/events`). React recebe stream; não lê arquivos por frame. `/api/history` fornece até mil eventos recentes para reconexão/replay, `/api/manifest` dá proveniência, `/api/status` dá estado. O processo do dashboard é separado do processo que simula MaleCNS. Se browser ou servidor cair, o runner continua; falhas do assinante de eventos são capturadas, e JSONL é a fonte durável.

```powershell
.\scripts\dashboard_build.ps1
python -m flybg3 dashboard --config config/combat-lab.toml
# em outro terminal:
python -m flybg3 arena --config config/combat-lab.toml --mode eval --policy frozen --episodes 2
```

Abra `http://127.0.0.1:8765`. Para desenvolvimento, rode o backend acima e `.\scripts\dashboard_dev.ps1` (Vite usa proxy para `/api` e `/events`). Node/npm só são necessários para **construir** o frontend; o painel pronto é servido pelo Python. A fonte visual é `dashboard/public/connectome.json`, regenerável por `python -m flybg3 export-connectome`. A exportação lê `brain.npz` e os pesos de `FlyBrain` já carregados.

O fundo desenha 1.400 soma positions reais com coordenadas normalizadas, projetadas 2D com rotação 3D interativa, e até 2.000 arestas reais entre a amostra. Por decisão, até 300 neurônios que **de fato dispararam** e 200 conexões entre eles são destacados. O dataset contém 166.700 posições de índices, das quais 140.638 são finitas nesta instalação; os demais não são inventados. Neuron IDs são os IDs de `brain.npz`; a intensidade visual indica disparo na janela, não potencial individual. Essa amostragem **não** é uma renderização completa de 25 milhões de arestas. Cores distinguem tipos anotados DN/LC/restante, não valência ou intenção.

Painéis: ambiente sintético claramente identificado, taxas brutas de grupos, ação da política, exploração, status de execução, breakdown de reward, métricas e timeline. Tooltips das barras mostram neurônios, spikes, janela e Hz. Os gráficos exibem dados crus por episódio. `TRAINING` e `EVALUATION` são separados. Ainda não há eventos de combate real BG3; controles sintéticos ficam fora do caminho de decisão até haver uma execução física confiável.

Os botões **Pause**, **Resume**, **Save Checkpoint** e **Reset Episode** enviam comandos explícitos a `/api/control`. O runner aplica-os antes da próxima decisão sintética; reset encerra o episódio como `ABORTED`, checkpoint cria arquivo novo, e pausa não altera pesos/estado do MaleCNS. Estes comandos não controlam BG3 nem habilitam `physical_actions_enabled`. O backend aceita só JSON e só atua no run ativo. Não exponha o servidor além do localhost sem autenticação.

O servidor usa fila limitada por cliente. Para `neural_state`, estado recente substitui antigo. Se um cliente não acompanhar eventos críticos, é desconectado e pode recuperar o journal em `/api/history`; o evento durável nunca é eliminado do JSONL. O overhead medido da amostra visual é registrado em `visualization_ms`; a taxa neural/ação já foi calculada antes dessa coleta. Testes com MaleCNS real comparam spikes e decisão com dashboard ligado/desligado.
