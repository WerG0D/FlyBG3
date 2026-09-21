# Pesquisa de APIs — 2026-09-21

## Evidência e versões

Repositório inicialmente vazio. Fontes consultadas antes de implementar:

* [fly.ai](https://github.com/alextitonis/fly.ai), commit `5e931b8dc4856550565c5fa129d3d0c055af3dd1`.
* PyPI `flybrain==0.1.0`, instalado em `.venv` com Python 3.12. O conteúdo de `flybrain/brain.py` é idêntico ao commit acima após normalizar quebras de linha. Inspeção local, não API inferida do README.
* [BG3SE API](https://github.com/Norbyte/bg3se/blob/b2b7513264ce4d0e79a8e4a5ef9180506b7ab2f8/Docs/API.md), cabeçalho v30; commit `b2b7513264ce4d0e79a8e4a5ef9180506b7ab2f8`.
* [Move With Minimap](https://github.com/tldev/bg3-move-with-minimap-mod), commit `a660d231905be290ef7d0e207d53ea36f21c3a2d`, exemplo real server-side Lua/Osiris.
* [Documentação de scripting Larian](https://docs.baldursgate3.game/).

## flybrain

`FlyBrain(data=None, seed=64, device=None, batch=1, dt=None, sensory_input=True, refractory=0.0)`.
`cells(types: list[str], side=None)` retorna índices NumPy por cell_type ou superclass.
`step(eye_drive=None, inject=())` recebe pares `(índices, incremento de voltagem)`; com batch=1 retorna índices NumPy dos disparos. `reset(seed)` zera voltagem, disparos e RNG. A instância mantém estado entre steps.

`n`, `weights`, `cell_type`, `side`, `superclass`, `groups`, `dt`, `steps` estão presentes no código instalado. O adaptador não treina nem altera pesos.

Valores upstream: dt=0.020 s, tau=0.100 s, gain=3, tonic=0.14, noise_hz=1.2, noise_amp=0.22. Modelo de neurônio pontual LIF: decaimento, soma sináptica, tônico, ruído, injeção; limiar 1 e reset 0. Tônico reescalado com dt. `device=auto` seleciona CUDA apenas quando CuPy detecta dispositivo; CPU usa Numba. Extra oficial `flybrain[gpu]` instala CuPy CUDA 12. Seeds não tornam CPU e GPU idênticos.

Download oficial: `python -m flybrain download`, cache `FLY_DATA` ou `~/fly-data`. Release brain-v1, dois arquivos NPZ, cerca de 258 MB. SHA256 upstream:

* brain.npz: `cc9bd1ecd00bd703a6fa648bc6ad145c93c7c1ee53debdcc9ce0d1f4305e6aca`
* weights.npz: `c29919aa44069a271b1ee978abe05fa9bf6e45e4ba3e436e92b624ef1b5be40c`

Upstream declara 166700 neurônios, 25582938 arestas, 1314 descendentes. Arestas não são sinapses individuais: cada peso representa uma contagem de sinapses, sinalizada pelo neurotransmissor e normalizada por entrada.

`eyes.py` injeta LC4, LPLC2, LPLC1, LC10a como detectores abstratos; evita o gargalo de neurônios graduados da lâmina. Os exemplos upstream associam DNa02 a steering, DNp01 a escape, DNg100 a andar para frente e MDN a andar para trás. Isso não valida automaticamente suas equivalências com ações humanas. Os grupos devem ser confirmados no NPZ e vazios devem causar erro explícito.

## BG3SE

`Ext.IO.LoadFile(path, [context]) -> string?`, `Ext.IO.SaveFile(path, content) -> boolean`, `Ext.Json.Parse(text)`, `Ext.Json.Stringify(value, [options])` confirmados. `Lua/Libs/IO.inl` e `Extender/Shared/ScriptHelpers.cpp` mostram raiz UserProfile + `/Script Extender/`. Windows padrão: `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Script Extender\FlyBG3`. `SaveFile` cria diretórios mas NÃO oferece rename atômico. Python deve tolerar leituras parciais; respostas Python usam replace atômico no mesmo diretório.

`Ext.Osiris.RegisterListener(name, arity, "after", handler)` confirmado. `TurnStarted` e `TurnEnded` têm 1 argumento. `Ext.Timer.WaitForRealtime(ms, callback)` e `MonotonicTime()` (ms) permitem polling leve não bloqueante. BootstrapServer.lua + Config.json com FeatureFlags=["Lua"] e ModTable são o caminho oficial.

## Movimento e combate: diferença importante

[CharacterMoveToPosition](https://docs.baldursgate3.game/index.php?title=CharacterMoveToPosition): `(character,x,y,z,"Walk"|"Run",event[,moveID])`. Existe, mas ignora AP/turno em combate e pode teleportar quando bloqueado. O exemplo Minimap usa 7 argumentos, testa navegação com `Ext.Level.BeginPathfindingImmediate`, `FindPath`, `ReleasePath` e bloqueia combate. Logo NÃO será apresentado como movimento normal balanceado de combate.

[EndTurn](https://docs.baldursgate3.game/index.php?title=EndTurn): `(target)`.
[TurnStarted](https://docs.baldursgate3.game/index.php?title=TurnStarted): `(object)`.
[CanSee](https://docs.baldursgate3.game/index.php?title=CanSee): `(source,target)->bool integer`, considera sneaking; tem efeito de registrar eventos de visão para certos pares de NPCs.

Limites de validação: assinaturas confirmadas em código/documentação não equivalem a testes num save. Abrir BG3, selecionar personagem e testar movimento são validação manual obrigatória. A pesquisa será complementada com contagens e resultados executados.

## Descending neurons candidatos

### Evidência no dataset instalado

O MaleCNS v1.0 é o conectoma completo de um único macho adulto, com 166.700 neurônios anotados. A página oficial oferece exploração por cell type, consultas neuPrint e os arquivos Feather usados pelo `flybrain`. Fonte: [MaleCNS](https://male-cns.janelia.org/), [downloads v1.0](https://male-cns.janelia.org/download/) e [Berg et al., Cell 2026](https://doi.org/10.1016/j.cell.2026.08.015).

`flybrain/build.py` escolhe `flywireType`, com fallback para `type`, e seleciona `superclass == descending_neuron`. A inspeção de `brain.npz` confirmou que todos os grupos abaixo estão dentro dos 1.314 descending neurons. Contagens são L/R:

| tipo | L/R | hipótese funcional | uso em FlyBG3 0.1 |
|---|---:|---|---|
| DNa02 | 1/1 | steering de alto ganho | decoder esquerda/direita |
| DNp01 | 1/1 | giant fiber, escape/take-off | decoder retreat |
| DNg100 | 1/1 | forward no `fly.ai`/Fly64; alias BDN2 indicado no código upstream | decoder approach |
| MDN | 2/2 | backward walking | decoder retreat |
| DNa01 | 1/1 | steering de baixo ganho | somente sonda experimental |
| DNb02 | 2/2 | turning/steering | somente sonda experimental |
| DNg13 | 1/1 | steering, com alvo motor distinto de DNa02 | somente sonda experimental |
| DNp09 | 1/1 | forward/pursuit; freezing depende do contexto | somente sonda experimental |
| DNp26 | 1/1 | aumento global de locomoção em tela optogenética | somente sonda experimental |
| DNp02, DNp10, DNp11 | 1/1 cada | jump/escape | somente sondas experimentais |
| DNg103 | 1/1 | sem função assumida neste projeto | somente sonda de comparação, sem rótulo motor |

`oDN1` é descrito como forward/bolt walking na literatura e aparece no conjunto conceitual do `fly.ai`, mas o próprio `fly.ai/wiz/dnscreen.py` registra “oDN1 is not in the data”. A consulta exata a `brain.cells(["oDN1"])` retorna zero; portanto ele não foi usado. `DNg12` existe no MaleCNS como `DNg12_a`…`DNg12_e`, e não como o nome agregado `DNg12`; também ficou fora desta primeira bateria.

### Evidência funcional e cautelas

* [Yang et al., eLife 2025](https://elifesciences.org/articles/102230) mediram DNa01 e DNa02 em moscas andando: DNa02 prediz steering de alto ganho e DNa01, baixo ganho. Isso sustenta a lateralidade, não uma equivalência direta com “virar um humanoide”.
* [Rayshubskiy et al., Current Biology 2023](https://pubmed.ncbi.nlm.nih.gov/37904997/) distinguem as saídas de DNa02 e DNg13 nos circuitos motores das pernas; ambos são relacionados a steering.
* [Braun et al., Nature 2024](https://www.nature.com/articles/s41586-024-07523-9) mostram redes de DNs: DNp09 dirige forward walking e conecta-se a DNa02/DNb02; DNa01, DNa02 e DNb02 caem em comunidades de walking/steering. Isso recomenda leitura populacional, não tratar todo DN como botão isolado.
* [Bidaye et al./Chen et al., Nature Communications 2020](https://www.nature.com/articles/s41467-020-19936-x) resumem e testam MDN como comando de backward walking e seus alvos no VNC.
* [Simpson, Current Opinion in Neurobiology 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11215313/) revisa DNp01 como giant fiber de escape, DNp02/DNp10/DNp11 como jump/escape, DNp09 como freezing ou forward/pursuit, oDN1 como bolt forward e DNa02/DNg13 como steering.
* [Zacarias et al., Nature Communications 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC6135764/) encontraram necessidade/suficiência de DNp09 para freezing em um paradigma de looming, mas a ativação inicialmente acelera a marcha e depois produz imobilidade. [Ache et al., Current Biology 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8716191/) não encontraram efeito de silenciar DNp09 no freezing mediado por LC11. Assim, DNp09 não é adotado como “STOP” inequívoco.
* [Cande et al., eLife 2018](https://elifesciences.org/articles/34275) é uma tela optogenética ampla: DNa01, DNa02 e DNp26 são alguns dos tipos com aumento global de locomoção. Fenótipo por ativação não prova que spikes naturais tenham uma única semântica.

As sondas adicionais são apenas medidas em `experiments/results.json`. O decoder de produção permanece exatamente com DNa02, DNp01, DNg100 e MDN; posição, distância, direção e velocidade nunca entram nele.

## Estado da integração local BG3

Verificação local em 2026-09-21 confirmou a instalação completa. O manifesto Steam (`appmanifest_1086940.acf`) informa `StateFlags=4`, `SizeOnDisk=159057747491`, `BytesDownloaded=BytesToDownload` e build `24532579`. Os executáveis `bin/bg3.exe` e `bin/bg3_dx11.exe` estão presentes (ProductVersion `4.1.1.7398727`). O loader do Script Extender está em `bin/DWrite.dll` (Norbyte, versão de arquivo `5.0.0.0`, SHA-256 `8F3C0782461CC280CAB4ADFC270979549211F6CAC91AD851BAA2B2716118ECB0`).

O pacote de teste foi criado pelo Divine do LSLib em `C:\Users\Wer\Downloads\Packed\Tools\Divine.exe` e instalado como `%LOCALAPPDATA%\Larian Studios\Baldur's Gate 3\Mods\FlyBG3.pak`. A listagem do pacote contém `meta.lsx`, `ScriptExtender/Config.json` e os cinco arquivos Lua do milestone log-only. Um processo `bg3_dx11.exe` foi iniciado para a verificação e carregou `BG3ScriptExtender.dll` versão `32.0.0.0`; ainda não houve carregamento de save nem observação pelo console, e `LastPlayed=0` continua no manifesto porque a execução foi iniciada diretamente pelo executável. A validação em jogo requer habilitar o mod no gerenciador, carregar um save e observar o console.

O milestone atual avançou para um executor físico guardado. `BootstrapServer.lua` carrega `ActionExecutor.lua`, que pode chamar `Osi.CharacterMoveToPosition` somente depois de uma resposta neural correspondente, com estímulo atual e revalidação do estado do personagem. `AllowCombatMovement=false` por padrão porque a chamada oficial ignora AP/turno em combate e pode teleportar quando o destino está bloqueado. Não são chamados `EndTurn`, `PurgeOsirisQueue` ou APIs de transformação. A bridge Python continua separada e não bloqueia a thread do BG3.

### Validação viva

O fluxo log-only foi comprovado em um save real com o UUID fornecido pelo usuário. O BG3 escreveu `Observation #1`, o Python executou o MaleCNS e o jogo registrou `Neural decision #1: IDLE`. Essa resposta foi coerente: a observação ocorreu fora de combate, sem `nearest_hostile` e sem dano; todos os estímulos do encoder foram zero e os scores motores ficaram abaixo do limiar.

Na mesma sessão, o jogo produziu dezesseis observações reais. A request 16 ocorreu durante o turno de Flyman, com um hostil visível a 2,72 m e ângulo relativo de +118,47°. O connectome gerou DNa02_L=1 Hz e DNa02_R=3 Hz; o decoder escolheu `TURN_RIGHT` com confiança 0,806 e a resposta manteve os mesmos `session_id`, `request_id` e UUID. Latência total: 379,5 ms. Isso comprova BG3 → observação → encoder → MaleCNS → descending neurons → decoder → `action.json` → BG3 log. A validação de movimento físico ainda exige uma nova sessão carregando o pacote atualizado.

### Primeira tentativa de movimento em combate

O teste seguinte comprovou seis decisões neurais consecutivas durante o turno de Flyman (`TURN_RIGHT`, depois `TURN_LEFT`), mas todas foram recusadas antes do comando físico com `pathfinding_request_failed`. A falha foi isolada na conversão Lua → `glm::vec3`: o projeto passava `{x=..., y=..., z=...}`, enquanto a ligação oficial declara `BeginPathfindingImmediate(lua_State*, EntityHandle, glm::vec3)` e o exemplo real Move With Minimap passa uma tabela posicional `{x, y, z}`. O executor agora converte explicitamente o ponto interno para `{point.x, point.y, point.z}` na fronteira BG3SE e inclui o erro original de `pcall` no log. Nenhuma parte do encoder, MaleCNS ou decoder foi alterada.

O teste após essa correção avançou pelo pathfinder e parou em `CharacterMoveToPosition_unavailable`. A chamada existe; a detecção estava errada. `BG3Extender/Lua/Osiris/FunctionProxy.h` define nomes `Osi.*` como `LightCppValue` com a interface `Callable`, e `FunctionProxy.inl` encaminha `__call` para `LuaCall`. Portanto `type(Osi.CharacterMoveToPosition) == "function"` não é uma verificação válida. O executor passou a chamar o proxy diretamente dentro de `pcall`; se o nome ou a aridade não existirem, o próprio BG3SE fornece um erro preciso. O teste Lua representa `CharacterMoveToPosition` como tabela com `__call` para cobrir esse comportamento.

O pacote seguinte foi validado pelo usuário em BG3SE v32 (build de 21 de junho de 2026). As requests 1–3 produziram `IDLE` e não moveram o personagem. A request 4 produziu `TURN_RIGHT` e o console registrou `Physical action #4: TURN_RIGHT (issued)`; a request 5 produziu `TURN_LEFT` e registrou a ação correspondente. O personagem moveu-se fisicamente nas duas direções corretas. Isso fecha o milestone completo BG3 → observação → MaleCNS → descending neurons → decoder → resposta correlacionada → pathfinder → movimento real.

### Próxima fronteira de combate

`EndTurn(character)` é uma chamada Osiris documentada e pode encerrar o turno depois de uma ação neural concluída. `CharacterMoveToPosition` pode emitir um `EntityEvent` ao chegar, o que oferece uma sincronização orientada a eventos. Já `UseSpell(caster, spell, target, ...)`, embora documentada, ignora pré-condições como acesso à habilidade e recursos. Ela não deve ser apresentada como um ataque básico normal nem habilitada silenciosamente. O decoder atual também não possui um canal neural biologicamente sustentado para `ATTACK`; transformar proximidade em ataque no executor violaria a regra de que o estado do jogo não escolhe a ação. Ataque permanece pendente até existir um readout neural explícito e uma execução cuja semântica de economia de turno esteja documentada.

O primeiro adaptador de ciclo de turno usa exatamente essa rota documentada. Cada movimento recebe `FlyBG3_Move_<request_id>` e um `moveID` correspondente. `EntityEvent(object,event)` marca chegada e, somente com `!flybg3_auto_end on`, chama `EndTurn` se o mesmo personagem ainda estiver no próprio turno. Uma decisão neural `IDLE` pode encerrar o turno sem aguardar evento físico. `CharacterMoveToCancelled(character,moveID)` e timeout apenas limpam o estado pendente e registram a falha. A opção é desligada por padrão até validação no save.
