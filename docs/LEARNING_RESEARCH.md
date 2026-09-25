# Capacidade de aprendizado do MaleCNS instalado

Inspeção em 25/09/2026 de `flybrain==0.1.0` em `.venv/Lib/site-packages/flybrain/brain.py` e `reservoir.py`, confrontada com o [repositório oficial](https://github.com/alextitonis/fly.ai). A API instalada é `FlyBrain(..., seed, device, batch, dt)`; `step(eye_drive=None, inject=())` devolve índices que dispararam. O upstream descreve explicitamente um cérebro congelado e um readout linear externo.

| Pergunta | Evidência na versão instalada | Conclusão |
| --- | --- | --- |
| Pesos mudam em `step()`? | `brain.py:173-195` calcula corrente com `self.weights`, atualiza `v`, `fired`, `last_spike` e `steps`; não escreve em `weights` ou `_W`. | Não. |
| Plasticidade, STDP, reward-modulated STDP? | Não há operação de atualização de sinapses em `brain.py`; `reservoir.py` diz que `FlyBrain` nunca é treinado e implementa readout externo. | Não implementadas. |
| Neuromodulação funcional / RL? | O LIF contém corrente sináptica, tônico, ruído, entrada visual/injetada, limiar e reset; não recebe recompensa. | Não implementados. PAM/PPL1 observados não equivalem a recompensa biológica. |
| Estado persiste? | `v`, `fired`, `steps`, `last_spike` e RNG são atributos de instância; `step()` atualiza-os, `reset(seed)` reinicia-os. | Sim, entre decisões, até reset manual/novo episódio. |
| O que se treina? | `reservoir.py` oferece `Readout` com ajustes externos; esta feature usa pesos de uma política linear própria sobre taxas de DNs. | Somente o readout/política. |

`brain.npz` local contém 166.700 IDs, `cell_type`, `side`, `superclass` e `positions` com forma `(166700, 3)`. São finitas 140.638 posições; o restante não deve ser plotado como anatomia. `weights.npz` fornece a matriz esparsa cujos índices correspondem aos índices de `brain.npz`. A visualização amostra neurônios e arestas reais e não representa todos os 25.582.938 contatos. Fonte do dataset: [MaleCNS v1.0](https://male-cns.janelia.org/); código que monta os pesos: [`flybrain/build.py`](https://github.com/alextitonis/fly.ai/blob/main/flybrain/build.py).

O experimento será descrito como **aprendizado de uma política de combate a partir da dinâmica neural do MaleCNS**. Não há base para dizer que os pesos do cérebro, a mosca biológica ou suas experiências subjetivas aprenderam BG3. O readout não recebe posição, HP, distância ou estado bruto do jogo; apenas taxas derivadas dos spikes. O encoder pode transformar observações em estímulos, e o RewardEngine pode observar consequências depois da ação.
