# FlyBG3 0.1

NPC de Baldur's Gate 3 controlado por uma simulação neural spiking cuja conectividade deriva do connectome MaleCNS v1.0 de *Drosophila melanogaster*.

O marco atual executa **movimento físico derivado da atividade neural**:

```text
BG3 + Script Extender (Lua, server-side)
       │ observation.json
       ▼
Python FlyBG3 Bridge
       │ encoder abstrato: LC4/LPLC2/LPLC1/LC10a
       ▼
flybrain 0.1.0 — MaleCNS congelado
       │ spikes de descending neurons
       ▼
decoder neural
       │ action.json
       ▼
BG3SE valida turno e caminho
       │ CharacterMoveToPosition
       ▼
Flyman move no mundo do jogo
```

O decoder recebe somente taxas de disparo de DNa02, DNp01, DNg100 e MDN. Ele não recebe posição, distância, direção ou velocidade do mundo. A observação só volta a ser usada depois da decisão, no adaptador físico que converte `TURN_LEFT`, `TURN_RIGHT`, `APPROACH` ou `RETREAT` em um destino curto e navegável.

## Requisitos

* Windows 10/11.
* Python 3.11–3.13. O desenvolvimento foi validado com Python 3.12; o Python 3.14 presente nesta máquina não foi usado porque a pilha científica/Numba deve ser instalada numa versão suportada.
* Baldur's Gate 3 e [BG3 Script Extender](https://github.com/Norbyte/bg3se), API v30 ou superior.
* Para empacotar o mod: [LSLib/Divine.exe](https://github.com/Norbyte/lslib).

## Instalação Python e connectome

No PowerShell, a partir da raiz do repositório:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m flybrain download
python tools\inspect_brain.py --verify-hashes --output docs\brain-inspection.json
```

O download oficial grava aproximadamente 258 MB em `%USERPROFILE%\fly-data` por padrão. Defina `FLY_DATA` antes do download para outro local. A inspeção deve informar 166.700 neurônios, 25.582.938 conexões agregadas e 1.314 descending neurons.

GPU é opcional e somente para NVIDIA/CUDA 12 conforme o extra oficial:

```powershell
python -m pip install -e ".[test,gpu]"
```

`device = "auto"` só escolhe CUDA quando CuPy realmente detecta um dispositivo; caso contrário usa CPU/Numba.

## Experimentos reproduzíveis

```powershell
python tools\fake_bg3.py --experiment
```

O comando executa 90 janelas neurais reais: 14 cenários, cinco seeds fixas (`42..46`) e fases temporais adicionais. Ele recria:

* [results.json](experiments/results.json), com estímulos, spikes, taxas, decisão, latência e estado residual por execução;
* [EXPERIMENTS.md](docs/EXPERIMENTS.md), com a matriz agregada e interpretação cautelosa.

Para um cenário interativo simples com o connectome real:

```powershell
python tools\fake_bg3.py --scenario left
```

## Bridge de arquivos sem BG3

Terminal 1:

```powershell
python -m flybg3 --directory runtime\fake --once
```

Terminal 2:

```powershell
python tools\fake_bg3.py --bridge-dir runtime\fake --scenario left
```

Isso comprova `observation.json → FlyBrain → action.json`, incluindo session UUID, request ID monotônico, journal persistente contra duplicatas, heartbeat lease e replace atômico no lado Python.

## Empacotar e instalar o mod

Instale primeiro o Script Extender pelo procedimento oficial. Depois:

```powershell
.\scripts\build_mod.ps1 -DivineExe "C:\caminho\LSLib\Packed\Tools\Divine.exe"
.\scripts\install_mod.ps1
```

O instalador copia somente `build\FlyBG3.pak` para `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods`. Ele não sobrescreve um pacote existente sem `-Force` e não edita `modsettings.lsx`. Ative FlyBG3 no BG3 Mod Manager ou no gerenciador de mods do jogo.

## Executar no BG3

1. Inicie o bridge antes de carregar o save:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m flybg3 --config config\default.toml
   ```

   Para iniciar pelo launcher PowerShell com logs detalhados, use `.\scripts\run_bridge.ps1 -VerboseLogging` (o nome evita conflito com o parâmetro comum `-Debug` do PowerShell).

2. Abra BG3, carregue um save e use o console server-side do Script Extender.
3. Fora de combate, crie o corpo próprio do Flyman: `!flybg3_spawn`. O mod usa um novo template herdado de `MEPHIT_Mud_A`, com visual de Mud Mephit, e o atribui ao host como personagem controlável para evitar decisões concorrentes da IA padrão. O seu avatar não é alterado.
4. O console deve mostrar `Flyman Mud Mephit spawned and bound: <UUID real do save>`. Anote esse UUID se tiver definido `FLYBG3_NPC_UUID` ou `[bridge].npc_uuid`: atualize o filtro ou deixe-o vazio.
5. Fora de combate, dispare uma observação manual com `!flybg3_observe`. Em combate, `TurnStarted` dispara automaticamente para o corpo do Flyman.

Saída esperada no console:

```text
[FlyBG3] Observation #1 sent
[FlyBG3] Neural decision #1: TURN_LEFT
[FlyBG3] Physical action #1: TURN_LEFT (issued)
```

Arquivos de comunicação no Windows:

```text
%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3\
  observation.json
  action.json
  heartbeat_bg3.json
  heartbeat_brain.json
  requests.sqlite3
```

O UUID da instância criada fica em `settings.json` nesse diretório. O mod só aceita esse UUID se `GetTemplate` confirmar o template próprio do Flyman. Um vínculo antigo ao seu avatar é descartado ao carregar a sessão. `!flybg3_spawn` reutiliza o Flyman já presente no nível; `!flybg3_bind UUID` serve apenas para recuperar manualmente uma instância que tenha esse template. `FLYBG3_NPC_UUID` ou `[bridge].npc_uuid` pode restringir o bridge ao mesmo corpo, mas o valor anterior do seu personagem deve ser removido. Nenhum UUID de instância é inventado no código.

### Recurso Mud Mephit e BG3 Toolkit

O template de Flyman herda o `MEPHIT_Mud_A` extraído do `Shared.pak` instalado; usa seus recursos visuais, animações e stats, e recebe nome localizado próprio. `scripts/build_mod.ps1` compila o root template para `_merged.lsf` e a tradução para `.loca` usando LSLib antes de empacotar. O BG3 Toolkit está instalado nesta máquina, mas a interface exige o DLC separado **BG3 Toolkit Data**. A pasta `Data\Editor` contém apenas `Config`, não os dados do DLC; por isso o recurso foi preparado e compilado por LSLib, sem alegar validação no editor. Para abri-lo no Toolkit, habilite BG3 Toolkit Data nas propriedades de Baldur's Gate 3 → DLC no Steam e aguarde o download. A [instalação oficial do Toolkit](https://docs.baldursgate3.game/Getting_Started%3A_Installing_the_Toolkit) explica essa dependência.

O código e o pacote foram testados localmente, mas a criação do Mud Mephit e `MakePlayer` ainda precisam de validação no seu save. Faça um save separado antes de `!flybg3_spawn`, pois a criatura é persistente e ganha retrato na party. Consulte [a nota de implementação](docs/MUD_MEPHIT.md) para os comandos e limites do teste.

## Primeiro movimento físico

O pacote atual pode emitir um movimento lateral pequeno ou um passo de aproximação/fuga. O executor só aceita uma resposta com o mesmo `session_id` e `request_id`, revalida que o personagem ainda pode agir e exige um hostil visível ou dano recente. `TURN_LEFT` e `TURN_RIGHT` significam um `lateral_step` de 2 m; não são uma rotação arbitrária, porque o Script Extender não expõe uma chamada Lua documentada para definir yaw.

O caminho físico valida primeiro o destino com `Ext.Level.BeginPathfindingImmediate`/`FindPath`/`ReleasePath` e só então usa `Osi.CharacterMoveToPosition`, APIs confirmadas na documentação e em um mod server-side real. Essa chamada pode ignorar AP/turno em combate e pode cair para teleporte quando o destino está bloqueado, por isso `AllowCombatMovement = false` permanece como padrão. O movimento foi comprovado em BG3SE v32 tanto para `TURN_RIGHT` quanto para `TURN_LEFT`; o teste em combate usou a opção experimental abaixo. A limitação e as fontes estão em [RESEARCH.md](docs/RESEARCH.md#movimento-e-combate-diferença-importante).

Comandos de controle no console server-side:

```text
!flybg3_physical on
!flybg3_physical off
!flybg3_combat_move on   # experimental; bypassa AP/turno
!flybg3_combat_move off
!flybg3_auto_end on      # encerra após IDLE ou depois do evento de chegada
!flybg3_auto_end off
```

Se uma decisão neural for produzida sem alvo/dano atual, o console registra `Physical action skipped` e o personagem permanece parado. Isso preserva a atividade espontânea do connectome para o experimento sem transformar tonicidade em movimento inesperado.

O encerramento automático fica desativado por padrão. Quando habilitado, uma decisão neural `IDLE` encerra o turno imediatamente. Para movimento, `CharacterMoveToPosition` recebe um evento único vinculado ao `request_id`, e somente o `EntityEvent` de chegada correspondente pode chamar `EndTurn`. Cancelamento e timeout são registrados e não encerram o turno à força.

## Testes

```powershell
python -m pytest -q
python -m pytest -q -m brain
```

O primeiro conjunto não exige download do cérebro. O segundo carrega o MaleCNS real, verifica causalidade, continuidade de estado e a ablação de propagação sináptica. Os arquivos Lua são parseados com Lua 5.4; os testes também verificam os gates do executor, o `vec3` posicional do pathfinder e o proxy chamável das funções Osiris.

## Evidência e limitações

As APIs, commits consultados, grupos neuronais e pesquisas funcionais estão em [RESEARCH.md](docs/RESEARCH.md). Os números do conectoma e hashes estão em [brain-inspection.json](docs/brain-inspection.json).

O conectoma fornece conectividade derivada de microscopia eletrônica. O modelo LIF usa neurônios pontuais e parâmetros calibrados pelo projeto `fly.ai`; não modela dendritos detalhados, neurônios graduados, neuromodulação, plasticidade ou toda a fisiologia da mosca. Os estímulos visuais são detectores abstratos. Este projeto não demonstra consciência e não deve ser descrito como uma mosca literal jogando BG3.

O pipeline e o movimento físico foram validados num save real. Ataque básico e encerramento automático de turno ainda não fazem parte deste milestone. `UseSpell` não será tratado como ataque normal porque a API Osiris documentada ignora pré-condições de acesso e recursos; qualquer integração de combate completa deve preservar essa limitação ou usar um mecanismo de ação do jogo que respeite a economia do turno.
