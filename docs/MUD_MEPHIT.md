# Flyman em um Mud Mephit próprio

O corpo novo é um root template do mod (`FlyBG3_MudMephit_Flyman`) que herda o `MEPHIT_Mud_A` do `Shared.pak`. O `MapKey` do template é `f8881547-6e53-44d4-943b-15cddef25f22`; ele identifica um recurso do mod, **não** a instância de Flyman no save. A instância recebe um UUID real quando `CreateAtObject` a cria.

O decoder neural, o encoder e o MaleCNS não mudaram. Somente o adaptador server-side mudou de corpo. `!flybg3_spawn` cria Flyman na posição do avatar host e chama `MakePlayer(Flyman, host, 0)`. Isso dá ao Flyman um turno e evita a IA NPC padrão competir com a decisão neural; o avatar host é apenas âncora/owner e não recebe comandos de movimento. Tecnicamente ele aparecerá como membro controlável da party, embora tenha corpo/modelo de NPC Mud Mephit. Um NPC inteiramente autônomo sem retrato precisaria de uma estratégia de AI/Osiris adicional, ainda não validada.

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

4. Confirme no console `Flyman Mud Mephit spawned and bound: <UUID>` e depois `Observation #N sent` / `Neural decision #N: ...`. Para testar movimento, use `!flybg3_physical on`; em combate, `!flybg3_combat_move on` e `!flybg3_auto_end on` continuam opções experimentais com as limitações descritas no README.

Se `!flybg3_spawn` retornar `CreateAtObject_failed`, verifique se o pacote atualizado está habilitado no gerenciador de mods e se o `Public/FlyBG3/RootTemplates/_merged.lsf` está presente no PAK. Se retornar `spawned_template_mismatch`, anote o UUID impresso no erro e não use `!flybg3_bind` até inspecionar `Osi.GetTemplate(UUID)`; o mod se recusa a substituir a checagem de identidade por um UUID manual. Se `MakePlayer` falhar, o erro inclui o UUID da criatura criada para diagnóstico. O código não apaga nem transforma automaticamente a criatura ao falhar.

O `settings.json` antigo, que apontava para o avatar, é descartado na primeira sessão com o novo mod. Se o bridge antigo estava configurado com `FLYBG3_NPC_UUID` ou `npc_uuid` do avatar, limpe esse filtro ou substitua pelo UUID impresso para Flyman. Repetir `!flybg3_spawn` no mesmo nível tenta recuperar a criatura existente antes de criar outra.

## Estado do Toolkit

O executável da BG3 Toolkit está presente, mas, ao escolher a pasta real do jogo, ele informou ausência dos dados `Data/Editor`. No disco, `Data/Editor` contém apenas `Config`, criada pela configuração da ferramenta; os dados de projeto do DLC **BG3 Toolkit Data** não estão instalados nesta máquina. A documentação oficial requer esse DLC para abrir projetos no editor. Enquanto ele não estiver disponível, o template é fonte LSX editável no repositório e é compilado para LSF por LSLib. O template binário, a localização e a estrutura do PAK passaram na validação local; a aparência, o retrato, o recrutamento e o turno precisam de teste dentro do BG3. Não afirmamos que o editor já abriu ou validou o projeto.

Depois de instalar o DLC, o próximo passo de edição visual é abrir/criar o projeto FlyBG3 no Toolkit, localizar o root `FlyBG3_MudMephit_Flyman`, conferir a herança de `MEPHIT_Mud_A` e testar a criatura em Game Mode. Essa etapa não deve alterar o circuito neural.
