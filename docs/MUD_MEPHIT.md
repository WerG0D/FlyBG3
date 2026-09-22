# Flyman em um Mud Mephit próprio

O corpo novo é um root template do mod (`FlyBG3_MudMephit_Flyman`) que herda o `MEPHIT_Mud_A` do `Shared.pak`. O `MapKey` do template é `f8881547-6e53-44d4-943b-15cddef25f22`; ele identifica um recurso do mod, **não** a instância de Flyman no save. A instância recebe um UUID real quando `CreateAtObject` a cria.

O decoder neural, o encoder e o MaleCNS não mudaram. Somente o adaptador server-side mudou de corpo. `!flybg3_spawn` cria Flyman na posição do avatar host e solicita `AddPartyFollower(Flyman, host)`. O host é apenas âncora/líder e não recebe comandos de movimento. A documentação da Larian define um party follower como criatura com controle limitado semelhante a uma invocação, apta a acompanhar e lutar com a party. O save real confirmou `follower=1` e um turno próprio para este template. O adaptador se recusa a observar ou agir se `IsPartyFollower` e `IsPlayer` retornarem ambos zero.

## Reproduzir

1. Feche BG3. Construa e instale o pacote:

   ```powershell
   .\scripts\build_mod.ps1 -DivineExe 'C:\Users\Wer\Downloads\Packed\Tools\Divine.exe'
   .\scripts\install_mod.ps1 -Force
   ```

2. Inicie o bridge em outro terminal:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m flybg3 --config config\default.toml
   ```

3. Abra BG3, carregue um save **separado**, abra o console server-side do Script Extender e, fora de combate, execute:

   ```text
   !flybg3_spawn
   !flybg3_observe
   ```

4. Confirme no console `Flyman joined party; follower=1` ou `Flyman already exists; party control requested`, seguido de `Observation #N sent` / `Neural decision #N: ...`. Se a criatura já foi criada pela versão anterior, execute `!flybg3_spawn` novamente: o comando tenta anexar a instância existente sem criá-la de novo. Para testar movimento, use `!flybg3_physical on`; em combate, `!flybg3_combat_move on` e `!flybg3_auto_end on` continuam opções experimentais com as limitações descritas no README.

5. Antes de observar, execute `!flybg3_status`. `brain=ready` significa que o processo Python está vivo, carregou o MaleCNS e escreveu um heartbeat recente. `brain=offline` exige iniciar o bridge; manter apenas BG3 aberto produz `Observation #N sent` seguido de timeout. O mod nunca executa uma decisão antiga de `action.json`.

Se a decisão chegar mas o Flyman continuar parado, confira `Sensory scan #N` no console. `hostile=0` sugere que `IsEnemy(Flyman, alvo)` não reconheceu hostilidade; `in_range=0` sugere alvos além de `MaxDistance`; `visible=0` sugere ausência de linha de visão. O mod não inventa um alvo nem força movimento sem evidência sensorial atual.

Se `!flybg3_spawn` retornar `CreateAtObject_failed`, verifique se o pacote atualizado está habilitado no gerenciador de mods e se o `Public/FlyBG3/RootTemplates/_merged.lsf` está presente no PAK. Se retornar `spawned_template_mismatch`, anote o UUID impresso no erro e não use `!flybg3_bind` até inspecionar `Osi.GetTemplate(UUID)`; o mod se recusa a substituir a checagem de identidade por um UUID manual. Se `AddPartyFollower` falhar, o erro inclui o UUID da criatura criada para diagnóstico. Se aparecer `Flyman still has no party control`, o adaptador continua bloqueado. O código não apaga nem transforma automaticamente a criatura ao falhar.

O `settings.json` antigo, que apontava para o avatar, é descartado na primeira sessão com o novo mod. Se o bridge antigo estava configurado com `FLYBG3_NPC_UUID` ou `npc_uuid` do avatar, limpe esse filtro ou substitua pelo UUID impresso para Flyman. Repetir `!flybg3_spawn` no mesmo nível tenta recuperar a criatura existente antes de criar outra.

Para evitar mortes durante ensaios, `ImmortalForTesting=true` aplica `Osi.SetImmortal(Flyman, 1)` ao carregar o save. O guardião `FlyBG3Body.isFlyman` impede que o comando altere o avatar ou outro NPC. `!flybg3_immortal off` chama `SetImmortal(Flyman, 0)` e `!flybg3_immortal on` reativa; a verificação usa `IsImmortal`. A imortalidade não ressuscita uma criatura que já morreu antes da aplicação.

## Estado do Toolkit

O executável da BG3 Toolkit está presente, mas, ao escolher a pasta real do jogo, ele informou ausência dos dados `Data/Editor`. No disco, `Data/Editor` contém apenas `Config`, criada pela configuração da ferramenta; os dados de projeto do DLC **BG3 Toolkit Data** não estão instalados nesta máquina. A documentação oficial requer esse DLC para abrir projetos no editor. Enquanto ele não estiver disponível, o template é fonte LSX editável no repositório e é compilado para LSF por LSLib. O template binário, a localização e a estrutura do PAK passaram na validação local; a criação, o vínculo como party follower e o turno do Mud Mephit foram confirmados pelo usuário. A decisão neural e o movimento nesse corpo ainda exigem teste no BG3. Não afirmamos que o editor já abriu ou validou o projeto.

Depois de instalar o DLC, o próximo passo de edição visual é abrir/criar o projeto FlyBG3 no Toolkit, localizar o root `FlyBG3_MudMephit_Flyman`, conferir a herança de `MEPHIT_Mud_A` e testar a criatura em Game Mode. Essa etapa não deve alterar o circuito neural.
