# Combat Learning Lab

O MaleCNS v1.0 permanece fixo. O primeiro ambiente é uma arena 1v1 **sintética** com o mesmo `SensoryEncoder`, `Simulation`/`FlyBrainAdapter` e `NeuralFeatureExtractor` que serão usados em uma integração posterior com BG3. O ambiente executa ações, relata consequências e só então o `RewardEngine` calcula recompensa. Este milestone não demonstra ainda ataque ou aprendizado em um save real.

```text
Arena observation → SensoryEncoder → MaleCNS (50 × 20 ms)
                                          ↓ taxas de DNs
                               NeuralFeatureExtractor
                                          ↓
                                CombatPolicy linear
                                          ↓ ação
                             arena.step(action)
                                          ↓ outcome
                                 RewardEngine
                                          ↓ reward
                         next observation → MaleCNS → TD update
```

`CombatPolicy.select_action(features: NeuralFeatures, training=...)` não aceita `observation`, posição, HP, distância, combate ou cooldown. As 14 features são Hz por neurônio, em ordem fixa: DNa02 L/R, DNp01 L/R, DNg100 L/R, MDN L/R, DNp02 L/R, DNp11 L/R, aSP22 L/R. Os últimos seis são sondas candidatas; nenhum deles foi validado como comando de ataque. A coluna `BASIC_ATTACK` é uma associação *aprendida* a partir dessas taxas, não uma alegação de que um DN específico signifique atacar. Cada valor é dividido por 50 Hz e limitado a 1; acrescenta-se intercepto 1.

O encoder validado anterior permanece igual por padrão. Para a arena, `config/combat-lab.toml` liga dois canais experimentais: `proximity_gain=0.6` aumenta a entrada de tracking LC10a com o tamanho angular abstrato do alvo; `health_stress_gain=0.4` soma um sinal bilateral a LC4 conforme a fração de HP perdida. O segundo é uma **proxy visceral experimental**, não nocicepção identificada em MaleCNS. Posição relativa e velocidade já entravam como laterality/looming. Ambos os ganhos são zero em `config/default.toml` para preservar a sessão BG3 validada.

## Espaço de ações e ambiente

`IDLE`, `APPROACH`, `RETREAT`, `BASIC_ATTACK`, `END_TURN`. A arena começa com Flyman de 22 HP, inimigo de 14–20 HP e separação aleatória de 2–6 m. `APPROACH` reduz 2 m; `RETREAT` aumenta 2 m; ataque básico só é válido a até 1,5 m e causa 3–6 HP; o inimigo avança 1 m se longe ou causa 2–5 HP se adjacente. Números são regras artificiais do **ambiente**, não comportamento imposto à política. Ataque inválido retorna `status=invalid` e razão; nunca vira aproximação automaticamente. Fim após vitória, derrota ou `max_turns` (24); timeout recebe reward terminal −1 para evitar a estratégia trivial de recuar indefinidamente. `END_TURN` e `IDLE` cedem a ação ao inimigo neste simulador mínimo.

## Política, treino e avaliação

`TrainableNeuralReadoutPolicy` usa cinco linhas de pesos lineares, uma por ação: `Q_a(x)=w_a·x`. A seleção é ε-greedy seeded (`ε=0.2` inicialmente). Após observar a consequência e obter a **próxima janela neural**, um passo TD atualiza somente a linha da ação escolhida: `δ = r + γ max_a Q_a(x') − Q_action(x)`; `w_action ← w_action + α δ x`, com `α=0.05`, `γ=0.9`. No estado terminal, o termo futuro é zero. Clipes numéricos limitam `δ` e os pesos. Isso é aproximação linear de Q, não aprendizado sináptico e não garantia de convergência. `EVAL` força ε=0 e proíbe updates; não altera o checkpoint.

Controles: `RandomPolicy` seeded; `FrozenPolicy` usa exatamente os pesos iniciais seeded sem updates; `Trainable` treina; `Shuffled` permuta o vetor de taxas a cada janela antes da mesma política treinável; `Zero` entrega taxas zero, mantendo só intercepto. O MaleCNS **ainda é executado** em ambos os controles de ablação. Os cinco recebem os mesmos estados iniciais de arena para uma seed e índice de episódio. A ablação mede dependência da *informação* neural, não ausência da simulação.

## Execução

```powershell
python -m flybg3 arena --config config/combat-lab.toml --mode eval --policy frozen --episodes 2
python -m flybg3 arena --config config/combat-lab.toml --mode train --policy trainable --episodes 10
python -m flybg3 validate-learning --config config/combat-lab.toml --train-episodes 3 --eval-episodes 3 --seeds 42 43 44
# Continue os pesos do readout; mantém também estado RNG quando o checkpoint é novo.
python -m flybg3 arena --config config/combat-lab.toml --mode train --policy trainable --opponent C --episodes 40 --eval-episodes 8 --checkpoint runtime/lab-runs/RUN/checkpoints/policy_final_XXXX.json
# Currículo D com maior exploração, quando C direto não produz vitórias.
python -m flybg3 arena --config config/combat-lab.toml --mode train --policy trainable --opponent D --episodes 40 --eval-episodes 8 --exploration 0.7 --checkpoint runtime/lab-runs/RUN/checkpoints/policy_final_XXXX.json
# Diagnóstico separado: remove as taxas neurais, preservando o mesmo readout.
python -m flybg3 arena --config config/combat-lab.toml --mode eval --policy zero --opponent C --episodes 8 --checkpoint runtime/lab-runs/RUN/checkpoints/policy_final_XXXX.json
```

Rastreamento completo fica em `runtime/lab-runs/run_*/`: `manifest.json`, `events.jsonl`, `episodes.jsonl`, `metrics.json`, `checkpoints/`. O arquivo agregado é `experiments/learning_validation.json`. Manifests registram seed, SHA/branch/sujeira Git, Python, flybrain, MaleCNS, configuração completa e hash SHA-256, SHA-256 dos módulos essenciais (nos novos runs), algoritmo e recompensa. Checkpoints não sobrescrevem um nome existente. A continuidade neural vale dentro de um episódio; cada novo episódio reinicia o LIF e o decoder. A política e seu RNG persistem durante treino e avaliação na mesma execução.

`--checkpoint` retoma pesos, ε e contador de episódios. Checkpoints recentes também preservam o estado do RNG; os primeiros checkpoints v1 não tinham esse campo, então sua retomada conserva os pesos mas reinicia a sequência aleatória da seed. O manifest de continuação registra caminho, SHA-256 e `rng_state_restored`; os índices da arena avançam a partir do contador anterior. Use `--mode eval` para impedir updates. `--policy zero` e `--policy shuffled` com checkpoint são ablações somente de avaliação.

Oponente C é um teste sintético adicional: inicia a 3–7 m, recua 0,5 m se fora do alcance e causa 1–2 HP por turno. Portanto, uma política que apenas repete ataque fora de alcance não causa dano. Os oponentes A e B preservam suas regras originais. Esses ambientes artificiais medem propriedade de aprendizado, não demonstram desempenho no BG3. `tools/analyze_lab_run.py RUN --output experiments/feature_diagnostics.json` calcula, **fora do loop de decisão**, taxas médias por DN em janelas dentro/fora do alcance; não injeta estado da arena na política.

Após a falha no C, foi adicionado o oponente D como **currículo**, sem mudar recompensa nem algoritmo: começa a 2–3,5 m, tem 6–10 HP, recua 0,25 m e causa 1 HP por turno. Ainda exige aproximar e depois atacar; atacar repetidamente fora do alcance permanece inútil. `--exploration 0.7` pode ampliar a busca durante o treino e fica registrado no manifest. A avaliação usa ε=0 independentemente desse valor. Ganhar no D não prova que a política vencerá no C; essa transferência deve ser medida separadamente.

Com ~0,2 s por janela neural em CPU, milhares de episódios podem levar horas. Não há atalho que substitua o connectome na arena. Diminuição de `simulation_steps` altera o experimento e deve ser registrada na configuração.

## Modos BG3

`[combat].mode=observe|validate|train|eval` e `physical_actions_enabled=false` existem na configuração do laboratório, mas **não estão ligados ao adaptador Lua atual**. Os comandos `arena` e `validate-learning` executam somente a arena sintética. O adaptador BG3 existente continua com o antigo decoder de movimento/TTS. `BASIC_ATTACK`, feedback de dano do alvo e economia AP ainda não foram validados no jogo; não habilite combate físico via este laboratório até uma integração específica posterior. O modo `observe` é, portanto, apenas configuração preparada para esse estágio, não uma promessa de execução no BG3.
