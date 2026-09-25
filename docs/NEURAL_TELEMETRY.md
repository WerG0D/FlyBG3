# Telemetria neural do FlyBG3

Esta camada **observa os spikes já produzidos** pelo MaleCNS v1.0. Ela não injeta estímulos, não executa steps adicionais, não altera voltagens ou pesos e não participa do decoder. O decoder de produção continua recebendo somente as taxas de DNa02, DNp01, DNg100 e MDN. Distância, ângulo, velocidade e heading aparecem apenas como contexto no monitor.

## Evidência do dataset instalado

Os nomes e as contagens abaixo foram consultados diretamente em `%USERPROFILE%\fly-data\brain.npz` (`cell_type`, `side`, `superclass`) da instalação `flybrain 0.1.0`, em 24/09/2026. `python tools/inspect_brain.py --telemetry` repete a validação na instalação atual. A anatomia publicada é o [MaleCNS v1.0](https://male-cns.janelia.org/) de [Berg et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC12636603/). Os números são *neurônios*, não spikes esperados.

| Barra ou sonda | Tipos exatos no NPZ | Neurônios | Interpretação e limite |
| --- | --- | ---: | --- |
| STEER LEFT | DNa02, lado L | 1 | Atividade descendente relacionada a steering. [Yang et al.](https://elifesciences.org/articles/102230) relacionam DNa02 a steering de alto ganho; um spike não prova intenção consciente de virar. |
| STEER RIGHT | DNa02, lado R | 1 | Mesmo circuito, lado R, mostrado separadamente. |
| ESCAPE | DNp01, DNp02, DNp11 | 6 (2 cada) | Agregado *escape-related*. DNp01 é o giant fiber; DNp02/DNp11 participam de componentes de salto/fuga, mas não representam um único comando. [Zhang et al.](https://pubmed.ncbi.nlm.nih.gov/36599984/), [Cande et al.](https://elifesciences.org/articles/34275). |
| GROOMING | DNg11 e DNg12_a…e | 45 (6 + 39) | Sonda de circuitos associados a grooming anterior. A associação funcional direta é sobretudo de DNg11 e de DNg12 como família; **não foi demonstrada aqui para cada subtipo do MaleCNS**. [Guo et al.](https://doi.org/10.1016/j.cub.2021.12.055). |
| PAM | PAM01…PAM15 | 316 | Atividade simulada de neurônios anotados PAM; não é uma medição de liberação de dopamina. Subtipos têm papéis heterogêneos. [Aso et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4273436/), [Otto et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7443709/). |
| PPL1 | PPL101…PPL108 | 16 | Atividade simulada de neurônios anotados PPL1; não é uma escala de aversão. [Boto et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC6585410/). |

O nome agregado `DNg12` **não** existe como cell type exato: somente `DNg12_a`, `_b`, `_c`, `_d`, `_e` (8, 16, 5, 4 e 6 neurônios). Igualmente, `PAM` e `PPL1` não existem como tipos exatos no NPZ: são famílias enumeradas acima. A resolução no início do bridge compara cada nome com o dataset; uma família totalmente ausente desativa só aquela barra e emite `WARNING`.

`DNg29` (2) e `DNg84` (2) existem no MaleCNS, porém a evidência consultada não sustenta chamá-los de grooming. `DNg29` foi estudado em [controle de voo](https://pubmed.ncbi.nlm.nih.gov/35090590/); ambos podem aparecer apenas como sondas sem interpretação motora em `--debug`. `DNp09` (2) pode produzir marcha seguida de freezing, dependendo de contexto e sequência; portanto **STOP** não é uma barra confiável. [Cande et al.](https://elifesciences.org/articles/34275). DNg100 (2) e MDN (4) já são lidos como forward/backward pelo decoder; [MDN](https://pubmed.ncbi.nlm.nih.gov/28238656/) tem evidência direta para marcha para trás. DNp02/DNp11 são candidatos a jump/takeoff, já incluídos na sonda ESCAPE. Não se inferem ações novas dessas sondas.

## Grandezas e apresentação

Para cada grupo, `firing_rate_hz = spike_count / (neuron_count × window_seconds)`. A janela usa os mesmos últimos `decoder.decision_window` steps de `brain.simulate` (50 × 0,02 s = 1 s por padrão). O campo `spikes` de cada grupo refere-se a essa janela. `active_neurons` conta índices distintos que dispararam ao menos uma vez durante **toda** a decisão; `total_spikes` soma todos os disparos. Não são salvos 166.700 valores individuais.

O agregado ESCAPE e o agregado GROOMING são taxas normalizadas pelos respectivos tamanhos das populações unidas, e os valores de cada tipo permanecem em `individual_groups` para debug. Essa agregação não afirma que todos os componentes tenham o mesmo papel. Os valores em `telemetry.json` são **taxas brutas**. A suavização EMA e a escala das barras são aplicadas **somente no processo do dashboard**, após ler o arquivo; nenhum dos dois valores retorna ao bridge ou ao decoder. Os tetos em Hz são escolhas de escala visual, configuráveis, não limites biológicos. O monitor mostra a taxa bruta mesmo quando a barra visual satura.

PAM/PPL1 são rótulos anatômicos de grupos dopaminérgicos; este LIF não modela adequadamente liberação de dopamina, plasticidade ou estados internos de reforço. `activity != pleasure`, `activity != happiness`, `activity != conscious reward`. As barras registram apenas atividade simulada no modelo atual. A inferência de comportamento biológico a partir da atividade desses grupos exige experimentos independentes.

No teste local com a configuração padrão, PAM/PPL1 já apresentaram aproximadamente 42/29 Hz por neurônio em um cenário lateral fraco e PAM chegou a 50 Hz em looming. Isso é atividade basal/saturação **do modelo**, não uma descoberta de recompensa no jogo. O teto visual padrão dessas barras foi colocado em 50 Hz para evitar saturação artificial ainda maior; a taxa bruta permanece ao lado da barra.

## Reproduzir

Em um terminal, mantenha `python -m flybg3 --config config/default.toml` executando. Em outro, rode `python -m flybg3 telemetry` ou `python -m flybg3 telemetry --debug`. O monitor lê `telemetry.json` no mesmo diretório do bridge e atualiza apenas quando `session_id`/`request_id` mudar. Para testes sem BG3, `python tools/fake_bg3.py --scenario all` exercita o mesmo MaleCNS, mas não cria uma nova request no bridge; use `--bridge-dir` para alimentar o bridge de arquivos.

Para o teste no jogo, use `!flybg3_status` até `brain=ready` e depois `!flybg3_observe`. `!flybg3_physical off` é opcional para medir decisões sem mover o Flyman; `!flybg3_physical on` restaura a execução física. Compare o `request_id` e a decisão do console BG3 com o monitor. `heading_degrees`, `relative_angle`, distância e velocidade exibidos em `--debug` são apenas o conteúdo da observação real; se o campo não estiver disponível, aparece como ausente. O monitor imprime um painel completo por decisão, inclusive em consoles Windows que não mostram corretamente atualizações por cursor. O round trip de observação/decisão/telemetria foi validado no jogo em 24/09/2026.

`telemetry.json` é escrito atomicamente no diretório do bridge. Ele contém `schema_version`, `recorded_at`, `session_id`, `request_id`, grupos, contagens, taxas, contexto, tempos e decisão. A mesma estrutura entra no JSONL da sessão. `action.json` não recebe esses grupos.

### Resultado local reproduzido

`python tools/fake_bg3.py --scenario all` reinicia o cérebro entre os quatro cenários isolados. Seed 42, CPU, 50 steps:

| cenário | DNa02 L/R (Hz) | ESCAPE (Hz/neuron) | decisão | simulação | coleta de telemetria |
| --- | ---: | ---: | --- | ---: | ---: |
| left | 4,0 / 0,0 | 0,3 | TURN_LEFT | 200,6 ms | 2,57 ms |
| right | 0,0 / 3,0 | 0,5 | TURN_RIGHT | 192,9 ms | 2,47 ms |
| looming | 1,0 / 2,0 | 33,5 | RETREAT | 211,4 ms | 2,68 ms |
| none | 0,0 / 0,0 | 0,3 | IDLE | 192,6 ms | 2,47 ms |

A latência varia entre execuções; os números acima medem apenas esta máquina. Um round trip separado via arquivos mediu simulação 211,1 ms, coleta 2,90 ms e escrita atômica de `telemetry.json` 1,68 ms. A atualização Rich do dashboard medida nessa execução levou 0,17 ms; a versão atual imprime um painel completo por decisão para compatibilidade com consoles Windows. `simulation_ms` inclui a instrumentação; `decision_path_ms` desconta a coleta explicitamente medida para que o timeout não dependa desse custo visual. O teste `-m brain` confirmou spikes, taxas, estado de voltagem, scores e decisão idênticos com telemetria ligada/desligada, e o mesmo número de chamadas a `brain.step()`.
