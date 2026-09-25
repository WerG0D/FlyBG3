# Validação do readout de combate

Procedimento: cinco condições (`random`, `frozen`, `trainable`, `shuffled`, `zero`) compartilham, por seed, os mesmos estados iniciais da arena. Cada episódio reinicia o MaleCNS com a seed configurada; dentro dele a dinâmica neural continua. A política treinável retém seus pesos entre episódios, explora durante treino e usa ε=0 durante avaliação. A arena aplica ações **reais no simulador**, não no BG3. `shuffled` embaralha a correspondência entre taxa e tipo de DN a cada janela; `zero` mantém o cérebro executando mas zera as taxas entregues ao readout. Assim podemos perguntar se a informação neural agrega valor além de um intercepto treinável.

O comando usado para o primeiro ensaio é:

```powershell
python -m flybg3 validate-learning --config config/combat-lab.toml --train-episodes 3 --eval-episodes 3 --seeds 42 43 44
```

O resultado estruturado fica em [`experiments/learning_validation.json`](../experiments/learning_validation.json). Cada `runtime/lab-runs/run_*` guarda manifest, eventos, episódios, métricas e checkpoint final. A execução prévia com timeout sem penalidade foi **descartada**: ela revelou política de recuo até o limite e reward zero. Foi adicionada penalidade terminal por timeout e um teste de regressão antes da rodada atual. Não se misturam dados das duas versões da função de recompensa.

Critérios para evidência de aprendizado: aumento reproduzível de win rate e reward em avaliação (ε=0) contra random/frozen, degradação com shuffled/zero, mais de uma seed, e depois generalização em arena e BG3 real. Três episódios por seed são um teste de integração/viabilidade, **insuficiente para inferência estatística**. A conclusão será `INCONCLUSIVE` mesmo se uma média ocasional for maior.

## Primeiro resultado (3 seeds × 3 episódios de treino + 3 de avaliação)

| Condição | Vitórias médias na avaliação | Reward médio |
| --- | ---: | ---: |
| Random | 0% | −4,432 |
| Frozen | 0% | −3,274 |
| Trainable | 100% | +3,953 |
| Shuffled | 33,3% | −1,653 |
| Zero (somente intercepto) | 66,7% | +1,134 |

O readout treinado venceu 9/9 avaliações iniciais no oponente A, mas o controle **sem informação neural** venceu 6/9. Portanto, esse ensaio não demonstra que as taxas descendentes são necessárias para a vitória. O conjunto é pequeno, e o oponente A avança sozinho até o alcance de ataque. Um agente que repete `BASIC_ATTACK` pode vencer sem ajustar sua ação à distância.

Na avaliação separada em B (maior HP, mais dano e distância inicial), os checkpoints das seeds 42/43/44 venceram respectivamente 2/3, 1/3 e 0/3 partidas; **todas as ações foram `BASIC_ATTACK`**. Na arena C, em que um inimigo recua e atacar fora de alcance não reduz a distância, os mesmos checkpoints venceram 0/3 em **cada seed** e continuaram escolhendo somente `BASIC_ATTACK`. A queda de desempenho reforça que a política inicial aprendeu um atalho na arena A. O resultado por episódio está em [`experiments/generalization.json`](../experiments/generalization.json).

Uma continuação da seed 42 por mais 24 episódios em A venceu 23/24 no treino e 6/6 na avaliação. As **39 decisões de avaliação** ainda foram todas `BASIC_ATTACK`. O mesmo checkpoint, congelado em C, perdeu 6/6, causou zero dano e tentou `BASIC_ATTACK` 88 vezes. Continuar esse checkpoint por 40 episódios em C também falhou: 0/40 vitórias no treino e 0/8 na avaliação; a avaliação causou zero dano. A política passou a alternar ações, porém não produziu uma sequência eficaz. Os arquivos detalhados estão em `runtime/lab-runs/run_manual_a540b79c`, `run_manual_867e1fe0` e `run_manual_474aa8e2`.

O diagnóstico offline [`experiments/feature_diagnostics_C.json`](../experiments/feature_diagnostics_C.json) encontrou 48 janelas dentro do alcance em 700 janelas da continuação C, mas nenhum dano no episódio. DNp01 L/R tiveram médias de 16,65/15,27 Hz perto e 6,76/5,95 Hz longe. Isso sugere que *alguma* diferença de estado atravessa o MaleCNS, mas a comparação é observacional e confunde distância, HP e tempo. Não prova codificação causal nem uso apropriado pelo readout.

O currículo D, iniciado a partir do checkpoint A com `ε=0,7`, teve 10/40 vitórias **durante exploração**. A avaliação posterior com ε=0 perdeu 8/8: as 176 ações foram `IDLE`, sem causar dano. O caminho vencedor `APPROACH` seguido de `BASIC_ATTACK` é possível e está coberto por teste, mas o readout TD de um passo não o preservou. Isso é um **resultado negativo de aprendizado**, não uma falha de conexão ao MaleCNS. Os detalhes estão em `runtime/lab-runs/run_manual_e1f0f7c2` e no resumo [`experiments/continuation.json`](../experiments/continuation.json).

Na avaliação pareada do mesmo checkpoint D, zerar ou embaralhar as taxas de DNs não mudou nenhuma das 176 ações: `IDLE` em 8/8 episódios para ambas as ablações, mesmo resultado/reward do readout normal. Portanto, **a política final não demonstrou dependência funcional das features neurais** nesse teste. Não ativamos ataque físico no BG3 com essa política.

Conclusão: `INCONCLUSIVE`. Não há base para afirmar aprendizado de combate neural generalizável, nem para ativar `BASIC_ATTACK` no BG3. A próxima avaliação exige alternância entre aproximação e ataque, seguida de ablações e repetição em mais seeds.
