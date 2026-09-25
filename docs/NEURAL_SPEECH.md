# Neural Speech: verbalização simbólica da atividade neural

Esta feature opcional mapeia taxas de disparo simuladas do MaleCNS v1.0 para uma intenção curta, uma frase fixa e áudio local. O caminho motor continua independente:

```text
observação BG3 → encoder → MaleCNS → taxas dos descending neurons
                                      ├→ MotorDecoder → action.json → BG3
                                      └→ SpeechDecoder → SpeechIntent → template → fila → TTS
```

`SpeechDecoder.decode(request_id, rates_hz)` recebe **somente** as taxas da janela neural que `FlyBrainAdapter.simulate()` já calculou. Não recebe observação BG3, distância, ângulo, HP, combate, `ActionType` nem scores motores. O bridge só invoca a fala **depois** de publicar `action.json`. A fala não chama `brain.step()`, não injeta corrente e não altera o estado do connectome. Não há LLM ou serviço externo.

## Grupos e regra explícita

| Leitura | Tipos MaleCNS confirmados | Uso |
| --- | --- | --- |
| steering L/R | `DNa02` L/R, 1 neurônio por lado | lateralidade simbólica |
| escape | `DNp01` L/R, 1 por lado | urgência e prioridade de perigo |
| forward | `DNg100` L/R, 1 por lado | `APPROACH` experimental |
| backward | `MDN` L/R, 2 por lado | `RETREAT` experimental |

Essas taxas são médias de disparos por neurônio por segundo nos últimos `decoder.decision_window` steps. `DNp02` e `DNp11` permanecem sondas de telemetria; a barra `ESCAPE` do painel agrega três tipos, mas o SpeechDecoder usa **apenas DNp01** para o limiar de perigo. `PAM`/`PPL1` e grooming não são usados para texto. Não há `STOP`: o grupo `DNp09` ainda não oferece um sinal confiável para essa palavra.

Com os padrões de `config/default.toml`:

1. `escape = max(DNp01_L, DNp01_R)`; `urgency = min(1, escape / 20 Hz)`.
2. `lateral_confidence = |DNa02_L - DNa02_R| / max(DNa02_L + DNa02_R, ε)`.
3. Lateralidade é forte se a diferença for ≥ 1 Hz **e** `lateral_confidence ≥ 0,35`.
4. Se escape ≥ 3 Hz, escolha `DANGER_LEFT`/`DANGER_RIGHT` quando houver lateralidade forte; caso contrário `DANGER`. Sua confiança é `urgency`.
5. Caso contrário, lateralidade forte escolhe `LEFT`/`RIGHT`, confiança `lateral_confidence`.
6. Caso contrário, diferença média de `MDN - DNg100` ≥ 1 Hz escolhe `RETREAT`; o inverso escolhe `APPROACH`. Confiança é a diferença dividida por 20 Hz, limitada a 1.
7. Qualquer confiança abaixo de 0,35 produz `SILENT`. Baixa atividade também produz `SILENT`; `speak_idle=true` permite `IDLE` quando todas as taxas estão abaixo de 1 Hz.

O limiar de escape e o limiar de confiança são separados: escape de 4 Hz já é candidato a perigo, mas sua confiança 0,20 ainda suprime a frase. Essa regra evita transformar disparos fracos em afirmações. `confidence` é uma medida operacional de dominância do readout, **não** uma probabilidade calibrada de significado biológico. `urgency` só usa DNp01, nunca distância, dano ou HP diretamente.

## Frases e silêncio

`SILENT → nenhuma frase`; `IDLE → “Quiet.”`; `LEFT/RIGHT → “Left.”/“Right.”`; `DANGER → “Danger.”`; `DANGER_LEFT/RIGHT → “Danger. Left.”/“Danger. Right.”`; `RETREAT → “Away.”`; `APPROACH → “Closer.”`. A tabela é determinística.

A política de saída favorece transições: uma intenção nova pode falar de imediato; a mesma intenção só repete após `cooldown_seconds` (2 s). Uma janela `SILENT` limpa o estado da transição. Áudio pendente de direção é substituído pela direção mais recente, inclusive `RIGHT → DANGER_RIGHT`. A fila tem capacidade limitada (`queue_size=2`); quando lotada descarta o evento pendente mais antigo. Não interrompe áudio já em execução.

## TTS e arquivos

O provider `windows` usa o `System.Speech.Synthesis.SpeechSynthesizer` local via Windows PowerShell 5.1, sem pacote Python extra e sem Internet. [`SpeechSynthesizer.Speak`](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.speak?view=netframework-4.8.1) é síncrono, por isso roda **somente no worker**; o loop que processa BG3 apenas faz enqueue. O provider é sondado ao iniciar. Se PowerShell, `System.Speech`, voz instalada ou dispositivo falhar, o bridge registra warning, mantém a decisão neural e usa `NullTTSProvider` ou marca o evento como `failed`. O teste local em 24/09/2026 encontrou as vozes Microsoft Maria Desktop e Microsoft Zira Desktop e executou `speech-test` com quatro frases sem erro.

`speech.json` é escrito atomicamente no mesmo diretório de `action.json`, sempre com `schema_version`, `session_id`, `request_id`, intenção, confiança, urgência, grupos fonte, oito taxas neurais, texto, status e tempos. **Não contém world-state bruto.** `queued=true` significa somente aceito na fila; `spoken=true` só é escrito após `Speak()` retornar sem erro. A conclusão gera uma segunda linha `type="speech"` no JSONL da sessão. O dashboard exibe intenção, texto, confiança, urgência e status apenas quando `session_id` e `request_id` coincidem com `telemetry.json`.

O tempo de simulação permanece em `telemetry.json`; `speech.json.timings` mede separadamente `speech_decode_ms`, `verbalization_ms` e `queue_enqueue_ms`. O tempo efetivo de reprodução ocorre no worker e não atrasa o próximo processamento. No teste isolado com MaleCNS real, a simulação levou cerca de 200 ms; o decode de fala levou ~0,02 ms, verbalização ~0,002 ms e enqueue ~0,015 ms. Latências variam por máquina.

## Como rodar

O padrão é `enabled=false`. Para uma sessão de teste, mantenha um único bridge e execute:

```powershell
.\.venv\Scripts\Activate.ps1
python -m flybg3 speech-test
python -m flybg3 --config config\default.toml --speech
```

Alternativamente copie `config/example.toml` para uma configuração local, ajuste `[bridge].directory` para o caminho real ou deixe vazio e use `[speech].enabled=true`; depois inicie com `python -m flybg3 --config config\local.toml`. `provider="null"` exercita toda a lógica de intenção, arquivos e fila sem som.

Para teste sem jogo, `python tools\fake_bg3.py --config config\example.toml --scenario all` produz LEFT, RIGHT, DANGER e SILENT com o cérebro real sem reproduzir áudio. Para testar arquivos e voz juntos, mantenha o bridge acima rodando com `--directory runtime\speech-demo` e execute `python tools\fake_bg3.py --bridge-dir runtime\speech-demo --scenario left`; então consulte `runtime\speech-demo\speech.json`. O modo contínuo permite que o worker conclua o áudio. `--once` aguarda somente no encerramento desse teste até 15 s pelo áudio pendente; isso não afeta o bridge contínuo.

No BG3, com o bridge de voz já iniciado, use no console server-side `!flybg3_physical off` para um teste sem deslocamento, `!flybg3_status` e `!flybg3_observe`. A console BG3 deve continuar mostrando `Observation #N sent` e `Neural decision #N`. O Python registra `Speech intent: ...; text='...'`. Essa feature não altera o PAK ou os comandos Lua; não habilita movimento físico. A verificação ao vivo dentro de um save com este novo código ainda depende de abrir BG3 e executar a observação manual.

## Limites científicos

As frases são símbolos definidos por software a partir de quatro famílias de neurônios descendentes em uma simulação LIF. Os rótulos motores vêm da literatura e do projeto fly.ai, mas nenhuma frase é uma tradução de atividade linguística da mosca. O modelo não reproduz dendritos detalhados, neuromodulação, plasticidade, corpo nem contexto sensorial biológico completo.

**The generated sentences are symbolic verbalizations of simulated neural activity. They are not evidence that the simulated fly possesses language, subjective thoughts, fear, pleasure, or consciousness.**
