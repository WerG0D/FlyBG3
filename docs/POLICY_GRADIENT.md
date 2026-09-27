# Readout episódico de política

Esta é uma segunda hipótese experimental para o **readout externo** de combate. O MaleCNS, seus pesos e sua dinâmica LIF não mudam. A política recebe somente as 14 taxas de neurônios descendentes já extraídas; o ambiente calcula a recompensa **após** executar a ação. Não há acesso da política a distância, HP, ângulo, posição, UUID ou outro estado bruto do BG3.

O TD linear de um passo anterior venceu na arena A repetindo ataque, mas não transferiu para C. No currículo D, obteve 10 vitórias exploratórias em 40 episódios e depois escolheu apenas `IDLE` nas 176 decisões de avaliação. Por isso, este ensaio testa uma atribuição de crédito que alcança ações anteriores ao resultado terminal, sem alterar a recompensa.

Para o vetor neural normalizado `z_t`, a política estocástica é `π(a|z_t) = softmax((W_a · z_t)/T)`. Um episódio concluído fornece o retorno descontado `G_t = Σ_{k=t}^{fim} γ^(k-t) r_k`. O baseline `b_t` é a média dos retornos observados em **episódios anteriores** no mesmo índice de passo; ele independe da ação. Depois do episódio inteiro, o readout aplica:

```text
gradient_a = Σ_t [(G_t - b_t) / (S · T)] · [1(a_t=a) - π(a|z_t)] · z_t
W ← W + α · clip_norm(gradient, C)
```

`S` é a escala configurada do retorno e `C` limita a norma do gradiente. `α`, `γ`, `T`, `S` e `C` constam de `config/combat-reinforce.toml`. O treino amostra da softmax com RNG seeded; a avaliação escolhe o maior logit e não atualiza pesos ou baseline. O checkpoint salva pesos, baselines, contagens, seed e estado RNG. Se o usuário pedir checkpoint durante um episódio, a gravação é adiada até o fim dele, pois o estado completo do MaleCNS durante um episódio não é salvo.

Este algoritmo é uma forma pequena de [REINFORCE](https://doi.org/10.1007/BF00992696), com função de política linear. A teoria de gradiente de política com aproximação funcional é discutida por [Sutton e colaboradores (NeurIPS 1999)](https://papers.nips.cc/paper/1999/hash/464d828b85b0bed98e80ade0a5c43b0f-Abstract.html). A aplicação aqui é experimental: poucos episódios, recompensa esparsa, representação neural comprimida e arena artificial não garantem convergência ou transferência para BG3.

```powershell
.\.venv\Scripts\python.exe -m flybg3 arena --config config/combat-reinforce.toml --mode train --policy trainable --opponent D --episodes 60 --eval-episodes 10
```

Para uma ablação pareada, use o checkpoint final e os mesmos índices de avaliação:

```powershell
.\.venv\Scripts\python.exe -m flybg3 arena --config config/combat-reinforce.toml --mode eval --policy zero --opponent D --episodes 10 --checkpoint CAMINHO_DO_CHECKPOINT
.\.venv\Scripts\python.exe -m flybg3 arena --config config/combat-reinforce.toml --mode eval --policy shuffled --opponent D --episodes 10 --checkpoint CAMINHO_DO_CHECKPOINT
```

O `zero` mantém a simulação MaleCNS funcionando, mas zera taxas entregues ao readout. `shuffled` permuta as taxas antes do readout. São controles para verificar se qualquer resultado depende da *informação* neural. A arena D é um currículo; sucesso nela não valida C ou BG3. O resultado deste ensaio deve ser comparado com TD, controles e outras seeds antes de habilitar ataque físico.

## Resultados observados — seed 42

Todos os ensaios usaram o MaleCNS real, 50 passos de 20 ms por decisão, pesos sinápticos congelados, a mesma recompensa e oponente sintético D ou C. A avaliação é determinística e não atualiza o readout.

| Readout / condição | Treino | Avaliação | Vitórias |
| --- | --- | --- | ---: |
| REINFORCE, D | 60 episódios D | D, IDs 61–70 | 6/10 |
| TD, D | 60 episódios D | D, IDs 61–70 | 6/10 |
| REINFORCE, taxas zeradas | checkpoint D/60 | D, IDs 61–70 | 0/10 |
| REINFORCE, taxas embaralhadas | checkpoint D/60 | D, IDs 61–70 | 3/10 |
| REINFORCE, sem adaptação C | checkpoint D/60 | C, IDs 61–70 | 0/10 |
| TD, sem adaptação C | checkpoint D/60 | C, IDs 61–70 | 0/10 |
| REINFORCE, adaptado em C | +40 episódios C | C, IDs 101–110 | 10/10 |
| REINFORCE adaptado, taxas zeradas | checkpoint C/100 | C, IDs 101–110 | 0/10 |
| REINFORCE adaptado, taxas embaralhadas | checkpoint C/100 | C, IDs 101–110 | 1/10 |

Os readouts TD e REINFORCE escolheram **as mesmas ações em todas as dez avaliações pareadas em D**. Portanto, D não mostra superioridade de um algoritmo. Nos 40 episódios de adaptação C, o REINFORCE venceu 10; a política de treino amostra ações, enquanto a avaliação usa argmax, o que explica parte da diferença entre 10/40 em treino e 10/10 em avaliação. Isso não prova convergência estável.

Para evitar comparar apenas lotes de arena diferentes, `tools/evaluate_checkpoints.py` avaliou os checkpoints REINFORCE de 60 e 100 episódios nas **mesmas** dez arenas C inéditas, IDs 1001–1010. O checkpoint anterior venceu **0/10**, o posterior **10/10**; a recompensa média foi −4,357 versus +3,929. Após adaptação, a política usou 50 `APPROACH` e 60 `BASIC_ATTACK`, contra 105 e 41 antes, e terminou em média em 11,0 turnos contra 14,6. O registro [policy_gradient_holdout.json](../experiments/policy_gradient_holdout.json) contém resultados por episódio, hashes dos checkpoints, configuração, seed e latências.

```powershell
python tools/evaluate_checkpoints.py CAMINHO_CHECKPOINT_D60 CAMINHO_CHECKPOINT_C100 --config config/combat-reinforce.toml --opponent C --seed 42 --first-episode 1001 --episodes 10 --output experiments/policy_gradient_holdout.json
```

Esta é uma observação em **uma seed** e no mesmo tipo de oponente sintético C usado para adaptação. Ainda faltam replicações com outras seeds e teste de transferência para outro tipo de adversário. Nem D nem C reproduzem economia de turnos, AP, pathfinding, habilidades ou adversários reais do BG3. Nenhuma capacidade de ataque físico foi ativada no jogo.
As ablações posteriores do checkpoint C/100 derrubaram a avaliação de 10/10 para 0/10 com taxas zeradas e 1/10 com taxas embaralhadas, mantendo a simulação neural em execução. O resumo legível por máquina está em [policy_gradient_ablation.json](../experiments/policy_gradient_ablation.json). Isso sustenta dependência da **informação** neural dentro deste teste, sem identificar quais neurônios causam uma ação específica. Ainda faltam replicações com outras seeds e adversários.
