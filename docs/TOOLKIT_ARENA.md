# FlyBG3Arena: campo de testes no BG3 Toolkit

O projeto **FlyBG3Arena** foi criado no BG3 Toolkit 4.1.1.6931813. Ele acrescenta quatro caixas e um `Goblin Brawler` ao nível herdado `Basic_Level_A`, ao redor do ponto inicial. É um cenário separado do mod neural FlyBG3: nenhuma regra do encoder, connectome ou decoder foi alterada.

```text
                marcador C

goblin          START          marcador B

marcador A                     marcador D
```

Os marcadores são itens `CONT_GEN_Crate_Clothing_A` criados pelo Toolkit. O alvo usa o root template `Goblins_Female_Guard` (nome mostrado no editor: `Goblin Brawler`). As posições registradas nos arquivos locais, em coordenadas do nível `(x, y, z)`, são:

| Objeto | Posição |
| --- | --- |
| Goblin Brawler | `(-3.627, 0, -2.580)` |
| Caixa 000 (marcador A) | `(0.955, 0, -3.418)` |
| Caixa 001 (marcador B) | `(8.272, 0, 7.577)` |
| Caixa 002 (marcador C) | `(0.276, 0, 10.583)` |
| Caixa 003 (marcador D) | `(5.280, 0, 0.281)` |

Essas posições vieram dos `.lsf` salvos pelo editor e convertidos para inspeção com LSLib. O esquema acima é apenas visual: ainda não medimos os ângulos dos marcadores em relação ao yaw do Flyman. O `Basic_Level_A` fornece terreno, iluminação, ponto inicial e navegação. A disposição serve para observação e deslocamento em uma área vazia. As caixas **não formam paredes contínuas**.

## Abrir e testar no Toolkit

1. Abra **Baldur's Gate 3 Toolkit**.
2. Selecione o projeto `FlyBG3Arena`.
3. No Level Browser, escolha `Basic_Level_A`.
4. Pressione `Ctrl+Enter` para entrar em Game Mode. O avatar de teste, quatro caixas e o goblin devem aparecer. Pressione `Ctrl+Enter` novamente para voltar ao editor.
5. Salve alterações adicionais com **File → Save all** (`Ctrl+Alt+S`). O Toolkit escreve objetos em `Data\Mods\FlyBG3Arena_00a41563-37f2-988d-98c9-5ca9bb65423a\Levels\Basic_Level_A`.

O teste de Game Mode foi executado nesta máquina: o terreno, as quatro caixas, o goblin e a interface do avatar carregaram. Isso verifica os objetos no editor; **não comprova** que o goblin seja hostil ao Flyman nem que o Script Extender funcione dentro do processo do Toolkit. Para decisões neurais, mantenha o fluxo BG3 + Script Extender + bridge Python já descrito no README.

## Arquivos e instalação no jogo normal

Os arquivos gerados pelo Toolkit foram copiados para `bg3-mod/FlyBG3Arena/Mods/`. O arquivo `toolkit/FlyBG3Arena/Projects/.../meta.lsx` preserva a identidade do projeto para recuperação em outra instalação. O UUID do módulo `00a41563-37f2-988d-98c9-5ca9bb65423a` foi emitido pelo Toolkit; não é um UUID de NPC nem do save. A arena e o FlyBG3 têm módulos distintos para impedir que uma publicação do editor substitua os scripts do mod neural.

No PowerShell, na raiz do repositório:

```powershell
.\scripts\build_arena.ps1 -DivineExe 'C:\Users\Wer\Downloads\Packed\Tools\Divine.exe'
.\scripts\install_mod.ps1 -PackageName FlyBG3Arena
```

O PAK foi compilado e listado com `Divine.exe`; contém um personagem e quatro itens de `Basic_Level_A`. Foi copiado para `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods\FlyBG3Arena.pak`. Ative `FlyBG3Arena` e `FlyBG3` no gerenciador de mods antes de usar ambos no jogo. Se o gerenciador mostrar duas entradas para `FlyBG3Arena` (projeto solto em `Data` e PAK), ative **uma** delas; o PAK versionado é o artefato para o jogo, e os arquivos soltos servem à edição no Toolkit. O usuário confirmou que a arena, os objetos, o Flyman e o combate abriram no jogo normal.

## Teste neural no jogo normal

Inicie o bridge em um terminal PowerShell separado e mantenha esse processo aberto enquanto joga:

```powershell
cd 'C:\Users\Wer\Documents\ChatGPT\FlyBG3'
.\scripts\run_bridge.ps1
```

Aguarde `166700 neurons loaded` e `Waiting for observation...`. No console **server** do Script Extender, use:

```text
Osi.TeleportPartiesToLevelWithMovie("Basic_Level_A", "FlyBG3Arena_Arrive", "")
!flybg3_spawn
!flybg3_status
!flybg3_physical on
!flybg3_combat_move on
!flybg3_observe
```

O prefixo `!` é necessário para os comandos registrados pelo mod; sem ele, o console tenta interpretar `flybg3_combat_move on` como Lua e produz erro de sintaxe. O resultado de `!flybg3_status` deve conter `brain=ready` e `heartbeat_age_ms` abaixo de 5000. Se aparecer `brain=offline`, confira se o terminal do bridge continua em execução e se terminou de carregar o MaleCNS. Depois, envie **uma nova** observação: `!flybg3_observe`. O jogo ignora respostas antigas, portanto observações feitas antes de iniciar o bridge não serão repetidas.

O primeiro teste no jogo mostrou `Observation #N sent` e a seleção de um hostil visível no turno do Flyman. As decisões desse teste deram `Brain bridge offline/stale; IDLE`, pois não havia processo Python ativo e o último `heartbeat_brain.json` tinha parado de atualizar. Em 24/09/2026, após iniciar o bridge e carregar o MaleCNS, o console confirmou `brain=ready, heartbeat_age_ms=191`, `Observation #2 sent` e `Neural decision #2: IDLE`. O log Python confirmou o processamento do mesmo request e uma simulação de aproximadamente 424 ms. Nessa observação havia `in_range=0, visible=0`; o teste comprova o protocolo ao vivo, mas não uma resposta motora a um hostil. O bridge precisa ser iniciado novamente depois de encerrar o processo Python ou reiniciar o Windows.

Para atualizar o repositório depois de editar a arena no Toolkit, copie os novos arquivos de `Data\Mods\FlyBG3Arena_00a41563-37f2-988d-98c9-5ca9bb65423a` para a pasta de mesmo nome em `bg3-mod/FlyBG3Arena/Mods/`, revise o diff e execute novamente `build_arena.ps1`. Não copie arquivos do projeto `FlyBG3` sobre esta pasta.

## Limitação para uma sala fechada

**LIMITAÇÃO:** esta instalação do Toolkit está em `USER MODE`; o Level Browser não oferece `Create` para um nível novo. A [atualização oficial de Patch 8](https://baldursgate3.game/news/the-final-patch-new-subclasses-photo-mode-and-cross-play_138) permite adicionar ou substituir itens, personagens e triggers em níveis existentes, mas não criar prédios, cenário estático nem terreno novo. **CAUSA:** restrições da edição parcial de níveis do Toolkit oficial. **EVIDÊNCIA:** a interface observada só mostrou níveis herdados; a Larian descreve expressamente esses limites. **ALTERNATIVA:** o campo `Basic_Level_A` acima permite testes imediatos. Para uma sala fechada original, será necessária uma versão desbloqueada como [MoonGlasses](https://www.nexusmods.com/baldursgate3/mods/12308) e um fluxo de nível novo; o [guia comunitário de criação de nível](https://wiki.bg3.community/Tutorials/Toolkit/Creating-a-new-level) descreve o template `Basic_Level_A` como ponto de partida. A instalação e compatibilidade do MoonGlasses com este build do Toolkit não foram validadas aqui.

A API oficial [TeleportPartiesToLevelWithMovie](https://docs.baldursgate3.game/index.php?title=TeleportPartiesToLevelWithMovie) aceita nome do nível, evento e filme. A chamada manual acima abriu `Basic_Level_A` no jogo normal. Use um save descartável para repetir o teste; nenhuma viagem automática foi adicionada ao mod.
