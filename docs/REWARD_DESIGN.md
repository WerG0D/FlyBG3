# Recompensa de combate

`RewardEngine` recebe somente `CombatOutcome` **após** `arena.step`/adaptador retornar. Nenhum rótulo de ação recebe bônus: a política pode propor `BASIC_ATTACK` fora de alcance e obter somente a penalidade por inválido e as consequências do turno.

| Consequência observada | Valor padrão |
| --- | ---: |
| HP causado ao alvo | +0,02 por HP |
| HP recebido | −0,02 por HP |
| inimigo morto | +1 |
| morte de Flyman | −1 |
| vitória | +3 |
| derrota | −3 |
| ação inválida | −0,05 |
| episódio encerrado por limite de turnos | −1 |

`RewardBreakdown` mantém as oito parcelas e soma `total`. `timeout` não concede vitória. A penalidade foi adicionada depois que uma execução inicial mostrou o readout recuando até o limite para obter zero de recompensa, melhor que enfrentar o inimigo e perder. Ela recompensa um **resultado terminal**, não uma ação específica. A arena usa HP não regenerável, evitando farming por cura no primeiro experimento. No BG3 real será necessário identificar alvo por UUID, ataques de outros membros, summons, regeneração e eventos de dano para atribuição causal. Sem essa instrumentação, não se deve usar uma diferença de HP como recompensa atribuída ao Flyman.

Possíveis reward hacks: prolongar combate para acumular dano em inimigo curável, atacar invocações substituíveis, favorecer dano sobre vitória, gerar invalidações previsíveis, ou deixar outros membros causarem dano atribuído ao agente. Guardas futuros: limite de turnos, recompensa terminal maior que ganhos repetitivos, alvo 1v1 identificado, logs por fonte de dano e avaliação em inimigos diferentes. Os coeficientes são hipóteses de engenharia, não uma escala biológica de motivação.
