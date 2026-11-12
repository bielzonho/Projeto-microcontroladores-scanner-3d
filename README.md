# EEN251 - Microcontroladores e Sistemas Embarcados
---

# Projeto Scanner 3D

Desenvolvimento de um scanner 3D com microcontroladores para digitalização de objetos físicos.

---

### Como cada parte está estruturada:

* **ARQUIVOS:** o que salvar na sua pasta

* **COMO EXECUTAR:** exatamente o que digitar

* **VOCÊ DEVE VER:** como um resultado correto se parece

* **COMO FUNCIONA:** a ideia, resumidamente

* **ALTERE:** onde editar se quiser experimentar

## 1. CONFIGURAÇÃO INICIAL (ÚNICA VEZ)

### 1.1 Instale o Python 3 (versão 3.9 ou mais recente)

* **Windows:** vá para [python.org/downloads](https://www.python.org/downloads/), baixe e execute o instalador. **IMPORTANTE:** marque a opção `"Add python.exe to PATH"` na primeira tela e clique em `"Install Now"`.

* **Linux:** O Python 3 normalmente já vem instalado.

* **macOS:** instale a partir de python.org se `python3 --version` não funcionar.

Verifique se funciona. Abra um terminal (veja 1.5) e digite:

* **Windows:** `python --version` (se falhar, tente: `py --version`)

* **Linux / macOS:** `python3 --version`

Você deve ver algo como `Python 3.12.1`.

> **NOTA:** Abaixo eu escrevo `python`. No Linux e macOS, digite `python3` em vez disso. No Windows, se `python` não funcionar, digite `py`.

### 1.2 Instale as bibliotecas que usamos

Digite isto no terminal (em uma única linha):

```
python -m pip install numpy matplotlib opencv-python

```

Aguarde até terminar sem mensagens de erro em vermelho.

* `numpy`: matemática em matrizes (arrays) de números

* `matplotlib`: desenho da pré-visualização 3D

* `opencv-python`: processamento de imagem (usado a partir da Parte C)

**Apenas Linux / Raspberry Pi OS:** se o pip disser `externally-managed-environment`, instale os pacotes do sistema em vez disso:

```
sudo apt install python3-numpy python3-matplotlib python3-opencv

```

### 1.3 Crie a pasta do projeto

Crie uma pasta chamada `scanner3d` em algum lugar fácil, por exemplo, dentro de `Documentos` (`Documents`). Todos os arquivos do projeto devem ficar **DENTRO DESTA PASTA**, todos no mesmo lugar (sem subpastas). Os programas encontram uns aos outros porque ficam lado a lado.

### 1.4 Um lugar para ler e editar o código

Qualquer editor de texto funciona. Recomendado: **Visual Studio Code** (gratuito, [code.visualstudio.com](https://code.visualstudio.com/)). Abra-o, escolha *Arquivo > Abrir Pasta* (*File > Open Folder*) e selecione `scanner3d`. O Bloco de Notas (Notepad) também funciona, mas não mostra cores.

Você só precisa editar um arquivo se uma nota **ALTERE** mandar.

### 1.5 Abra um terminal DENTRO da pasta

* **Windows:** abra a pasta `scanner3d` no Explorador de Arquivos, clique na barra de endereços no topo, digite `cmd` e pressione Enter. Uma janela preta se abrirá, já dentro da pasta correta.

* **Linux:** abra um terminal e digite: `cd ~/Documents/scanner3d`

* **macOS:** abra o Terminal e digite: `cd ~/Documents/scanner3d`
  *(ajuste o caminho se você colocou a pasta em outro lugar, ex: `~/Documentos/scanner3d`)*

Verifique se você está no lugar certo: digite `dir` (Windows) ou `ls` (Linux / macOS). Você deve ver `mesh.py` na lista.

Cada comando neste guia deve ser digitado nesse terminal, seguido de Enter.

## PARTE A - O GERADOR DE MALHA (`mesh.py`)

**O que ele faz:** transforma "fatias" (*slices*) de um objeto em um arquivo de malha 3D (`.obj`).
Uma fatia = para um ângulo da plataforma, uma lista de pontos `(raio, altura)`.

* **ARQUIVOS:** `mesh.py`

* **COMO EXECUTAR:**

```
python mesh.py

```

### VOCÊ DEVE VER no terminal:

```
1202 vertices, 2400 faces
closed mesh: True
signed volume: 81861.2 (outward)

```

e um novo arquivo `fake_vase.obj` aparecerá na pasta.

* `closed mesh: True` = sem buracos.

* `outward` = as faces apontam para fora. Se você vir `INSIDE-OUT`, a ordem das faces está errada (virada do avesso).

### COMO FUNCIONA:

1. Cada ponto é `(r, z)` em algum ângulo `theta`:
   `x = r * cos(theta)` | `y = r * sin(theta)` | `z = z`

2. Fatias vizinhas são unidas com triângulos (a última fatia se junta de volta à primeira, fechando a superfície ao redor).

3. O topo e a base recebem uma tampa plana feita de triângulos em formato de leque a partir de um ponto no eixo central.

4. O arquivo `.obj` é texto puro: linhas `v x y z` são pontos (vértices), linhas `f a b c` são triângulos (faces) que usam os números dos pontos (contando a partir de 1).

### ALTERE:

A função `fake_scan()` perto do topo de `mesh.py` constrói o vaso de exemplo. Altere os números nela (`num_angles`, `num_heights`, a fórmula do raio) e execute novamente.
`build_mesh(slices, scale=1.0)`: `scale` converte pixels em milímetros para escaneamentos reais.

## PARTE B - O VISUALIZADOR (`viewer.py`)

**O que ele faz:** desenha qualquer arquivo `.obj` para que você possa vê-lo.

* **ARQUIVOS:** `viewer.py`

* **COMO EXECUTAR:**

```
python viewer.py fake_vase.obj

```

Uma janela se abre. Segure o botão esquerdo do mouse e arraste para girar.

*Sem janela / erro de exibição?* Salve uma imagem em vez disso:

```
python viewer.py fake_vase.obj --save preview.png

```

e depois abra o arquivo `preview.png`.

### VOCÊ DEVE VER:

Um vaso azul com uma cintura fina e três lóbulos suaves.

### ALTERE:

`--elev 40 --azim 30` muda o ângulo de visão, ex.:

```
python viewer.py fake_vase.obj --save top.png --elev 80

```

> **Dica:** MeshLab (gratuito) ou Blender (gratuito) mostram arquivos `.obj` com mais recursos. Ambos abrem `fake_vase.obj` diretamente.

## PARTE C - ENCONTRANDO A LINHA DO LASER EM UMA FOTO

**O que ela faz:** pega quadros (*frames*) da câmera e encontra onde a linha do laser está em cada linha horizontal da imagem, depois converte pixels em milímetros. O resultado é a lista de pontos `(raio r, altura z)` por ângulo que a Parte A precisa.

Para demonstração e testes no PC sem câmera, o `laser_sim.py` gera imagens simuladas (uma linha de laser no vaso, brilho de lâmpada e ruído). Com a câmera real, você usará fotos reais e o mesmo detector.

* **ARQUIVOS (4 novos, na mesma pasta de antes):**

  * `scanner_config.py`: os números que descrevem a configuração da câmera

  * `laser_sim.py`: gera imagens simuladas para testes no PC

  * `detect_line.py`: **O DETECTOR** (código principal de detecção)

  * `test_detector.py`: executa o detector e verifica a precisão

* **COMO EXECUTAR:**

```
python test_detector.py

```

### VOCÊ DEVE VER:

```
laser-on minus laser-off : mean error 0.010 mm, 95% under 0.062 mm, worst 0.098 mm
single frame, threshold 180: mean error 0.025 mm, worst 0.1 mm ...
single frame, threshold 235: mean error 0.032 mm, worst 0.1 mm ...
single frame, threshold 250: mean error 0.043 mm, worst 0.1 mm ...
saved detector_demo.png

```

Abra `detector_demo.png`. Quatro painéis:

1. **laser ON:** foto com a linha do laser e o brilho da lâmpada

2. **laser OFF:** mesma cena, laser desligado (apenas lâmpada)

3. **ON minus OFF:** resta apenas o laser, a lâmpada sumiu

4. **green dots:** (pontos verdes) onde o detector encontrou a linha

Os pontos verdes devem ficar exatamente sobre a linha.

### COMO LER OS NÚMEROS:

`error` (erro) = raio detectado menos raio verdadeiro, em milímetros.
Um pixel de imagem equivale a cerca de `0.24 mm` de raio nesta configuração (`1 / (6 pixels por mm × 0.707)`). Erros abaixo disso significam que o cálculo de sub-pixel está funcionando.

### COMO FUNCIONA (os passos dentro de `detect_line.py`):

1. **Subtração de fundo (`laser_signal`):** Duas fotos por ângulo da plataforma: laser LIGADO (ON) e laser DESLIGADO (OFF). Subtraia o canal vermelho. Qualquer coisa que não seja o laser (lâmpada, janela, tela) está em ambas as fotos e se cancela.

2. **Sub-pixel (`find_line_columns`):** Em cada linha horizontal da imagem, pegue o pixel mais brilhante e faça a média dos pixels vizinhos ponderada pelo brilho. Isso dá a posição da linha com precisão maior que um pixel. Linhas sem laser são ignoradas.

3. **Filtro (`reject_outliers`):** Descarte detecções que saltam para longe de seus vizinhos.

4. **Pixels para milímetros (`columns_to_profile`):**

   * `z = (BASE_ROW - row) / PX_PER_MM`

   * `r = (column - AXIS_COL) / (PX_PER_MM * sin(ALPHA))`

   * *Por que `sin(ALPHA)`:* a câmera olha para o corte do laser de lado, no ângulo `ALPHA`. Um ponto a `r mm` do eixo só se desloca `r * sin(ALPHA)` lateralmente na imagem. A `45°`, isso é `0.707`.

5. **Reamostragem (`resample`):** Escolha um número fixo de alturas igualmente espaçadas, para que cada fatia tenha o mesmo número de pontos, como `mesh.py` exige.

### DETALHES IMPORTANTES DO MÉTODO:

* O método `ON-menos-OFF` possui de 2 a 4 vezes menos erro que usar apenas uma foto com limiar fixo (`threshold`), e seu limiar (`min_signal = 40`) não exige reajuste constante quando a luz ambiente muda.

* **Limite de saturação:** se a luz ambiente for tão forte que a câmera mostre branco puro (`255`) em **AMBAS** as fotos, a diferença ali será zero e a linha do laser ficará invisível. Não aponte a câmera para uma lâmpada forte ou janela, e diminua a exposição da câmera.

### ALTERE (experimentos, depois execute `python test_detector.py` novamente):

* `scanner_config.py`: `PX_PER_MM`, `ALPHA_DEG` ... (veja "câmera real" abaixo)

* `laser_sim.py`: em `render_frame()`, tente `noise_sigma=3.0`, `lamp=False`, `line_sigma=1.6` (linha mais grossa).

* `test_detector.py`: `NUM_ANGLES` (mais ângulos = escaneamento mais fino), `NUM_POINTS` (pontos por fatia).

### O QUE ISSO SIGNIFICA PARA A CÂMERA REAL:

Os quatro números em `scanner_config.py` são valores de **CALIBRAÇÃO**. Com o scanner real, você os mede (a Parte E tem um programa auxiliar que os mede a partir de fotos; a lista abaixo é o método manual):

* `AXIS_COL`: coluna da imagem correspondente ao eixo de rotação da plataforma. Coloque uma haste fina e reta exatamente no meio da plataforma e leia sua coluna em uma foto. Gire a plataforma `180°`: a haste deve permanecer na mesma coluna.

* `BASE_ROW`: linha horizontal da imagem onde o laser encontra a superfície da plataforma (laser ligado, plataforma vazia).

* `PX_PER_MM`: fotografe um objeto de altura conhecida (ex: um bloco de `50 mm`), meça sua altura em pixels e divida os pixels pelos milímetros.

* `ALPHA_DEG`: ângulo entre o plano do laser e a direção da câmera. Meça no suporte com um transferidor e depois refine com um bloco de tamanho conhecido: altere `ALPHA_DEG` até que o raio medido bata com o do bloco.

**Observações para a montagem real:**

* Se a câmera real ficar acima da plataforma e vir a cena inclinada, use a **Parte F** para aplicar a transformação de perspectiva.

* Partes do objeto que escondem a linha do laser da visão da câmera (amassados, cantos vivos) ficarão faltando ou interpoladas.

* **Direção de rotação:** se a plataforma girar para o lado oposto ao que `mesh.py` assume, a malha final parecerá espelhada. Correção: inverta a lista de fatias antes de construir a malha (`slices = slices[::-1]`) ou use `--mirror` no `scan_folder.py`. Nunca inverta o sinal de `y`, pois isso vira a malha do avesso.

## PARTE C-2 - TESTE PRÁTICO DO DETECTOR DE LINHA (`try_detector.py`)

**Objetivo:** ver o detector funcionando em UMA foto, mudar parâmetros e ver o que acontece.

### PASSO 0 - Verifique a pasta

Sua pasta `scanner3d` deve conter estes arquivos, lado a lado:
`scanner_config.py`, `laser_sim.py`, `detect_line.py`, `try_detector.py`.

### PASSO 1 - Execute sem opções

```
python try_detector.py

```

Você deve ver:

```
angle 0 deg | noise 3 | lamp on | laser 200 | axis error 0 px

  height z    true r    detected r    error
     0.0 mm   23.00 mm     23.08 mm   +0.079 mm
    10.3 mm   31.13 mm     31.13 mm   -0.001 mm
    20.7 mm   30.61 mm     30.61 mm   +0.000 mm
    31.0 mm   22.01 mm     22.00 mm   -0.005 mm
    41.4 mm   14.45 mm     14.45 mm   +0.001 mm
    51.7 mm   15.99 mm     16.00 mm   +0.011 mm

  mean error 0.011 mm   (one image pixel = 0.24 mm)
  GOOD: error is smaller than one pixel

  picture saved: try_result.png

```

**Como ler a tabela:**

* `height z`: altura no vaso, em mm

* `true r`: o raio real naquela altura

* `detected r`: o raio que o detector mediu a partir da foto

* `error`: detectado menos real. Próximo de `0` é bom.

### PASSO 2 - Abra a imagem

Abra `try_result.png`. Ela tem seis áreas:

1. **laser ON:** a foto com a linha do laser (brilho laranja = lâmpada)

2. **laser OFF:** a mesma cena com o laser desligado

3. **ON minus OFF:** resta apenas o laser, a lâmpada sumiu

4. **green dots:** onde o detector achou a linha, sobreposto à foto 1

5. **graph:** curva PRETA = forma verdadeira, pontos VERDES = o que o detector mediu

6. **text:** o veredito (`GOOD` / `BAD`) e o erro médio

Para salvar a imagem com outro nome sem sobrescrever:

```
python try_detector.py --out minha_imagem.png

```

### PASSO 3 - Experimentos (um de cada vez, abra a imagem após cada um)

* **Mudando o ângulo:**

```
python try_detector.py --angle 60

```

*Resultado:* `GOOD`, erro médio `0.011 mm`. A curva preta fica mais fina porque o vaso tem 3 lóbulos e não é perfeitamente redondo.

* **Aumentando o ruído:**

```
python try_detector.py --noise 25

```

*Resultado:* `GOOD`, erro médio `0.043 mm`.

* **Ruído extremo:**

```
python try_detector.py --noise 80

```

*Resultado:* `GOOD`, erro médio `0.141 mm`.

* **Sem lâmpada ambiente:**

```
python try_detector.py --no-lamp

```

*Resultado:* `GOOD`, erro médio `0.009 mm`.

* **Laser mais fraco:**

```
python try_detector.py --laser-peak 80

```

*Resultado:* `GOOD`, erro médio `0.012 mm`.

* **Laser muito fraco (ajuste de sensibilidade):**

```
python try_detector.py --laser-peak 30

```

*Resultado:* `"NO LASER LINE FOUND in this frame"`. O detector ignora sinais mais fracos que `min_signal` (padrão `40.0`).
*Como ajustar para um laser real mais fraco:*

1. Abra `detect_line.py` no seu editor.

2. Encontre esta linha:

```
def find_line_columns(signal, min_signal=40.0, half_window=5):

```

3. Mude `40.0` para `15.0` e salve o arquivo (não use valores muito baixos como `8`, pois começa a pegar ruído em linhas vazias).

4. Execute `python try_detector.py --laser-peak 30` novamente. Quando terminar o teste, volte para `40.0`.

* **Erro de calibração no eixo:**

```
python try_detector.py --axis-error 10

```

*Resultado:* `BAD`, erro médio `2.359 mm`. Os pontos verdes mantêm a forma certa, mas ficam deslocados `2.4 mm` para a esquerda. Isso demonstra por que a calibração precisa é fundamental.

* **Combinando opções:**

```
python try_detector.py --angle 120 --noise 20 --no-lamp --out meu_teste.png

```

### PASSO 4 - Altere um número no arquivo de configuração

1. Abra `scanner_config.py` no seu editor.

2. Encontre a linha `ALPHA_DEG = 45.0` e mude `45.0` para `30.0`. Salve.

3. Execute `python try_detector.py`.

Com um ângulo menor, cada pixel representa mais milímetros (`0.33 mm` em vez de `0.24 mm`), reduzindo a resolução lateral. Um ângulo próximo de `45°` oferece o melhor equilíbrio entre resolução e áreas ocultas. Volte para `45.0` e salve quando terminar.

## PARTE D - O ESCANEAMENTO SIMULADO COMPLETO (`simulate_scan.py`)

**Objetivo:** rodar toda a cadeia de uma só vez:
`objeto -> fotos em cada ângulo (laser on + off) -> detector -> fatias -> malha (.obj) -> imagem`

### PASSO 0 - Verifique a pasta

Estes seis arquivos devem estar lado a lado em `scanner3d`:
`mesh.py`, `viewer.py`, `scanner_config.py`, `laser_sim.py`, `detect_line.py`, `simulate_scan.py`.

### PASSO 1 - Execute

```
python simulate_scan.py

```

Você deve ver:

```
scan took 3.7 s

mesh: 2402 vertices, 4800 faces -> scan.obj
closed mesh: True, outward
volume  scanned 82,114 mm3   true 82,125 mm3   difference -0.01 %
distance between scanned and true surface: mean 0.009 mm, worst 0.101 mm
picture: scan_preview.png

```

Novos arquivos na pasta: `scan.obj` (o modelo 3D) e `scan_preview.png` (uma imagem dele).

### PASSO 2 - Olhe o resultado

Abra `scan_preview.png` ou gire o modelo interativamente:

```
python viewer.py scan.obj

```

### PASSO 3 - Experimentos

* **Poucos ângulos (12 ou 6):**

```
python simulate_scan.py --angles 12
python simulate_scan.py --angles 6

```

Menos fotos deixam a superfície mais facetada (como um prisma de 12 ou 6 lados). Mais ângulos geram uma superfície mais suave, porém levam mais tempo.

* **Com erro de eixo:**

```
python simulate_scan.py --axis-error 10

```

O volume cai `20.34%` e o vaso fica visivelmente mais fino, embora pareça visualmente limpo. Sempre escaneie um objeto de tamanho **CONHECIDO** (ex: um bloco de `50 mm`) primeiro para validar a calibração.

* **Salvando com outro nome:**

```
python simulate_scan.py --angles 30 --noise 15 --out medio.obj --preview medio.png

```

## PARTE E - O ASSISTENTE DE CALIBRAÇÃO (`calibrate.py`)

**Objetivo:** medir os quatro números da câmera a partir de fotos de dois cilindros comuns:

* `PX_PER_MM`: quantos pixels um milímetro ocupa na foto

* `BASE_ROW`: linha da imagem onde fica a superfície da plataforma

* `AXIS_COL`: coluna da imagem onde fica o eixo de rotação da plataforma

* `ALPHA_DEG`: ângulo entre o plano do laser e a visão da câmera

### COMO FUNCIONA

Um cilindro reto (uma lata, um pote) em pé na plataforma faz uma linha de laser **VERTICAL** e reta na foto:

* `altura da linha em pixels ÷ altura real em mm = PX_PER_MM`

* `extremidade inferior da linha = BASE_ROW`

* `coluna da linha = AXIS_COL + raio × PX_PER_MM × sin(ALPHA)`

Com dois cilindros de raios diferentes, o sistema resolve tanto `AXIS_COL` quanto `ALPHA_DEG`, fazendo a média ao redor da plataforma para compensar pequenos desvios de centralização.

### E-1 DEMONSTRAÇÃO NO PC

Arquivos necessários: `scanner_config.py`, `laser_sim.py`, `detect_line.py`, `calibrate.py`.

Execute:

```
python calibrate.py

```

Você verá a tabela com os valores calculados prontos para serem colados no `scanner_config.py`. *(Não cole os números dessa demonstração simulada; cole apenas os valores medidos com suas fotos reais).*

### E-2 COMANDOS E VERIFICAÇÕES

* **Salvar fotos de demonstração:**

```
python calibrate.py --save-photos

```

* **Calibrar a partir de pastas de fotos:**

```
python calibrate.py --cyl calib_A 25 50 --cyl calib_B 35 45

```

* **Aviso de saturação ou erro de digitação:** Se a luz ambiente estourar a imagem (`--strong-lamp`) ou se você digitar a altura de um cilindro errada, os dois cilindros darão `PX_PER_MM` diferentes e o programa emitirá um `WARNING` recusando-se a gerar os valores. Mantenha a exposição da câmera baixa e a sala escura.

### E-3 USANDO COM A CÂMERA REAL

1. Escolha dois cilindros com lados verticais retos e cores claras/foscas (evite superfícies brilhantes, escuras ou transparentes), com raios que difiram em pelo menos `3 mm` (ex: `25 mm` e `35 mm`).

2. Meça o raio (`diâmetro ÷ 2`) e a altura de cada um com uma régua ou paquímetro.

3. Coloque um cilindro aproximadamente no centro da plataforma. Tire pares de fotos (`laser ligado`, `laser desligado`) em 8 a 12 ângulos espaçados **UNIFORMEMENTE** ao redor de uma volta completa (mínimo de 3). Use as mesmas configurações de câmera para todas.

4. Salve-as em uma pasta chamada `calib_A` como `on_00`, `off_00`, `on_01`, `off_01` ... (`.png` ou `.jpg`). Repita para o segundo cilindro em `calib_B`. *(Na Parte I, `capture.py --out calib_A --photos 12` automatiza isso).*

5. Execute:

```
python calibrate.py --cyl calib_A <raio> <altura> --cyl calib_B <raio> <altura>

```

6. Abra `scanner_config.py` e substitua os valores de `PX_PER_MM`, `AXIS_COL`, `BASE_ROW` e `ALPHA_DEG` pelos valores impressos.

7. Escaneie um terceiro objeto de tamanho conhecido e verifique as dimensões no `scan_folder.py` (Parte H).

> **COMO SABER SE PRECISA DA PARTE F:** Nas fotos de um cilindro reto, a linha do laser deve parecer **VERTICAL**. Se ela parecer **INCLINADA** (câmera posicionada acima ou muito perto do objeto), use a **Parte F** em vez desta.

## PARTE F - O MAPA DE PERSPECTIVA (`plane_map.py`)

**Objetivo:** permitir o uso de uma câmera posicionada com inclinação (montada acima ou perto do objeto). Como a câmera é **FIXA**, o mapeamento é medido **UMA VEZ** e salvo em `camera_map.json`.

### DE QUAL EU PRECISO, PARTE E OU PARTE F?

Olhe para uma foto de um cilindro reto com o laser ligado:

* A linha do laser parece **VERTICAL** → A Parte E (`calibrate.py`) é suficiente.

* A linha do laser parece **INCLINADA** → Use a Parte F (`plane_map.py`).

* Na dúvida, use sempre a Parte F, pois ela funciona tanto com inclinação quanto sem inclinação.

### POR QUE É NECESSÁRIO

O laser cria um plano vertical de luz passando pelo eixo de rotação. Uma câmera inclinada enxerga esse plano através de uma transformação de perspectiva `3×3` (homografia). O mapa converte cada pixel da linha diretamente em milímetros:

* `t`: distância do eixo ao longo do plano do laser (o raio desejado)

* `z`: altura acima da plataforma

Ele substitui os quatro parâmetros de `scanner_config.py`.

### COMO É MEDIDO

Um cilindro de raio `R` e altura `H`, centralizado no eixo, gera uma linha de laser cujas extremidades são pontos conhecidos:
`extremidade inferior = (t = R, z = 0)` | `extremidade superior = (t = R, z = H)`

Cada cilindro fornece 2 pontos. O mínimo são 2 cilindros (4 pontos), mas o ideal são **3 cilindros** (6 pontos), permitindo autoverificação de consistência.

### F-1 DEMONSTRAÇÃO NO PC

Arquivos necessários: `scanner_config.py`, `laser_sim.py`, `detect_line.py`, `calibrate.py`, `plane_map.py`.

Execute:

```
python plane_map.py

```

O programa gera o arquivo `camera_map.json` e verifica que o erro de ajuste entre os pontos de referência fica abaixo de `0.4 mm`.

Para testar a simulação de escaneamento completo com câmera inclinada:

```
python simulate_scan.py --tilted

```

### F-2 USANDO COM A CÂMERA REAL

1. Monte a câmera e o laser, e **NÃO OS MOVA** depois disso. Se mover a câmera, o laser ou a plataforma, refaça a calibração.

2. Tire fotos de **três cilindros** conforme descrito na Parte E (raios claramente diferentes, ex: `15 mm`, `25 mm` e `35 mm`; 8 a 12 ângulos espaçados uniformemente; mesmas configurações de câmera; pastas com arquivos `on_00` / `off_00` ...).

3. Execute:

```
python plane_map.py --cyl PASTA_A raioA alturaA --cyl PASTA_B raioB alturaB --cyl PASTA_C raioC alturaC

```

4. Se exibir `"map saved to camera_map.json"`, escaneie um objeto de tamanho **CONHECIDO** para validar as medidas. Se exibir um `WARNING` (erro acima de `0.4 mm`), verifique se a iluminação não cortou a linha do laser ou se as medidas digitadas estão corretas.

**Observações técnicas:**

* Evite lentes grande-angulares (*"Wide"*), pois distorcem linhas retas nas bordas da imagem.

## PARTE G - LIMPEZA DE UM ESCANEAMENTO (`cleanup.py`, `glitches.py`, `test_cleanup.py`)

**Objetivo:** remover pontos errados (reflexos) e preencher buracos (sombras ou fotos falhas) **ANTES** que a malha 3D seja construída.

**Problemas tratados:**

* `reflection` (reflexo): um ponto brilhante fora da linha do laser que engana o detector.

* `shadow` (sombra): parte da linha fica oculta pela geometria do objeto.

* `dead pair` (par morto): um par inteiro de fotos sem leitura válida (falha no laser, oscilação de luz, obstrução).

### COMO FUNCIONA

Os dados formam uma tabela (uma linha por ângulo de foto, uma coluna por altura, contendo o raio). Como a superfície varia suavemente entre ângulos vizinhos, qualquer célula que desvie mais de `2 mm` da mediana das 3 fotos adjacentes de cada lado é descartada (junto com 2 células acima e abaixo) e preenchida por interpolação linear entre os vizinhos válidos mais próximos.
A suavização (*smoothing*, média com vizinhos) fica **DESLIGADA** por padrão para preservar detalhes finos, mas pode ser ativada com `--smooth 1` se a superfície estiver ruidosa/áspera.

### PASSO 0 - Verifique a pasta

Arquivos necessários: `detect_line.py`, `simulate_scan.py`, `plane_map.py`, `cleanup.py`, `glitches.py`, `test_cleanup.py`.

### G-1 TESTES DE REPARO NA SIMULAÇÃO

1. **Escaneamento com falhas, sem reparo:**

```
python simulate_scan.py --glitches --glitch-kinds reflection,shadow --out messy.obj --preview messy.png

```

2. **Escaneamento com falhas e pares mortos, reparado com `--clean`:**

```
python simulate_scan.py --glitches --clean --out repaired.obj --preview repaired.png

```

3. **Relatório estatístico completo:**

```
python test_cleanup.py

```

### G-2 LIMITAÇÕES E PARÂMETROS

* Detalhes mais finos que o espaçamento entre várias fotos podem ser interpretados como picos de erro. Se mais de `2%` dos pontos forem corrigidos, um `WARNING` será exibido. Nesse caso, aumente o número de fotos por volta (`--angles`) ou aumente o limite de detecção de pico (`--spike 3.0`).

* São necessárias pelo menos 7 fotos para executar a limpeza.

* Opções no `simulate_scan.py`: `--clean`, `--spike 2.0` (limite em mm), `--smooth 1` (passadas de suavização).

## PARTE H - ESCANEANDO A PARTIR DE UMA PASTA DE FOTOS (`scan_folder.py`)

**Objetivo:** o programa principal para processar suas fotos **REAIS**. Ele detecta a altura do objeto automaticamente, extrai os perfis de cada foto, aplica a limpeza (Parte G), constrói a malha `.obj` e salva a pré-visualização.

### O QUE O PROGRAMA ESPERA

* Uma pasta contendo pares de fotos por posição da plataforma:
  `on_00.png`, `off_00.png`, `on_01.png`, `off_01.png` ... (`.png` ou `.jpg`, começando em `00` ou `01`).

* Posições **UNIFORMEMENTE** espaçadas ao longo de exatamente **UMA** volta completa (`ângulo = 360 × k ÷ N`). Para 60 fotos, uma a cada `6°`. **NÃO** tire uma foto repetida em `360°`.

* Mesmas configurações de câmera e resolução das fotos de calibração.

* A altura (`z`) é detectada automaticamente pela mediana das alturas encontradas nas fotos (a base é fixada em `z = 0`). Caso queira forçar uma faixa específica, use `--z-range MIN MAX`.

### PASSO 0 - Arquivos necessários

`mesh.py`, `viewer.py`, `scanner_config.py`, `detect_line.py`, `cleanup.py`, `scan_folder.py` (além de `plane_map.py` e `calibrate.py` se usar `--map`).

### H-1 TESTES COM FOTOS SALVAS

```
# Gera pasta com 60 pares de fotos e escaneia:
python simulate_scan.py --save-photos scan_photos
python scan_folder.py scan_photos --check-vase

# Com câmera inclinada e mapa de perspectiva:
python simulate_scan.py --tilted --save-photos tilt_photos
python scan_folder.py tilt_photos --map tilt_photos/camera_map.json --check-vase

```

### H-2 OPÇÕES DO `scan_folder.py`

* `--map ARQUIVO`: usa o mapa de perspectiva (`camera_map.json` da Parte F). Sem isso, usa `scanner_config.py` (Parte E).

* `--points 40`: pontos por fatia, de baixo para cima (maior = mais resolução vertical).

* `--z-range MIN MAX`: define a faixa de altura manualmente em mm.

* `--per-turn N`: informa o total de posições por volta caso as últimas fotos estejam faltando.

* `--no-clean`: desativa o reparo automático de falhas.

* `--spike 2.0`: limite de detecção de falhas em mm (Parte G).

* `--smooth 1`: número de passadas de suavização (padrão `0`).

* `--mirror`: espelha o modelo final (útil se o motor girar no sentido inverso).

* `--out ARQUIVO`: nome do arquivo `.obj` de saída (padrão `scan.obj`).

* `--preview ARQUIVO`: nome da imagem de pré-visualização (padrão `scan_preview.png`).

### H-3 USANDO COM FOTOS REAIS

1. Calibre usando a Parte E (`scanner_config.py`) ou Parte F (`camera_map.json`).

2. Coloque o objeto na plataforma e capture `N` pares de fotos em uma volta completa dentro de uma pasta (usando o `capture.py` da Parte I).

3. Execute:

```
python scan_folder.py PASTA --map camera_map.json

```

*(omitindo `--map` caso tenha calibrado pela Parte E).*
4. **VERIFIQUE AS MEDIDAS:** Confira se a linha `"size"` e a altura exibidas no terminal batem com a medição real feita com uma régua. Se o objeto sair espelhado, rode novamente adicionando `--mirror`.

### H-4 LIMITAÇÕES GEOMÉTRICAS

* Como o sistema registra um único raio por altura e ângulo, ele não consegue reconstruir furos passantes, cavidades internas ou alças salientes que bloqueiem o laser.

* O topo e a base da malha são sempre fechados com uma tampa plana.

* A calibração só é válida enquanto câmera, laser, plataforma e resolução da imagem permanecerem inalterados.

## PARTE I - O PI: CÂMERA, LASER E PLATAFORMA (`capture.py`, `test_capture.py`)

**Objetivo:** automatizar a captura no Raspberry Pi. O `capture.py` liga o laser, tira uma foto, desliga o laser, tira outra foto, avança a plataforma um passo e repete por uma volta completa, salvando tudo no formato exigido pelo `scan_folder.py`.

**Modos de movimentação suportados:**

* `uln2003`: motor de passo 28BYJ-48 + placa driver ULN2003 ligado diretamente aos pinos GPIO do Pi.

* `stepper`: motor de passo com driver STEP/DIR (A4988, DRV8825, etc.).

* `manual`: giro manual passo a passo guiado pelo terminal.

* `dry-run`: simulação completa no PC sem hardware.

### PASSO 0 - Arquivos necessários

Adicione `capture.py` e `test_capture.py` à pasta `scanner3d`.

### I-1 TESTE NO SEU PC (sem hardware)

```
# Simula uma captura completa e gera a malha:
python capture.py --dry-run --out dry_photos
python scan_folder.py dry_photos --check-vase

# Testa o diagnóstico de iluminação em um par de fotos:
python capture.py --dry-run --check

```

### I-2 CONFIGURAÇÃO DO HARDWARE NO RASPBERRY PI

#### 2.1 Copie a pasta para o Pi e instale as bibliotecas

Copie a pasta `scanner3d` para o Pi (via pendrive ou SCP):

```
scp -r scanner3d pi@raspberrypi.local:~/

```

No terminal do Pi, instale os pacotes do sistema (`apt`):

```
sudo apt update
sudo apt install python3-picamera2 python3-gpiozero python3-opencv python3-numpy python3-matplotlib
cd ~/scanner3d

```

#### 2.2 Conexão da câmera (Pi DESLIGADO)

* Conecte o cabo flat na porta identificada como **CAMERA** na placa (não na DISPLAY).

* Levante a trava com cuidado, insira o cabo totalmente (no Pi 4, os contatos metálicos ficam voltados para as portas HDMI) e feche a trava.

* Ligue o Pi e verifique se a câmera é reconhecida:

```
rpicam-hello --list-cameras

```

*(Em versões anteriores do sistema, use `libcamera-hello --list-cameras`).*

#### 2.3 Circuito do laser (Pi DESLIGADO)

**NUNCA** alimente o laser diretamente por um pino GPIO (limite de `8 mA` por pino). Use um transistor NPN para chavear a alimentação:

```
Pi pino 2 (5 V) -------------+---- módulo laser (+)
                             |
                     módulo laser (-)
                             |
                         coletor
Pi GPIO17 (pino 11) - 1 kohm - base     transistor NPN (2N2222,
                         emissor        BC337, BC547 ...)
                             |
Pi pino 9 (GND) -------------+

```

* Verifique a tensão do seu módulo laser (`3 V` ou `5 V`) e a pinagem do transistor escolhido.

* **SEGURANÇA:** Nunca olhe diretamente para o feixe do laser ou para reflexos em superfícies brilhantes.

* Se o módulo acionar em nível BAIXO, use `--laser-active-low`. Para outro pino GPIO, use `--laser-pin N`.

#### 2.4 Teste o laser

```
python3 capture.py --laser-test

```

O laser deve piscar 3 vezes (`1 s` ligado, `1 s` desligado).

#### 2.5A Conexão do motor 28BYJ-48 + ULN2003

Com o **Pi DESLIGADO**, conecte as quatro entradas da placa ULN2003 aos pinos padrão:

* `ULN2003 IN1` → **GPIO5** (pino 29)

* `ULN2003 IN2` → **GPIO6** (pino 31)

* `ULN2003 IN3` → **GPIO13** (pino 33)

* `ULN2003 IN4` → **GPIO19** (pino 35)

* `GND da placa ULN2003` → qualquer pino **GND** do Pi (ex: pino 30 ou 34)

Alimente os pinos `+` e `-` da placa ULN2003 com uma fonte externa de `5 V` (unindo o GND dela ao GND do Pi) para não sobrecarregar a placa. Nunca conecte outro microcontrolador simultaneamente aos mesmos pinos.

Teste uma volta completa com uma marcação na plataforma:

```
python3 capture.py --platform uln2003 --turn-test

```

O padrão são `4096` meios-passos por volta. Se a marca parar um pouco antes ou depois do ponto inicial, ajuste o valor:

```
python3 capture.py --platform uln2003 --steps-per-turn 4076 --turn-test

```

Se o motor vibrar sem girar, aumente o atraso entre passos com `--step-delay 0.004`. Para inverter o sentido, use `--reverse`.

#### 2.5B Conexão de motor com driver STEP/DIR (A4988, DRV8825)

* Conecte `STEP` ao **GPIO20** (pino 38), `DIR` ao **GPIO21** (pino 40) e opcionalmente `ENABLE` (`--enable-pin N`).

* Una o GND do driver ao GND do Pi e alimente o motor pela fonte externa dedicada.

* Calcule `--steps-per-turn = passos_por_volta × micropassos × redução` (ex: `200 × 16 = 3200`).

```
python3 capture.py --platform stepper --steps-per-turn 3200 --turn-test

```

#### 2.6 Modo manual (sem motor)

Basta executar o `capture.py` sem especificar `--platform` (o padrão é `manual`). O terminal indicará o ângulo exato para cada posição usando um disco graduado.

### I-3 AJUSTE DE EXPOSIÇÃO E FOCO

Posicione um objeto na plataforma, escureça o ambiente, alinhe a linha vertical do laser sobre o objeto e execute:

```
python3 capture.py --check

```

Abra as imagens geradas em `check_photos/` (`on_00.jpg` e `off_00.jpg`) e leia o diagnóstico no terminal:

* `NO LINE FOUND` / `line WEAK`: escureça a sala ou aumente o tempo de exposição (`--exposure-us`).

* `pixels already at full red`: a luz ambiente está estourando a imagem; diminua `--exposure-us` e bloqueie luzes externas.

* **Frequência da rede elétrica:** O padrão `--exposure-us 8333` (`1/120 s`) evita cintilação (*flicker*) de lâmpadas em redes de `60 Hz` (padrão no Brasil). Para redes de `50 Hz`, use `10000`.

* **Resolução:** O padrão é `--size 1640 1232`. Mantenha exatamente a mesma resolução para calibração e escaneamento.

**Capturando fotos de calibração (12 posições por cilindro):**

```
python3 capture.py --out calib_A --photos 12 --platform uln2003

```

### I-4 EXECUTANDO O ESCANEAMENTO REAL

```
# Com motor 28BYJ-48 (ULN2003):
python3 capture.py --out photos --platform uln2003

# Com driver STEP/DIR:
python3 capture.py --out photos --platform stepper --steps-per-turn 3200

# Manualmente:
python3 capture.py --out photos

```

Em seguida, processe a malha 3D:

```
python3 scan_folder.py photos --map camera_map.json

```

*(Pressione `Ctrl+C` a qualquer momento para interromper; o laser será desligado automaticamente).*

### I-5 PRINCIPAIS OPÇÕES DO `capture.py`

* `--out PASTA`: pasta de destino das fotos (padrão: `photos`).

* `--photos 60`: quantidade de posições em uma volta completa.

* `--format jpg|png`: formato de imagem (padrão: `jpg`).

* `--overwrite`: permite sobrescrever uma pasta existente.

* `--platform manual|stepper|uln2003`: modo de controle da plataforma.

* `--steps-per-turn N`: passos por volta completa (`4096` padrão para `uln2003`).

* `--coil-pins 5 6 13 19`: pinos BCM para IN1..IN4 (`uln2003`).

* `--step-pin 20 --dir-pin 21 --enable-pin N`: pinos BCM para `stepper`.

* `--step-delay S`: intervalo em segundos entre passos.

* `--reverse`: inverte o sentido de rotação.

* `--settle 0.7`: tempo de estabilização (segundos) após o movimento da plataforma.

* `--laser-pin 17 --laser-active-low --laser-settle 0.3`: controle do laser.

* `--size L A --exposure-us 8333 --gain 1.0`: resolução, exposição e ganho fixos da câmera.

* `--discard 2`: quadros descartados antes de salvar a foto para estabilizar o sensor.

## PARTE J - CONTROLE REMOTO VIA PC OU NAVEGADOR WEB

*(`pi_server.py`, `scanner_page.html`, `export_stl.py`, `pc_client.py`)*

**Objetivo:** controlar todo o scanner remotamente pelo navegador (PC ou celular) ou linha de comando. O Raspberry Pi executa a captura, processa o modelo 3D localmente (`scan_folder.py`) e envia o arquivo final `.obj` ou `.stl` pronto para download.

```
PC / Celular --- "iniciar, 60 fotos" ---> Pi (pi_server.py -> capture.py)
PC / Celular <-- "12 de 60 prontas" ----- Pi (atualização em tempo real)
PC / Celular <-- "criando o modelo" ----- Pi (scan_folder.py no Pi)
PC / Celular <-- model.obj / model.stl -- Pi

```

### J-1 INICIANDO O SERVIDOR NA REDE LOCAL (WI-FI)

1. Certifique-se de que o Pi e o PC/celular estejam na **MESMA** rede Wi-Fi e que todos os arquivos (`.py`, `scanner_page.html`, `export_stl.py`, `camera_map.json`) estejam na pasta `~/scanner3d` do Pi.

2. No terminal do Pi, descubra seu IP e inicie o servidor:

```
hostname -I
cd ~/scanner3d
python3 pi_server.py --token SEUTOKENLONGO

```

*(O token deve ter pelo menos 10 caracteres. Se omitido, o servidor gera um aleatório e exibe no terminal. Para testes sem hardware, adicione `--allow-dry-run`).*

### J-2 USANDO PELA PÁGINA WEB (`scanner_page.html`)

Abra no navegador do PC ou celular: `http://IP_DO_PI:8000/`

1. Digite a senha (**Token**) no campo superior.

2. **Testes prévios (cartão "Testes do equipamento"):**

   * **Testar laser:** pisca o laser 3 vezes para verificar alinhamento.

   * **Foto de teste:** captura um par ON/OFF e exibe as imagens e o diagnóstico de exposição direto na tela.

3. **Escaneamento:** Escolha o número de fotos (`60` padrão, `36` rápido) e clique em **"Iniciar scan"**. Acompanhe o progresso e, ao final, gire e inspecione a malha diretamente na caixa **"Modelo 3D"**.

4. **Downloads:** Clique em **"Baixar modelo (.obj)"**, **"Baixar .stl (impressao 3D)"** ou **"Baixar fotos"** (`.zip`).

5. **Scans anteriores:** Lista todos os escaneamentos salvos no Pi (`scans/scan_DATA_HORA/`), mostrando o espaço livre em disco e permitindo visualizar, baixar ou apagar registros antigos.

### J-3 USANDO PELO CLIENTE DE LINHA DE COMANDO (`pc_client.py`)

No terminal do seu PC, dentro da pasta `scanner3d`:

```
python pc_client.py --host 192.168.0.50 --token SEUTOKENLONGO run --photos 60 --stl

```

* **Opções adicionais:** `--platform uln2003|stepper`, `--steps-per-turn N`, `--reverse`, `--format jpg|png`, `--map camera_map.json`, `--out PASTA`, `--photos-zip`, `--dry-run`.

* **Comandos de controle:** `status`, `wait`, `stop`, `download`.

### J-4 ACESSO PELA INTERNET (CLOUDFLARE TUNNEL)

Para acessar o scanner de fora da rede local com segurança (`HTTPS`) sem abrir portas no roteador:

1. **Instale o `cloudflared` no Pi (única vez):**

```
# Para Raspberry Pi OS 64-bit (aarch64):
curl -LO https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb

```

*(Para sistemas 32-bit `armv7l`, utilize o pacote `armhf` da mesma página).*

2. **Terminal 1 no Pi (inicie o servidor escutando apenas localmente):**

```
cd ~/scanner3d
python3 pi_server.py --host 127.0.0.1 --token SEUTOKENLONGO

```

3. **Terminal 2 no Pi (abra o túnel):**

```
cloudflared tunnel --url http://localhost:8000

```

O terminal exibirá um endereço público temporário no formato `https://palavras-aleatorias.trycloudflare.com`.

4. **Acesso remoto:** Abra esse endereço `https://...` em qualquer navegador ou utilize no cliente PC:

```
python pc_client.py --url https://palavras-aleatorias.trycloudflare.com --token SEUTOKENLONGO run --photos 60

```

*(Nota: caso exista um arquivo `~/.cloudflared/config.yaml`, renomeie-o para não interferir no túnel rápido. Pressione `Ctrl+C` para encerrar o túnel quando terminar).*

## SOLUÇÃO DE PROBLEMAS (TROUBLESHOOTING)

* **`"python is not recognized"` / `"command not found"`**
  Windows: reinstale o Python marcando `"Add python.exe to PATH"`, ou use `py`. Linux / macOS: use `python3`.

* **`"No module named cv2"` / `"numpy"` / `"matplotlib"`**
  Execute: `python -m pip install numpy matplotlib opencv-python` (ou via `sudo apt install` no Raspberry Pi).

* **`"No module named scanner_config"` (ou outros módulos do projeto)**
  Verifique se todos os arquivos `.py` estão na mesma pasta e se o terminal foi aberto dentro dela.

* **O motor 28BYJ-48 vibra mas não gira**
  Aumente o atraso entre passos (`--step-delay 0.004`), confira a ordem dos fios `IN1..IN4` e verifique a fonte externa de `5 V`.

* **A câmera não é detectada no Pi**
  Desligue o Pi, reconecte o cabo flat na porta **CAMERA** verificando o lado dos contatos metálicos e teste com `rpicam-hello --list-cameras`.

## LISTA DE ARQUIVOS

| Arquivo | Parte | Descrição | 
| ----- | ----- | ----- | 
| `GUIDE_PT.md` | Geral | Este guia passo a passo | 
| `mesh.py` | Parte A | Converte fatias em malha `.obj` | 
| `viewer.py` | Parte B | Visualizador interativo de arquivos `.obj` | 
| `scanner_config.py` | Parte C | Parâmetros de calibração da câmera | 
| `laser_sim.py` | Parte C | Simulador de imagens de laser para testes no PC | 
| `detect_line.py` | Parte C | Algoritmo detector da linha do laser | 
| `test_detector.py` | Parte C | Teste automatizado de precisão do detector | 
| `try_detector.py` | Parte C-2 | Teste visual interativo do detector | 
| `simulate_scan.py` | Parte D | Simulação completa de escaneamento no PC | 
| `calibrate.py` | Parte E | Calibração para câmera alinhada sem inclinação | 
| `plane_map.py` | Parte F | Calibração de perspectiva (`camera_map.json`) para câmera inclinada | 
| `cleanup.py` | Parte G | Filtro de remoção de reflexos e preenchimento de falhas | 
| `glitches.py` | Parte G | Gerador de falhas simuladas para testes | 
| `test_cleanup.py` | Parte G | Validação do filtro de limpeza | 
| `scan_folder.py` | Parte H | Processa uma pasta de fotos reais e gera a malha 3D | 
| `test_scan_folder.py` | Parte H | Teste de detecção automática de altura | 
| `capture.py` | Parte I | Controle de câmera, laser e motor no Raspberry Pi | 
| `test_capture.py` | Parte I | Testes de lógica de captura | 
| `pi_server.py` | Parte J | Servidor web e API de controle no Raspberry Pi | 
| `scanner_page.html` | Parte J | Interface web responsiva com visualizador 3D | 
| `export_stl.py` | Parte J | Conversor de `.obj` para `.stl` binário (impressão 3D) | 
| `pc_client.py` | Parte J | Cliente de linha de comando para controle remoto | 

> **IMPORTANTE:** Mantenha apenas **uma cópia** de cada arquivo na mesma pasta (apague duplicatas como `capture (1).py`). Arquivos gerados durante o uso (`.obj`, `.stl`, `.png`, `camera_map.json`, `__pycache__`) podem ser removidos livremente quando necessário.

---
# Integrantes:
Joaquim Anderlini Alves da Cunha - 22.00536-6

Gabriel Giardino Sprotte - 23.00964-0

Gabriel Fernandes Sabino - 23.01062-2

Guilherme Gonsales de Sá - 23.00882-2

Thiago Espigado Miras - 22.01836-0

### Créditos:
Drivers para o display OLED: https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/display/ssd1306/ssd1306.py
