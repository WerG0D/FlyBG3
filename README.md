# FlyBG3 0.1

NPC de Baldur's Gate 3 controlado por uma simulação neural spiking cuja conectividade deriva do connectome MaleCNS v1.0 de *Drosophila melanogaster*.

O marco atual é deliberadamente **log-only**:

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
console BG3: Neural decision #N: TURN_LEFT
```

Não há caminho ativo de movimento. `ActionExecutor.lua` é um protótipo futuro e não é carregado pelo bootstrap. O decoder recebe somente taxas de disparo de DNa02, DNp01, DNg100 e MDN. Ele não recebe posição, distância, direção ou velocidade do mundo.

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

## Prova log-only no BG3

1. Inicie o bridge antes de carregar o save:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m flybg3 --config config\default.toml
   ```

   Para iniciar pelo launcher PowerShell com logs detalhados, use `.\scripts\run_bridge.ps1 -VerboseLogging` (o nome evita conflito com o parâmetro comum `-Debug` do PowerShell).

2. Abra BG3, carregue um save e use o console server-side do Script Extender.
3. Para o primeiro teste, obtenha o avatar do host com `_P(Osi.GetHostCharacter())` e copie o GUID real retornado.
4. Vincule o personagem: `!flybg3_bind SEU-UUID-REAL`.
5. Fora de combate, dispare uma observação manual com `!flybg3_observe`. Em combate, `TurnStarted` dispara automaticamente para o UUID vinculado.

Saída esperada no console:

```text
[FlyBG3] Observation #1 sent
[FlyBG3] Neural decision #1: TURN_LEFT
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

O UUID persistido pelo comando do console fica em `settings.json` nesse diretório. `FLYBG3_NPC_UUID` ou `[bridge].npc_uuid` pode restringir o bridge ao mesmo personagem. Nenhum UUID de NPC fictício vem configurado.

## Primeiro movimento físico

Depois de confirmar os dois logs acima, o pacote atual pode emitir um movimento lateral pequeno ou um passo de aproximação/fuga. O executor só aceita uma resposta com o mesmo `session_id` e `request_id`, revalida que o personagem ainda pode agir e exige um hostil visível ou dano recente. `TURN_LEFT` e `TURN_RIGHT` significam um `lateral_step` de 2 m; não são uma rotação arbitrária, porque o Script Extender não expõe uma chamada Lua documentada para definir yaw.

O caminho físico valida primeiro o destino com `Ext.Level.BeginPathfindingImmediate`/`FindPath`/`ReleasePath` e só então usa `Osi.CharacterMoveToPosition`, APIs confirmadas na documentação e em um mod server-side real. Essa chamada pode ignorar AP/turno em combate e pode cair para teleporte quando o destino está bloqueado, por isso `AllowCombatMovement = false` permanece como padrão. O primeiro milestone físico é deliberadamente fora de combate; movimento turn-based exige um estado Anubis próprio e será tratado depois. A limitação e as fontes estão em [RESEARCH.md](docs/RESEARCH.md#movimento-e-combate-diferença-importante).

Comandos de controle no console server-side:

```text
!flybg3_physical on
!flybg3_physical off
!flybg3_combat_move on   # experimental; bypassa AP/turno
!flybg3_combat_move off
```

Se uma decisão neural for produzida sem alvo/dano atual, o console registra `Physical action skipped` e o personagem permanece parado. Isso preserva a atividade espontânea do connectome para o experimento sem transformar tonicidade em movimento inesperado.

## Testes

```powershell
python -m pytest -q
python -m pytest -q -m brain
```

O primeiro conjunto não exige download do cérebro. O segundo carrega o MaleCNS real, verifica causalidade, continuidade de estado e a ablação de propagação sináptica. Os arquivos Lua são parseados com Lua 5.4 e há um teste que falha se o caminho ativo log-only voltar a carregar chamadas de movimento.

## Evidência e limitações

As APIs, commits consultados, grupos neuronais e pesquisas funcionais estão em [RESEARCH.md](docs/RESEARCH.md). Os números do conectoma e hashes estão em [brain-inspection.json](docs/brain-inspection.json).

O conectoma fornece conectividade derivada de microscopia eletrônica. O modelo LIF usa neurônios pontuais e parâmetros calibrados pelo projeto `fly.ai`; não modela dendritos detalhados, neurônios graduados, neuromodulação, plasticidade ou toda a fisiologia da mosca. Os estímulos visuais são detectores abstratos. Este projeto não demonstra consciência e não deve ser descrito como uma mosca literal jogando BG3.

O teste vivo ainda requer o jogo, um save e um UUID real. Movimento físico continuará desativado até a comprovação dos dois logs acima.
