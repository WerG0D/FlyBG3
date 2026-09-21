# Experimentos do connectome

Gerado em `2026-09-21T11:13:19.800438+00:00` com `flybrain 0.1.0`, 166700 neurônios, 25582938 conexões, backend `cpu`.

Cada linha agrega cinco execuções, uma para cada seed fixa. O cérebro, encoder e decoder são resetados entre cenários; fases do mesmo cenário preservam voltagens, spikes, estado do encoder e suavização do decoder. Frequências são spikes por neurônio por segundo na janela de 1 s. A latência é de parede, inclui a instrumentação das sondas adicionais e não é determinística. `DNp01` é o máximo entre os dois lados; `other_DNs` mostra o maior candidato adicional por frequência média. O decoder recebeu somente as oito taxas de DNa02, DNp01, DNg100 e MDN.

| scenario / phase | DNa02_L | DNa02_R | DNp01 | DNg100 | MDN | other_DNs | decision | consistency | latency ms |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| threat_left_low/stimulus | 3.80 | 0.20 | 0.80 | 0.10 | 0.30 | DNg103_L 6.40 | turn_left:5 | 100% | 260.7 ± 70.7 |
| threat_left_medium/stimulus | 4.00 | 0.00 | 17.80 | 0.10 | 0.50 | DNp02_L 16.60 | retreat:5 | 100% | 271.4 ± 58.3 |
| threat_left_high/stimulus | 4.20 | 0.20 | 43.00 | 0.10 | 0.80 | DNp02_L 39.60 | retreat:5 | 100% | 305.2 ± 74.7 |
| threat_right_low/stimulus | 0.20 | 3.00 | 0.40 | 0.20 | 0.35 | DNg103_R 6.40 | turn_right:5 | 100% | 316.0 ± 105.5 |
| threat_right_medium/stimulus | 0.00 | 3.60 | 16.80 | 0.20 | 0.45 | DNp02_R 16.00 | retreat:5 | 100% | 295.5 ± 89.6 |
| threat_right_high/stimulus | 0.00 | 4.00 | 39.20 | 0.10 | 0.70 | DNp02_R 27.20 | retreat:5 | 100% | 280.5 ± 87.2 |
| threat_front/stimulus | 2.20 | 2.00 | 45.60 | 0.30 | 0.85 | DNp02_L 35.80 | retreat:5 | 100% | 279.3 ± 63.7 |
| approaching_slowly/stimulus | 1.20 | 1.20 | 2.40 | 0.20 | 0.50 | DNg103_L 6.40 | retreat:5 | 100% | 233.3 ± 16.0 |
| approaching_quickly/stimulus | 2.20 | 2.00 | 45.60 | 0.30 | 0.85 | DNp02_L 35.80 | retreat:5 | 100% | 241.6 ± 10.5 |
| moving_away/stimulus | 1.00 | 1.00 | 0.00 | 0.20 | 0.30 | DNg103_L 6.40 | idle:5 | 100% | 235.9 ± 15.7 |
| stationary/stimulus | 1.00 | 1.00 | 0.00 | 0.20 | 0.30 | DNg103_L 6.40 | idle:5 | 100% | 226.4 ± 12.9 |
| no_stimulus/silence | 0.00 | 0.40 | 0.00 | 0.10 | 0.35 | DNg103_L 6.60 | idle:5 | 100% | 233.2 ± 6.8 |
| left_to_right/left | 3.80 | 0.20 | 0.80 | 0.10 | 0.30 | DNg103_L 6.40 | turn_left:5 | 100% | 224.8 ± 10.2 |
| left_to_right/right | 0.40 | 3.00 | 0.20 | 0.00 | 0.25 | DNg103_L 7.40 | turn_right:5 | 100% | 264.9 ± 54.3 |
| threat_then_silence/threat | 4.20 | 0.20 | 43.00 | 0.10 | 0.80 | DNp02_L 39.60 | retreat:5 | 100% | 273.4 ± 61.7 |
| threat_then_silence/silence | 1.00 | 0.40 | 1.00 | 0.00 | 0.45 | DNg103_L 8.40 | retreat:5 | 100% | 276.4 ± 63.7 |
| threat_then_silence/silence[2] | 1.60 | 0.40 | 0.00 | 0.10 | 0.20 | DNg103_L 8.00 | retreat:5 | 100% | 265.3 ± 64.9 |
| threat_then_silence/silence[3] | 0.40 | 0.00 | 0.00 | 0.00 | 0.35 | DNg103_L 8.00 | idle:3, retreat:1, turn_left:1 | 60% | 301.7 ± 112.0 |

## Definição dos estímulos

- `threat_left_low`: Ameaça a -75°, baixa aproximação. stimulus=ângulo -75°, distância 12 m, closing_speed +0.25 m/s × 1
- `threat_left_medium`: Ameaça a -75°, aproximação média. stimulus=ângulo -75°, distância 8 m, closing_speed +2 m/s × 1
- `threat_left_high`: Ameaça a -75°, aproximação alta. stimulus=ângulo -75°, distância 4 m, closing_speed +8 m/s × 1
- `threat_right_low`: Ameaça a +75°, baixa aproximação. stimulus=ângulo +75°, distância 12 m, closing_speed +0.25 m/s × 1
- `threat_right_medium`: Ameaça a +75°, aproximação média. stimulus=ângulo +75°, distância 8 m, closing_speed +2 m/s × 1
- `threat_right_high`: Ameaça a +75°, aproximação alta. stimulus=ângulo +75°, distância 4 m, closing_speed +8 m/s × 1
- `threat_front`: Ameaça frontal simétrica em aproximação alta. stimulus=ângulo +0°, distância 4 m, closing_speed +8 m/s × 1
- `approaching_slowly`: Alvo frontal aproximando lentamente. stimulus=ângulo +0°, distância 10 m, closing_speed +0.5 m/s × 1
- `approaching_quickly`: Alvo frontal aproximando rapidamente. stimulus=ângulo +0°, distância 5 m, closing_speed +8 m/s × 1
- `moving_away`: Alvo frontal afastando; looming é retificado em zero. stimulus=ângulo +0°, distância 6 m, closing_speed -4 m/s × 1
- `stationary`: Alvo frontal imóvel; permanece apenas tracking visual. stimulus=ângulo +0°, distância 8 m, closing_speed +0 m/s × 1
- `no_stimulus`: Nenhum alvo ou dano. silence=sem alvo × 1
- `left_to_right`: Continuidade temporal: esquerda seguida por direita. left=ângulo -75°, distância 12 m, closing_speed +0.25 m/s × 1; right=ângulo +75°, distância 12 m, closing_speed +0.25 m/s × 1
- `threat_then_silence`: Ameaça alta seguida por três janelas sem estímulo. threat=ângulo -75°, distância 4 m, closing_speed +8 m/s × 1; silence=sem alvo × 3

Intensidade não é uma ação nem uma classe comportamental. É apenas a combinação declarada de distância e velocidade de fechamento que o encoder transforma em voltagem de LC4/LPLC2/LPLC1; LC10a recebe tracking lateral. Velocidade negativa é retificada para zero no canal looming.

## Persistência

- `threat[1]`: DNp01 L/R 43.00/24.60 Hz; decisões {'retreat': 5}.
- `silence[1]`: DNp01 L/R 1.00/0.20 Hz; decisões {'retreat': 5}.
- `silence[2]`: DNp01 L/R 0.00/0.00 Hz; decisões {'retreat': 5}.
- `silence[3]`: DNp01 L/R 0.00/0.00 Hz; decisões {'idle': 3, 'retreat': 1, 'turn_left': 1}.

## Sondas de outros descending neurons

- `DNp02` respondeu fortemente a looming alto: L/R 39.6/22.2 Hz para ameaça esquerda e 24.2/27.2 Hz para direita. `DNp11` também subiu para 25.0/13.2 e 13.0/25.0 Hz. Isso concorda com a literatura de jump/escape, mas nenhum deles entra no decoder atual.
- `DNg13` mostrou resposta modesta e lateral em baixa intensidade: L/R 3.0/2.4 Hz para esquerda e 2.0/3.4 Hz para direita. É candidato a uma futura comparação de steering, ainda sem peso no readout.
- `DNg103` apresentou baseline alto em silêncio (6.6/6.4 Hz) e pouca discriminação nesta bateria; não há base para tratá-lo como STOP. `DNp09`, `DNp26`, `DNp10` e `DNa01` também não produziram aqui um sinal mais limpo que os grupos atuais.

O JSON contém, por execução e fase, o estímulo exato, spikes, todas as taxas monitoradas, scores, decisão, tempos e um resumo residual: voltagem média/p95 da rede, fração acima de 0,5, spikes do último step e voltagens agregadas dos DNs monitorados. Nenhum desses campos residuais é entrada do decoder.

## Leitura cautelosa

As seeds medem sensibilidade ao ruído do modelo, não variabilidade biológica. Simetria anatômica imperfeita, pequeno número de neurônios por tipo e estado inicial podem produzir diferenças laterais. Consistência aqui significa repetição dentro deste LIF e deste encoder, não validação contra comportamento real.
