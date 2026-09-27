# Ensaio de combate no BG3 — somente observação

O checkpoint treinado em arena C pode agora ser aplicado às **taxas neurais produzidas por uma observação real do BG3**, sem comandar ataque ou substituir o decoder de movimento. A sequência é:

```text
BG3 observation.json → SensoryEncoder → MaleCNS → 14 taxas descendentes
                                               ├→ decoder de movimento → action.json
                                               └→ readout congelado     → combat_observe.json + log Python
```

`CombatShadowProbe.inspect` recebe somente `neural_activity`, `session_id` e `request_id`. Não recebe observação, HP, distância, posição ou alvo. Seu checkpoint é carregado em avaliação determinística; não há atualização de pesos e nenhuma chamada extra ao simulador. O bridge publica `action.json` **antes** de calcular a candidata de combate. Uma falha do probe não bloqueia nem modifica a resposta existente. `combat_observe.json` contém apenas taxas, valores do readout, candidata, IDs, hash do checkpoint e latência; consumidores devem conferir `session_id` e `request_id` para rejeitar estado antigo.

## Preparação

Não é necessário reconstruir o PAK: esta etapa altera somente o bridge Python. Pare um bridge anterior que esteja usando a pasta do Script Extender, pois o lock permite um processo por vez. A configuração [combat-bg3-observe.toml](../config/combat-bg3-observe.toml) mantém o MaleCNS congelado, usa os mesmos ganhos sensoriais experimentais do treino e deixa o novo readout em `observe`. **O `physical_actions_enabled=false` do Python não controla a chave Lua do mod.**

Em PowerShell, na raiz do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
$checkpoint = (Get-ChildItem 'runtime/lab-runs/run_manual_f8725c01/checkpoints' -Filter 'policy_final_*.json' | Select-Object -First 1).FullName
python -m flybg3 --config config/combat-bg3-observe.toml --combat-observe-checkpoint $checkpoint
```

O nome do run acima é o checkpoint C/100 produzido neste experimento local; se o diretório foi movido, substitua pelo caminho de um checkpoint REINFORCE válido com seed 42. Não use `--checkpoint` da arena no lugar de `--combat-observe-checkpoint`. O bridge imprime `Combat readout loaded in OBSERVE ONLY mode`, carrega os 166.700 neurônios e espera observações. O arquivo `combat_observe.json` fica em:

```text
%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3\combat_observe.json
```

No console **server** do BG3 Script Extender, antes de observar:

```text
!flybg3_physical off
!flybg3_combat_move off
!flybg3_auto_end off
!flybg3_status
!flybg3_observe
```

Se Flyman ainda não estiver no save, invoque `!flybg3_spawn` fora de combate e confirme o UUID/party follower antes de `!flybg3_observe`. Em combate, faça uma observação quando for o turno dele. Espere `[FlyBG3] Observation #N sent` e `[FlyBG3] Neural decision #N: ...` no console do jogo. No terminal Python, confirme `[FlyBG3] Combat shadow #N: BASIC_ATTACK (observe only)` ou outra candidata **com o mesmo N**. `BASIC_ATTACK` ainda não é enviado em `action.json`; o jogo não executará ataque por causa desse probe.

Registre pelo menos: sem alvo visível, inimigo distante, inimigo próximo, HP alto/baixo do Flyman, três observações sucessivas do mesmo estado e mudança de alvo. Compare `candidate_action`, `features_hz`, decisão motora, request ID e contexto no log JSONL de `logs/session-*.jsonl`. A fala neural e o motor antigo podem ser deixados desligados durante este teste. Para limpar estados de experimento entre cenários, use o reset manual já documentado no README e registre a troca de sessão.

**Limites:** a observação atual do jogo informa HP do Flyman, distância, ângulo e velocidade relativa do hostil visível mais próximo; não informa o HP do alvo. HP e posição só influenciam o readout por meio do encoder e da dinâmica MaleCNS. A arena C usa regras artificiais e não modela AP, alcance do Mephit, pathfinding nem turnos reais. Uma candidata coerente no log não autoriza executar `BASIC_ATTACK` fisicamente. O próximo gate é comparar decisões log-only em vários encontros reais, validar alvo/alcance/AP e só então integrar um executor de ataque separado com checagens do Script Extender.
