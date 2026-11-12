# SCANNER 3D A LASER - GUIA PASSO A PASSO

**Última atualização:** 08/11/2026

**Status:** As Partes de A a J estão prontas (malha, visualizador, detecção da linha do laser, teste prático da detecção, escaneamento simulado completo, assistente de calibração, mapa de perspectiva para câmera inclinada, limpeza de fotos ruins, escaneamento a partir de uma pasta de fotos, captura de fotos com o Pi, o PC enviando a ordem para o Pi).

Tudo até a Parte H foi testado em fotos falsas (simuladas); o código da câmera, laser e motor da Parte I **NÃO** pôde ser testado em hardware real (a Parte J foi testada apenas em um único computador, não em uma rede real).

O que vem a seguir está listado na Parte K. Novas partes serão adicionadas no final.

> **Nota:** Tudo neste guia roda no seu PC. Você ainda **NÃO** precisa do Raspberry Pi, da câmera ou do laser.

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

```bash
python -m pip install numpy matplotlib opencv-python
```

Aguarde até terminar sem mensagens de erro em vermelho.

* `numpy`: matemática em matrizes (arrays) de números
* `matplotlib`: desenho da pré-visualização 3D
* `opencv-python`: processamento de imagem (usado a partir da Parte C)

**Apenas Linux / Raspberry Pi OS:** se o pip disser `externally-managed-environment`, instale os pacotes do sistema em vez disso:

```bash
sudo apt install python3-numpy python3-matplotlib python3-opencv
```

### 1.3 Crie a pasta do projeto

Crie uma pasta chamada `scanner3d` em algum lugar fácil, por exemplo, dentro de `Documentos` (`Documents`). Cada arquivo que eu enviar vai **DENTRO DESTA PASTA**, todos no mesmo lugar (sem subpastas). Os programas encontram uns aos outros porque ficam lado a lado.

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

```bash
python mesh.py
```

### VOCÊ DEVE VER no terminal:

```text
1202 vertices, 2400 faces
closed mesh: True
signed volume: 81861.2 (outward)
```

e um novo arquivo `fake_vase.obj` aparecerá na pasta.

* `closed mesh: True` = sem buracos.
* `outward` = as faces apontam para fora. Se você vir `INSIDE-OUT`, a ordem das faces está errada (virada do avesso).

### COMO FUNCIONA:

1. Cada ponto é $(r, z)$ em algum ângulo $\theta$.

$$
x = r \cdot \cos(\theta), \quad y = r \cdot \sin(\theta), \quad z = z
$$

2. Fatias vizinhas são unidas com triângulos (a última fatia se junta de volta à primeira, fechando a superfície ao redor).
3. O topo e a base recebem uma tampa plana feita de triângulos em formato de leque a partir de um ponto no eixo central.
4. O arquivo `.obj` é texto puro: linhas `v x y z` são pontos (vértices), linhas `f a b c` são triângulos (faces) que usam os números dos pontos (contando a partir de 1).

### ALTERE:

A função `fake_scan()` perto do topo de `mesh.py` constrói o vaso falso. Altere os números nela (`num_angles`, `num_heights`, a fórmula do raio) e execute novamente.

`build_mesh(slices, scale=1.0)`: `scale` converterá mais tarde pixels em milímetros para escaneamentos reais.

## PARTE B - O VISUALIZADOR (`viewer.py`)

**O que ele faz:** desenha qualquer arquivo `.obj` para que você possa vê-lo.

* **ARQUIVOS:** `viewer.py`
* **COMO EXECUTAR:**

```bash
python viewer.py fake_vase.obj
```

Uma janela se abre. Segure o botão esquerdo do mouse e arraste para girar.

*Sem janela / erro de exibição?* Salve uma imagem em vez disso:

```bash
python viewer.py fake_vase.obj --save preview.png
```

e depois abra o arquivo `preview.png`.

### VOCÊ DEVE VER:

Um vaso azul com uma cintura fina e três lóbulos suaves.

### ALTERE:

`--elev 40 --azim 30` muda o ângulo de visão, ex.:

```bash
python viewer.py fake_vase.obj --save top.png --elev 80
```

> **Dica:** MeshLab (gratuito) ou Blender (gratuito) mostram arquivos `.obj` com mais recursos. Ambos abrem `fake_vase.obj` diretamente.

## PARTE C - ENCONTRANDO A LINHA DO LASER EM UMA FOTO

**O que ela faz:** pega quadros (*frames*) da câmera e encontra onde a linha do laser está em cada linha horizontal da imagem, depois converte pixels em milímetros. O resultado é a lista de pontos `(raio r, altura z)` por ângulo que a Parte A precisa.

Neste momento, as "fotos" são **FALSAS**: `laser_sim.py` as desenha (uma linha de laser no vaso, um brilho quente de lâmpada e ruído da câmera). Como sabemos a forma verdadeira, podemos medir o quão errado o detector está. Com a câmera real, você usará fotos reais e o mesmo detector.

* **ARQUIVOS (4 novos, na mesma pasta de antes):**
  * `scanner_config.py`: os números que descrevem a configuração da câmera
  * `laser_sim.py`: desenha as fotos falsas
  * `detect_line.py`: **O DETECTOR** (este é o código que você vai manter)
  * `test_detector.py`: executa o detector em fotos falsas e verifica erros

* **COMO EXECUTAR:**

```bash
python test_detector.py
```

*(Este é automático: ele apenas imprime números e salva uma imagem. Para uma versão prática onde você muda as coisas e vê o que acontece, vá para a **PARTE C-2** logo após esta parte.)*

### VOCÊ DEVE VER (os dígitos podem variar um pouco, mas o padrão não):

```text
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

Um pixel de imagem equivale a cerca de $0.24\text{ mm}$ de raio nesta configuração $\left(\frac{1}{6\text{ pixels por mm} \times 0.707}\right)$. Erros muito abaixo disso significam que o passo de sub-pixel funciona. $0.01\text{ mm}$ **NÃO** é o que uma câmera real vai lhe dar: as fotos falsas têm apenas ruído simples, nenhuma das imperfeições do mundo real. O objetivo deste teste é provar que "a lógica está certa", e não que "o scanner é tão preciso assim".

### COMO FUNCIONA (os passos dentro de `detect_line.py`):

1. **Subtração de fundo (`laser_signal`):** Duas fotos por ângulo da plataforma: laser LIGADO (ON) e laser DESLIGADO (OFF). Subtraia o canal vermelho. Qualquer coisa que não seja o laser (lâmpada, janela, tela) está em ambas as fotos e se cancela.
2. **Sub-pixel (`find_line_columns`):** Em cada linha horizontal da imagem, pegue o pixel mais brilhante e faça a média dos pixels vizinhos ponderada pelo brilho. Isso dá a posição da linha com precisão maior que um pixel. Linhas sem laser são ignoradas.
3. **Filtro (`reject_outliers`):** Descarte detecções que saltam para longe de seus vizinhos.
4. **Pixels para milímetros (`columns_to_profile`):**

$$
z = \frac{\text{BASE\_ROW} - \text{row}}{\text{PX\_PER\_MM}}
$$

$$
r = \frac{\text{column} - \text{AXIS\_COL}}{\text{PX\_PER\_MM} \cdot \sin(\alpha)}
$$

   *Por que* $\sin(\alpha)$*:* a câmera olha para o corte do laser de lado, no ângulo $\alpha$ (`ALPHA`). Um ponto a $r\text{ mm}$ do eixo só se desloca $r \cdot \sin(\alpha)$ lateralmente na imagem. A $45^\circ$, isso é $0.707$.

5. **Reamostragem (`resample`):** Escolha um número fixo de alturas igualmente espaçadas, para que cada fatia tenha o mesmo número de pontos, como `mesh.py` exige.

### O QUE O TESTE MOSTROU:

* Ambos os métodos funcionam nessas fotos falsas, mas `ON-menos-OFF` tem cerca de 2 a 4 vezes menos erro e seu limiar (`min_signal = 40`) é fácil de escolher, porque a luz parasita já foi removida.
* O "jeito do artigo" (uma foto, manter apenas pixels acima de um limiar vermelho) funcionou aqui com 180, 235 e 250, mas apenas porque esta lâmpada falsa não é muito brilhante. Você tem que ajustar esse número manualmente, e ele precisará ser reajustado sempre que a luz da sala mudar.
* Limite do `ON-menos-OFF` (segue diretamente da matemática, não medido aqui): se a luz ambiente for tão forte que a câmera mostre branco puro (255) em **AMBAS** as fotos, a diferença ali será zero e a linha do laser ficará invisível. Não aponte a câmera para uma lâmpada forte ou janela, e diminua a exposição da câmera.

### ALTERE (experimentos, depois execute `python test_detector.py` novamente):

* `scanner_config.py`: `PX_PER_MM`, `ALPHA_DEG` ... (veja "câmera real" abaixo)
* `laser_sim.py`: em `render_frame()`, tente `noise_sigma=3.0`, `lamp=False`, `line_sigma=1.6` (linha mais grossa). Eu tentei `noise_sigma` 10 e 25 com ON-menos-OFF: erro médio de $0.018\text{ mm}$ e $0.035\text{ mm}$. O detector lida bem com ruído.
* `test_detector.py`: `NUM_ANGLES` (mais ângulos = escaneamento mais fino), `NUM_POINTS` (pontos por fatia)

### O QUE ISSO SIGNIFICA PARA A CÂMERA REAL:

Os quatro números em `scanner_config.py` são valores de **CALIBRAÇÃO**. Com o scanner real, você os mede em vez de inventá-los. *(A Parte E tem um programa auxiliar que os mede a partir de fotos. A lista abaixo é o método manual.)*

* `AXIS_COL`: coluna da imagem correspondente ao eixo de rotação da plataforma. Coloque uma haste fina e reta exatamente no meio da plataforma e leia sua coluna em uma foto. Gire a plataforma $180^\circ$: a haste deve permanecer na mesma coluna.
* `BASE_ROW`: linha horizontal da imagem onde o laser encontra a superfície da plataforma (laser ligado, plataforma vazia).
* `PX_PER_MM`: fotografe um objeto de altura conhecida (ex: um bloco de $50\text{ mm}$), meça sua altura em pixels e divida os pixels pelos milímetros.
* `ALPHA_DEG`: ângulo entre o plano do laser e a direção da câmera. Meça no suporte com um transferidor e depois refine com um bloco de tamanho conhecido: altere `ALPHA_DEG` até que o raio medido bata com o do bloco.

**Simplificações na configuração falsa que a real não tem:**

* A câmera real fica acima da plataforma e vê a cena inclinada. O artigo corrige isso com uma "transformação de perspectiva" (trapézio para retângulo). A Parte F cuida disso.
* Partes do objeto podem esconder a linha do laser da visão da câmera (amassados, cantos vivos). Essas áreas ficarão faltando ou incorretas. Mesma limitação do artigo.
* Direção de rotação: se a plataforma girar para o lado oposto ao que `mesh.py` assume, a malha final parecerá espelhada. Correção: inverta a lista de fatias antes de construir a malha:

```python
slices = slices[::-1]
vertices, faces = build_mesh(slices)
```

*(NÃO corrija isso invertendo o sinal de* $y$*: isso vira a malha do avesso. Eu testei: a verificação de volume fica negativa.)*

## PARTE C-2 - TESTE PRÁTICO DO DETECTOR DE LINHA (`try_detector.py`)

**Objetivo:** ver o detector funcionando em UMA foto, mudar parâmetros e ver o que acontece. Mesma ideia de mudar os números do vaso na Parte A.

### PASSO 0 - Verifique a pasta

Sua pasta `scanner3d` deve conter estes arquivos, lado a lado:
`scanner_config.py`, `laser_sim.py`, `detect_line.py`, `try_detector.py`.

Abra um terminal dentro da pasta (seção 1.5). Digite `dir` (Windows) ou `ls` (Linux / macOS) e verifique se `try_detector.py` está na lista.

### PASSO 1 - Execute sem opções

Digite:

```bash
python try_detector.py
```

*(Linux / macOS: `python3 try_detector.py`)*

Após um ou dois segundos, você deve ver isto (mesmos números ou muito próximos):

```text
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

**Como ler a tabela, coluna por coluna:**

* `height z`: altura no vaso, em mm
* `true r`: o raio real do vaso falso naquela altura
* `detected r`: o raio que o detector mediu a partir da foto
* `error`: detectado menos real. Próximo de 0 é bom.

*(A tabela mostra apenas cada 5º ponto, para mantê-la curta.)*

### PASSO 2 - Abra a imagem

Um novo arquivo `try_result.png` apareceu na pasta. Abra-o:

* **Windows:** dê um duplo clique nele no Explorador de Arquivos
* **macOS:** digite `open try_result.png`
* **Linux:** dê um duplo clique, ou digite `xdg-open try_result.png`

Ela tem seis áreas:

1. **laser ON:** a foto com a linha do laser (brilho laranja = lâmpada)
2. **laser OFF:** a mesma cena com o laser desligado
3. **ON minus OFF:** resta apenas o laser, a lâmpada sumiu
4. **green dots:** onde o detector achou a linha, sobreposto à foto 1
5. **graph:** curva PRETA = a forma verdadeira do vaso, pontos VERDES = o que o detector mediu
6. **text:** o veredito (`GOOD` / `BAD`) e o erro médio

**A PARTE DE DETECÇÃO DE LINHA FUNCIONA QUANDO TODOS OS TRÊS SÃO VERDADEIROS:**

* os pontos verdes na área 4 ficam exatamente sobre a linha do laser
* os pontos verdes na área 5 ficam sobre a curva preta
* o texto diz `GOOD` (BOM)

A imagem é sobrescrita toda vez que você executa o script. Para guardar uma, adicione um nome:

```bash
python try_detector.py --out minha_imagem.png
```

### PASSO 3 - Experimentos (um de cada vez, abra a imagem após cada um)

Digite cada comando, pressione Enter, olhe a tabela e a imagem. Os resultados abaixo são os que eu obtive; os seus devem bater.

* **Mudando o ângulo:**

```bash
python try_detector.py --angle 60
```

  *Resultado:* `GOOD`, erro médio $0.011\text{ mm}$. Olhe para a área 5: a curva preta está mais fina do que antes (raio máximo cerca de $24\text{ mm}$ em vez de $32\text{ mm}$). O vaso não é redondo: ele tem 3 lóbulos, então parece mais largo de alguns ângulos e mais fino de outros.

* **Aumentando o ruído:**

```bash
python try_detector.py --noise 25
```

  *Resultado:* `GOOD`, erro médio $0.043\text{ mm}$. As áreas 1-3 parecem granuladas, como uma câmera ruim no escuro. O detector ainda encontra a linha. Na área 4 você pode ver alguns pontos verdes perdidos longe da linha (um acima, um abaixo). São falsas detecções em linhas horizontais onde não há laser. Eles ficam fora da altura do vaso, então não têm quase nenhum efeito no resultado.

* **Ruído extremo:**

```bash
python try_detector.py --noise 80
```

  *Resultado:* `GOOD`, erro médio $0.141\text{ mm}$. Extremamente granulado, e ainda com menos de um pixel de erro. Fotos reais têm outros problemas além do ruído, então não espere essa precisão na máquina real.

* **Sem lâmpada ambiente:**

```bash
python try_detector.py --no-lamp
```

  *Resultado:* `GOOD`, erro médio $0.009\text{ mm}$. A área 1 não tem brilho laranja. Ligeiramente melhor do que com a lâmpada.

* **Laser mais fraco:**

```bash
python try_detector.py --laser-peak 80
```

  *Resultado:* `GOOD`, erro médio $0.012\text{ mm}$. Área 1: a linha está fraca, mas ainda é encontrada.

* **Laser muito fraco (falha e ajuste):**

```bash
python try_detector.py --laser-peak 30
```

  *Resultado:* `"NO LASER LINE FOUND in this frame"` (Nenhuma linha de laser encontrada neste quadro), a área 5 diz `"nothing detected"` (nada detectado).

  *Por quê:* o detector ignora qualquer coisa mais escura que um limite chamado `min_signal` (definido como 40). Um laser tão fraco fica abaixo do limite.

  *Como corrigir isso (e este é o tipo de ajuste que você fará com o laser real):*

  1. Abra `detect_line.py` no seu editor.
  2. Encontre esta linha:

```python
def find_line_columns(signal, min_signal=40.0, half_window=5):
```

  3. Mude `40.0` para `15.0` e salve o arquivo.
  4. Execute `python try_detector.py --laser-peak 30` novamente. A linha agora é encontrada (no meu teste: erro médio $0.021\text{ mm}$).
  5. Não diminua demais: com `min_signal` em 8, o detector começa a marcar linhas vazias como "linha de laser" (cerca de 2 linhas erradas por foto no meu teste).
  6. Quando terminar, volte o valor para `40.0`.

* **Erro de calibração no eixo:**

```bash
python try_detector.py --axis-error 10
```

  *Resultado:* `BAD`, erro médio $2.359\text{ mm}$. Olhe para a área 5: os pontos verdes têm a FORMA certa, mas ficam cerca de $2.4\text{ mm}$ à esquerda da curva preta. As áreas 1-4 parecem exatamente iguais à execução normal. A foto e a detecção estão ótimas, mas esta opção finge que você mediu a posição do eixo (`AXIS_COL`) errado por 10 pixels.

  *Lição:* um detector perfeito não consegue consertar uma calibração errada. É por isso que a etapa de calibração na máquina real é tão importante.

* **Combinando opções livremente:**

```bash
python try_detector.py --angle 120 --noise 20 --no-lamp --out meu_teste.png
```

  *(meu resultado: `GOOD`, erro médio* $0.023\text{ mm}$*)*

### PASSO 4 - Altere um número no arquivo de configuração

Isto mostra o que o ângulo entre a câmera e o laser faz.

1. Abra `scanner_config.py` no seu editor.
2. Encontre a linha `ALPHA_DEG = 45.0` e mude `45.0` para `30.0`. Salve.
3. Execute `python try_detector.py`.

*Resultado:* `GOOD`, erro médio $0.014\text{ mm}$, e o texto agora diz `"one image pixel = 0.33 mm"` em vez de `0.24 mm`.

*O que isso significa:* com um ângulo menor, a linha do laser se move menos lateralmente na foto para o mesmo raio, então cada pixel representa mais milímetros: o escaneamento fica mais grosseiro (menos resolução). Um ângulo maior (cerca de $45^\circ$) dá detalhes mais finos, mas esconde mais partes do objeto da visão da câmera. $45^\circ$ é a escolha do artigo.

Volte para `45.0` e salve quando terminar.

### PASSO 5 - Se algo der errado

* `"No module named ..."`: veja **SOLUÇÃO DE PROBLEMAS** no final deste guia.
* `"unrecognized arguments"`: você digitou uma opção errada. Opções começam com dois traços e são em letras minúsculas, ex: `--no-lamp` e não `-no-lamp`.
* *Nada acontece / sem imagem*: certifique-se de que o terminal está **DENTRO** da pasta `scanner3d` (seção 1.5).

## PARTE D - O ESCANEAMENTO SIMULADO COMPLETO (`simulate_scan.py`)

**Objetivo:** rodar toda a cadeia de uma só vez, da maneira que o scanner real funcionará:

`objeto falso -> fotos em cada ângulo (laser on + off) -> detector -> fatias -> malha (.obj) -> imagem`

Apenas as fotos são falsas. Tudo depois delas é o código que você continuará usando com a câmera real.

### PASSO 0 - Verifique a pasta

Estes seis arquivos devem estar lado a lado em `scanner3d`:
`mesh.py`, `viewer.py`, `scanner_config.py`, `laser_sim.py`, `detect_line.py`, `simulate_scan.py` *(este é o novo)*. Abra um terminal dentro da pasta (seção 1.5).

### PASSO 1 - Execute

```bash
python simulate_scan.py
```

*(Linux / macOS: `python3 simulate_scan.py`)*

Uma linha vai contando enquanto trabalha: `"scanning: photo pair 1 of 60"` ...

Depois você deve ver (o tempo depende do seu PC; o resto deve bater ou ficar muito próximo):

```text
scan took 3.7 s

mesh: 2402 vertices, 4800 faces -> scan.obj
closed mesh: True, outward
volume  scanned 82,114 mm3   true 82,125 mm3   difference -0.01 %
distance between scanned and true surface: mean 0.009 mm, worst 0.101 mm
picture: scan_preview.png
```

**O que cada linha significa:**

* `60 photo pairs`: a plataforma "gira" em 60 passos; em cada passo tira uma foto com o laser ligado e uma com ele desligado
* `closed mesh: True`: sem buracos na superfície
* `outward`: os triângulos apontam para fora (não estão do avesso)
* `volume`: tamanho do objeto escaneado vs. o falso verdadeiro
* `distance`: quão distante a superfície escaneada está da verdadeira, em milímetros, sobre todos os 2402 pontos

Novos arquivos na pasta: `scan.obj` (o modelo 3D escaneado) e `scan_preview.png` (uma imagem dele).

### PASSO 2 - Olhe o resultado

Abra `scan_preview.png`. Você deve ver o mesmo vaso da Parte B: cintura fina, três lóbulos suaves. Essa é a prova de que a cadeia funciona: a forma emergiu a partir de nada além de fotos de laser.

Você também pode girá-lo:

```bash
python viewer.py scan.obj
```

Pequenos triângulos escuros perto da borda superior são uma peculiaridade de desenho do visualizador simples (ele ordena as faces apenas de forma aproximada). A malha em si passou na verificação `closed/outward` acima. O MeshLab ou o Blender geralmente a desenham sem esse defeito visual.

### PASSO 3 - Experimentos (abra `scan_preview.png` após cada um)

Os resultados abaixo são os que eu obtive; os seus devem bater.

* **Poucos ângulos (12):**

```bash
python simulate_scan.py --angles 12
```

  Rápido (0.7 s na minha máquina). Distância média $0.009\text{ mm}$, ainda minúscula. **MAS** olhe para a imagem: o vaso agora tem lados planos visíveis, como uma coluna de 12 lados. Menos fotos = uma superfície mais facetada.

* **Muito poucos ângulos (6):**

```bash
python simulate_scan.py --angles 6
```

  Parece uma forma de seis lados. O volume cai para $65,790\text{ mm}^3$, contra $82,114\text{ mm}^3$ com 60 fotos.

  **IMPORTANTE:** a linha `"difference"` no terminal ainda parece boa, porque ela compara com uma malha verdadeira feita com os mesmos 6 ângulos. Ela mede apenas os erros do detector, não a perda por ter poucas fotos. Para ver essa perda, compare os números de volume e as imagens entre as execuções. Regra geral: mais ângulos = objeto mais suave, porém um escaneamento mais longo (o padrão do artigo de 20 fotos é o modo rápido; contagens maiores são o modo detalhado).

* **Com ruído:**

```bash
python simulate_scan.py --noise 25
```

  Distância média $0.035\text{ mm}$, pior caso $0.201\text{ mm}$. A imagem parece idêntica à normal.

* **Com erro de eixo:**

```bash
python simulate_scan.py --axis-error 10
```

  Volume $65,422\text{ mm}^3$ vs. $82,125\text{ mm}^3$ verdadeiro: $20.34\%$ menor. Distância média $2.357\text{ mm}$.

  A imagem mostra um vaso limpo e suave, apenas visivelmente mais fino. **NADA** na imagem diz que está errado. Um escaneamento mal calibrado parece perfeito.

  *Lição para a máquina real:* escaneie algo de tamanho **CONHECIDO** primeiro (por exemplo, um bloco de $50\text{ mm}$) e verifique os números antes de confiar em qualquer escaneamento.

* **Combinando opções e salvando com outro nome:**

```bash
python simulate_scan.py --angles 30 --noise 15 --out medio.obj --preview medio.png
```

### PASSO 4 - O que você tem agora

Esta é a cadeia de software do scanner real, com as fotos simuladas. Quando o Pi, a câmera e o laser estiverem funcionando, a única parte que muda é de onde vêm as fotos: em vez de `render_frame()` do `laser_sim.py`, o programa tirará uma foto com a câmera (laser ligado, depois laser desligado) após girar a plataforma um passo. O detector, a malha e o visualizador permanecem como estão.

A Parte H faz a metade da leitura: `scan_folder.py` transforma uma pasta de pares de fotos em uma malha.

### PASSO 5 - Se algo der errado

* `"No laser line found at angle ..."`: o detector não encontrou nada em uma foto. Veja a Parte C-2 (o experimento `--laser-peak 30`). A Parte G mostra como pular esse par de fotos e reparar o buraco (`--clean`).
* `"viewer.py not found in this folder, so no picture was made"`: coloque `viewer.py` na mesma pasta que `simulate_scan.py`. O escaneamento em si funcionou e `scan.obj` foi criado.
* `"No module named mesh"` (ou outro módulo): um arquivo está faltando na pasta. Verifique a lista no PASSO 0.

## PARTE E - O ASSISTENTE DE CALIBRAÇÃO (`calibrate.py`)

**Objetivo:** medir os quatro números da câmera em vez de adivinhá-los:

* `PX_PER_MM`: quantos pixels um milímetro ocupa na foto
* `BASE_ROW`: linha da imagem onde fica a superfície da plataforma
* `AXIS_COL`: coluna da imagem onde fica o eixo de rotação da plataforma
* `ALPHA_DEG`: ângulo entre o plano do laser e a visão da câmera

A Parte C-2 mostrou o porquê: com `AXIS_COL` errado por apenas 10 pixels, o escaneamento saiu $2.4\text{ mm}$ mais fino e ainda parecia perfeitamente bom. Este assistente mede todos os quatro números a partir de fotos de dois cilindros comuns.

### COMO FUNCIONA

Um cilindro reto (uma lata, um pote) em pé na plataforma faz uma linha de laser **VERTICAL** e reta na foto.

* $\text{altura da linha em pixels} / \text{altura real em mm} \rightarrow \text{PX\_PER\_MM}$
* $\text{extremidade inferior da linha} \rightarrow \text{BASE\_ROW}$
* $\text{coluna da linha} = \text{AXIS\_COL} + \text{raio} \times \text{PX\_PER\_MM} \times \sin(\alpha)$

Um cilindro dá uma coluna dessas. Um segundo cilindro com um raio diferente dá uma segunda coluna, e duas colunas são suficientes para resolver **TANTO** `AXIS_COL` **QUANTO** `ALPHA_DEG`. As fotos são tiradas em vários ângulos ao redor e é feita a média, de modo que não importa se o cilindro ficar um pouco fora do centro (o assistente até diz o quão fora do centro ele estava).

Se os dois cilindros discordarem sobre `PX_PER_MM`, uma das linhas foi cortada e o assistente se recusa a dar os números.

### E-1 TESTE COM FOTOS FALSAS (sem hardware)

Arquivos necessários na pasta (apenas estes quatro):
`scanner_config.py`, `laser_sim.py`, `detect_line.py`, `calibrate.py`.

> **IMPORTANTE:** `laser_sim.py` foi **ATUALIZADO** (novas configurações opcionais). Substitua o seu `laser_sim.py` antigo pelo novo. Tudo o que você executou antes dá exatamente os mesmos resultados com ele.

Execute:

```bash
python calibrate.py
```

Você deve ver (em alguns segundos):

```text
Calibration from 2 fake cylinders (12 photo pairs each, normal lamp)

  number       secret true value   measured    error
  PX_PER_MM                5.700       5.726    +0.026
  BASE_ROW                 437.0       438.0    +1.000
  AXIS_COL                331.40      331.14    -0.256
  ALPHA_DEG                41.00       40.87    -0.132

  cylinder A: really placed 1.5 mm off-center, estimated 1.5 mm
  cylinder B: really placed 1.0 mm off-center, estimated 1.0 mm

Paste into scanner_config.py:

PX_PER_MM = 5.726
AXIS_COL = 331.14
BASE_ROW = 438
ALPHA_DEG = 40.87

Check: scan a third cylinder (radius 30 mm) and measure it
  with default numbers: measured radius  29.13 mm  (error -0.87 mm)
  with calibrated     : measured radius  30.01 mm  (error +0.01 mm)
```

**Como ler isso:**
O programa inventa uma câmera fictícia com números OCULTOS (a coluna `"secret true value"`). Ele tira fotos falsas de dois cilindros (raio de $25\text{ mm}$ e $35\text{ mm}$), e o assistente vê apenas as fotos. `"measured"` é o que ele calculou. `"error"` é o medido menos o secreto. Em uma máquina real não há coluna secreta: você só obtém os números medidos.

A verificação no final é o hábito importante: escanear um **TERCEIRO** objeto de tamanho conhecido. Com os números padrão, o raio erra por $0.87\text{ mm}$; com os números calibrados, erra por $0.01\text{ mm}$.

> **NÃO** cole esses números de demonstração no seu `scanner_config.py`. Eles pertencem à câmera fictícia. Colar é apenas para números medidos a partir de fotos **REAIS**.

### E-2 EXPERIMENTOS

* **Salvando as fotos falsas:**

```bash
python calibrate.py --save-photos
```

  Mesma execução, mas também grava as fotos falsas em duas pastas, `calib_A` e `calib_B` (24 imagens cada). Abra `on_00.png` e `off_00.png` em uma delas: a foto `on` tem uma linha de laser vertical reta, a foto `off` não tem.

* **Lendo das pastas salvas:**

```bash
python calibrate.py --cyl calib_A 25 50 --cyl calib_B 35 45
```

  Mede a partir dos **ARQUIVOS DE FOTO** em vez de criar fotos falsas na hora. Você obtém os mesmos números de antes. É exatamente assim que você usará fotos reais: uma pasta por cilindro, e após cada `--cyl` seu raio em mm e sua altura em mm. ($A = 25\text{ mm}$ de raio, $50\text{ mm}$ de altura; $B = 35\text{ mm}$ de raio, $45\text{ mm}$ de altura.)

* **Simulando lâmpada muito forte (erro de saturação):**

```bash
python calibrate.py --strong-lamp
```

  Mesma demonstração, mas com uma lâmpada tão forte que a câmera satura (branco puro) próximo à linha do laser. Resultado: `PX_PER_MM` medido como $5.016$ em vez de $5.700$, `ALPHA_DEG` $48.4$ em vez de $41.0$, e o assistente imprime:

```text
WARNING: The cylinders give different PX_PER_MM (5.72 and 4.31).
They should agree. One line is probably cut off at the top or
bottom ... Lower the camera exposure or dim the room light, retake
the photos, and check that the heights you typed are right.
No numbers to paste: fix the problem above and run again.
```

  *Por quê:* onde a lâmpada é forte, `ON menos OFF` é quase zero (o limite descrito na Parte C), então parte da linha do laser desaparece, a linha parece mais curta e a escala sai errada. Isso não é apenas teoria: aconteceu comigo enquanto construía este assistente, e a primeira versão não detectou o problema. É por isso que essa verificação existe.

  *Lição para a máquina real:* mantenha a exposição da câmera **BAIXA** e a sala escura enquanto tira as fotos.

* **Simulando erro de digitação:**

```bash
python calibrate.py --cyl calib_A 25 50 --cyl calib_B 35 60
```

  Aqui eu digitei a altura do cilindro B errada (60 em vez de 45). O assistente pega isso também: `"The cylinders give different PX_PER_MM (5.74 and 4.28)"`. Portanto, a mesma verificação também protege você contra erros de digitação nas suas medidas.

* **Usando apenas um cilindro:**

```bash
python calibrate.py --cyl calib_A 25 50
```

  Apenas UM cilindro. Ele ainda imprime os números, mas `ALPHA_DEG` é marcado como `"assumed, not measured"` (assumido, não medido — ele apenas usa 45) e `AXIS_COL` sai $323.33$ em vez de $331.4$. Isso só é confiável para objetos aproximadamente tão largos quanto aquele cilindro. Use dois cilindros.

### E-3 QUÃO PRECISO ELE É? (medido em 30 câmeras fictícias aleatórias, fotos falsas)

* `PX_PER_MM`: dentro de $0.8\%$
* `AXIS_COL`: dentro de $1.2\text{ pixels}$
* `ALPHA_DEG`: dentro de $0.7^\circ$
* `BASE_ROW`: sempre 1 pixel mais alto (o final da linha é borrado em cerca de um pixel). 1 pixel equivale a cerca de $0.17\text{ mm}$ de altura.
* *Verificação do terceiro cilindro (raio de* $15\text{ mm}$*):* pior erro de $0.18\text{ mm}$ com dois cilindros. Com apenas UM cilindro e os $45^\circ$ assumidos, o pior erro foi de $2.64\text{ mm}$.
* O aviso nunca disparou quando não devia (0 de 30).
* Fotos reais serão menos precisas do que essas fotos falsas.

### E-4 USANDO COM A CÂMERA REAL (mais tarde)

1. Dois cilindros com lados verticais retos e vista circular de cima (latas, potes, um pedaço de cano). Raios claramente diferentes, com pelo menos $3\text{ mm}$ de diferença ($25\text{ mm}$ e $35\text{ mm}$ funcionaram bem; quanto maior a diferença, melhor). Cores claras e foscas funcionam melhor; objetos brilhantes, escuros ou transparentes escaneiam mal.
2. Meça cada raio (diâmetro dividido por 2) e altura com uma régua ou paquímetro.
3. Coloque um cilindro aproximadamente no meio da plataforma. Tire pares de fotos (laser ligado, laser desligado) em 8 a 12 ângulos espaçados **UNIFORMEMENTE** ao redor de uma volta completa (pelo menos 3). Mesmas configurações de câmera para todas.
4. Salve-as em uma pasta chamada, por exemplo, `calib_A` como `on_00`, `off_00`, `on_01`, `off_01` ... (`.png` ou `.jpg`). Repita para o segundo cilindro em `calib_B`. *(Parte I: `capture.py --out calib_A --photos 12` faz isso.)*
5. Execute:

```bash
python calibrate.py --cyl calib_A <raio> <altura> --cyl calib_B <raio> <altura>
```

6. Se ele imprimir os números, abra `scanner_config.py` e substitua os valores antigos de `PX_PER_MM`, `AXIS_COL`, `BASE_ROW` e `ALPHA_DEG` pelos impressos (mantenha os comentários). Deixe `IMG_W` e `IMG_H` em paz: apenas o simulador de fotos falsas os utiliza.
7. Escaneie um terceiro objeto de tamanho conhecido e verifique o tamanho medido (Parte H, `scan_folder.py`, escaneia uma pasta de fotos).

> **Atenção:** Ainda não testado com fotos reais. O assistente assume que a câmera olha para o plano do laser de lado, sem nenhuma inclinação. **COMO SABER:** nas suas fotos de um cilindro reto, a linha do laser deve parecer **VERTICAL**. Se parecer inclinada (câmera acima ou muito perto do objeto), este assistente não é suficiente: use a **Parte F** em vez disso.

### E-5 SE ALGO DER ERRADO

* `"Need at least 3 on_/off_ pairs in 'folder'"`: a pasta tem poucos pares de fotos, ou os nomes não começam com `on_` e `off_`.
* `"Could not read on_xx.png and its partner off_xx.png"`: uma foto está faltando: cada `on_NN` precisa de um `off_NN` com o mesmo número.
* `"laser line not found in one of the photos"`: veja Parte C-2 (laser fraco).

## PARTE F - O MAPA DE PERSPECTIVA (`plane_map.py`)

**Objetivo:** fazer o scanner funcionar com uma câmera que olha para o laser com inclinação (montada acima ou perto do objeto), que é o que a câmera real provavelmente fará. A câmera é **FIXA**, então isso é medido **UMA VEZ** e salvo em um arquivo, `camera_map.json`.

### DE QUAL EU PRECISO, PARTE E OU PARTE F?

Olhe para uma foto de um cilindro reto com o laser ligado:

* A linha do laser parece **VERTICAL** $\rightarrow$ A Parte E (`calibrate.py`) é suficiente.
* A linha do laser parece **INCLINADA** $\rightarrow$ Use a Parte F.

Na dúvida, use a Parte F. Nos meus testes, ela funcionou igualmente bem sem inclinação alguma, e continuou funcionando em todas as inclinações que tentei (veja F-3).

### POR QUE É NECESSÁRIO

O laser cria uma "folha" plana vertical de luz passando pelo eixo de rotação. Uma câmera olhando para uma folha plana sempre a vê através de um "mapa de perspectiva" $3 \times 3$ (uma homografia). Com uma inclinação, a folha parece espremida e inclinada, e as partes que estão mais longe parecem menores. O modelo reto da Parte E não consegue descrever isso. O mapa consegue: ele converte cada pixel da linha do laser diretamente em dois números em milímetros:

* $t$: distância do eixo ao longo da folha (o raio que queremos)
* $z$: altura acima da plataforma

Ele substitui os quatro números `PX_PER_MM`, `AXIS_COL`, `BASE_ROW` e `ALPHA_DEG`.

Abra `tilted_example.png` (imagem enviada com este guia): o painel 1 é o que a câmera inclinada vê, o painel 2 mostra que a linha em um cilindro reto fica inclinada, o painel 3 é o resultado após o mapa.

### COMO É MEDIDO

Com o mesmo tipo de cilindros da Parte E. Um cilindro de raio $R$ e altura $H$, centralizado no eixo, faz uma linha de laser cujas duas extremidades são pontos conhecidos da folha:

$$
\text{extremidade inferior} = (t = R, z = 0), \quad \text{extremidade superior} = (t = R, z = H)
$$

Cada cilindro dá 2 pontos. Dois cilindros (4 pontos) são o mínimo. **TRÊS** são melhores: assim os seis pontos podem ser verificados uns contra os outros, e o assistente avisa quando eles não se encaixam.

### F-1 TESTE COM FOTOS FALSAS (sem hardware)

Arquivos necessários na pasta (cinco):
`scanner_config.py`, `laser_sim.py`, `detect_line.py`, `calibrate.py`, `plane_map.py`.

> **IMPORTANTE:** `laser_sim.py` foi **ATUALIZADO** novamente (agora ele pode simular uma câmera inclinada). Substitua o seu `laser_sim.py` antigo. Tudo das partes anteriores dá exatamente os mesmos resultados com ele (eu reexecutei tudo).

Execute:

```bash
python plane_map.py
```

Você deve ver (em alguns segundos):

```text
Perspective map from 3 fake cylinders, tilted fake camera (12 photo pairs each, normal lamp)

  reference points agree within 0.03 mm (rms)
  against the hidden truth (demo only), over the whole area t 0-40 mm, z 0-55 mm:
      map error: mean 0.10 mm, worst 0.26 mm

  map saved to camera_map.json

Check 1: a 4th cylinder (radius 30 mm) that was not used for the map
  measured radius error: +0.01 mm

Check 2: the fake vase, 12 photo pairs, every measured point compared with the true shape
  perspective map (this part)      : mean error 0.05 mm, worst 0.13 mm
  straight-on model (calibrate.py) : mean error 11.32 mm, worst 30.84 mm
      calibrate.py's own check says: The cylinders give different PX_PER_MM (3.80 and 3.06). ...
```

**Como ler isso:**
O programa inventa uma câmera inclinada (oculta), tira fotos falsas de três cilindros (raios de 25, 35 e $15\text{ mm}$) e mede o mapa apenas a partir dessas fotos.

* `"reference points agree within 0.03 mm"`: os seis pontos de referência se encaixam em um único mapa quase perfeitamente. Esta é a autoverificação. Deve ficar abaixo de $0.4\text{ mm}$.
* `"against the hidden truth"`: apenas na demonstração. Como a inclinação é secreta, mas conhecida pelo programa, ele pode avaliar o mapa. Média de $0.10\text{ mm}$.
* `Check 1` é o hábito para a máquina real: um objeto conhecido que **NÃO** foi usado para criar o mapa. Erro $+0.01\text{ mm}$.
* `Check 2` é o principal: o vaso tem uma forma que muda com a altura. O mapa de perspectiva erra por $0.05\text{ mm}$ em média. O método reto da Parte E erra por $11\text{ mm}$ e avisa por conta própria que algo está errado (seus dois cilindros discordam sobre `PX_PER_MM`): com uma câmera inclinada, ele é inutilizável.

O novo arquivo `camera_map.json` guarda o mapa (nove números). É o que o scanner vai carregar.

### F-2 EXPERIMENTOS

* **Salvando as fotos inclinadas:**

```bash
python plane_map.py --save-photos
```

  Mesma execução, e também grava as fotos falsas nas pastas `tilt_A`, `tilt_B` e `tilt_C` (24 imagens cada). Abra `tilt_B/on_00.png`: a linha do laser está claramente **INCLINADA**, não vertical.

* **Calculando a partir das pastas:**

```bash
python plane_map.py --cyl tilt_A 25 50 --cyl tilt_B 35 45 --cyl tilt_C 15 40
```

  Mede a partir dos **ARQUIVOS** de foto em vez de criar fotos falsas, e dá exatamente o mesmo mapa (comparei os dois arquivos: diferença 0.0). É assim que você usará fotos reais: uma pasta por cilindro (fotos nomeadas `on_00.png`, `off_00.png`, `on_01.png` ...), e após cada `--cyl` o raio em mm e a altura em mm.

* **Lâmpada muito forte:**

```bash
python plane_map.py --strong-lamp
```

  Uma lâmpada tão forte que a câmera satura próximo à linha. O assistente diz `"reference points agree within 4.43 mm"` (deveria ser abaixo de 0.4), imprime um `WARNING` de que uma linha provavelmente foi cortada, e **NÃO** salva o mapa. Mesma lição da Parte E: mantenha a exposição da câmera baixa e a sala escura.

* **Erro de digitação na altura:**

```bash
python plane_map.py --cyl tilt_A 25 50 --cyl tilt_B 35 45 --cyl tilt_C 15 55
```

  Digitei a altura do terceiro cilindro errada (55 em vez de 40). Resultado: `"agree within 2.21 mm"`, `WARNING`, mapa não salvo. A verificação de três cilindros também protege contra erros de digitação.

* **Apenas dois cilindros:**

```bash
python plane_map.py --cyl tilt_A 25 50 --cyl tilt_B 35 45
```

  Funciona e salva um mapa, mas avisa que com dois cilindros não há como fazer autoverificação.

* **Cilindros de mesmo raio (recusado):**

```bash
python plane_map.py --cyl tilt_A 25 50 --cyl tilt_B 25 45
```

  Recusado (`"the cylinder radii must differ by at least 3 mm"`), porque eles não dariam informação sobre como o mapa se comporta do eixo para fora.

### F-3 QUÃO PRECISO ELE É? (fotos falsas, inclinações aleatórias)

Criei 30 câmeras inclinadas aleatórias (diferentes forças e direções de inclinação, cilindros colocados fora do centro em até $2.5\text{ mm}$) e escaneei o vaso através de cada mapa. 0 de 30 deram um falso aviso.

* **Com 3 cilindros:** erro médio dos pontos do vaso de $0.04\text{ mm}$; pior ponto individual em todas as 30 tentativas de $0.22\text{ mm}$. O mapa em si ficou dentro de $0.36\text{ mm}$ em toda a área $t \in [0, 40]\text{ mm}$, $z \in [0, 55]\text{ mm}$.
* **Com apenas 2 cilindros:** média de $0.05\text{ mm}$, pior ponto individual de $0.27\text{ mm}$, mapa dentro de $0.52\text{ mm}$. Ligeiramente pior, e sem autoverificação.

Comparação do modelo reto (Parte E) contra o mapa de perspectiva no vaso (erro médio):

| Inclinação | Mapa de Perspectiva (Parte F) | Modelo Reto (Parte E) |
| :--- | :--- | :--- |
| Sem inclinação | $\sim 0.06\text{ mm}$ | $\sim 0.06\text{ mm}$ |
| Metade da inclinação | $0.04\text{ mm}$ | $0.17\text{ mm}$ |
| Inclinação da demo | $0.06\text{ mm}$ | $11.0\text{ mm}$ *(inutilizável)* |
| $1.5\times$ a inclinação | $0.05\text{ mm}$ | $18.0\text{ mm}$ |
| $2.0\times$ a inclinação | $0.06\text{ mm}$ | $24.0\text{ mm}$ |

*(Fotos reais serão menos precisas do que essas fotos falsas.)*

### F-4 UM ESCANEAMENTO COMPLETO COM UMA CÂMERA INCLINADA

Arquivos na pasta (oito): `mesh.py`, `viewer.py`, `scanner_config.py`, `laser_sim.py`, `detect_line.py`, `calibrate.py`, `plane_map.py`, `simulate_scan.py`.

`simulate_scan.py` foi **ATUALIZADO**: substitua sua cópia antiga (ele se comporta exatamente como antes, a menos que você adicione `--tilted`).

Execute:

```bash
python simulate_scan.py --tilted
```

Você deve ver (o tempo depende do seu PC):

```text
building the perspective map from fake cylinders ...
map ready (against the hidden truth: mean 0.10 mm, worst 0.26 mm)
scan took 4.2 s
mesh: 2402 vertices, 4800 faces -> scan.obj
closed mesh: True, outward
volume  scanned 81,996 mm3   true 82,125 mm3   difference -0.16 %
distance between scanned and true surface: mean 0.049 mm, worst 0.131 mm
picture: scan_preview.png
```

O vaso retorna com a mesma forma de antes, embora cada foto tenha sido tirada por uma câmera inclinada. Outras opções funcionam também, ex: `--angles 30 --noise 15` (obtive distância média de $0.050\text{ mm}$). `--axis-error` não funciona com `--tilted` (não há mais `AXIS_COL`) e o programa avisa isso.

### F-5 USANDO COM A CÂMERA REAL (mais tarde)

1. Monte a câmera e o laser, e **NÃO OS MOVA** depois disso. O mapa só é válido para esta posição exata da câmera e esta posição exata do laser. Se você mover a câmera, o laser ou a plataforma, meça o mapa novamente.
2. Tire fotos de três cilindros conforme descrito na Parte E, passo E-4 (raios claramente diferentes, por exemplo 15, 25 e $35\text{ mm}$; meça o raio e a altura com cuidado; fotos em 8 a 12 ângulos igualmente espaçados; mesmas configurações de câmera; pastas com arquivos `on_00` / `off_00` ...).
3. Olhe para as suas fotos: se a linha do laser em um cilindro reto estiver inclinada, você precisa desta parte (se estiver vertical, a Parte E basta). Então execute:

```bash
python plane_map.py --cyl PASTA_A raioA alturaA --cyl PASTA_B raioB alturaB --cyl PASTA_C raioC alturaC
```

4. Se disser `"map saved to camera_map.json"`, escaneie um objeto de tamanho **CONHECIDO** e verifique o tamanho medido. Se der um aviso, corrija o que ele diz e repita.
5. No programa do scanner, converta cada par de fotos assim:

```python
from plane_map import load_map, detect_profile_plane
H = load_map("camera_map.json")
r, z = detect_profile_plane(photo_on, photo_off, H,
                            n_points, z_min, z_max)
slices.append(list(zip(r, z)))
```

**Limitações importantes:**

* Não testado com fotos reais. Linhas reais podem precisar de ajuste no limiar do detector (Parte C-2).
* O mapa assume uma câmera *pinhole* perfeita. Lentes grande-angulares (*"Wide"*) curvam linhas retas, e o mapa não consegue corrigir isso. Mais um motivo para evitar as versões de câmera "Wide".
* `detect_profile_plane` precisa da faixa de altura `z_min` a `z_max` que você deseja amostrar. Na simulação a altura do objeto é conhecida; para um objeto real não é, então `scan_folder.py` (Parte H) pega os pontos mais baixos e mais altos encontrados em todas as fotos e faz todo o escaneamento.

### F-6 SE ALGO DER ERRADO

* `"the cylinder radii must differ by at least 3 mm"`: use cilindros com raios claramente diferentes.
* `"agree within X mm"` com X acima de 0.4, e um `WARNING`: uma linha de laser foi cortada (lâmpada muito forte, laser muito fraco), ou um raio ou altura foi digitado errado. Corrija e repita.
* `"laser line not found in one of the photos"`: veja Parte C-2 (laser fraco).
* `"Need at least 3 on_/off_ pairs"`: poucas fotos em uma pasta, ou os nomes dos arquivos não começam com `on_` e `off_`.

## PARTE G - LIMPEZA DE UM ESCANEAMENTO (`cleanup.py`, `glitches.py`, `test_cleanup.py`)

**Objetivo:** fotos reais dão errado de vez em quando, e uma foto errada cria um amassado ou um espinho (pico) na malha. Esta parte remove pontos errados e preenche buracos **ANTES** que a malha seja construída.

**Problemas típicos** (`glitches.py` cria problemas falsos para podermos testar o reparo):

* `reflection` (reflexo): um ponto brilhante que não é a linha do laser (o laser refletindo em algo brilhante). O detector segue o ponto.
* `shadow` (sombra): parte da linha fica escondida. O detector não encontra nada ali.
* `dead pair` (par morto): um par inteiro de fotos é inútil (o laser não ligou, a lâmpada piscou, alguém passou na frente). Nenhuma linha.

*(Cerca de* $12\%$ *dos pares de fotos recebem um reflexo,* $12\%$ *uma sombra,* $3\%$ *são mortos. Esses são meus palpites de como fotos reais falham; fotos reais podem falhar de outras maneiras, e nada disso foi testado em fotos reais ainda.)*

### COMO FUNCIONA

O escaneamento é uma tabela: uma linha por foto, uma coluna por altura, o raio em cada célula. O objeto é suave de um ângulo de foto para o próximo, então uma célula que esteja a mais de $2\text{ mm}$ de distância do valor mediano da mesma altura nas 3 fotos de cada lado é considerada errada. Células erradas, e buracos onde a linha estava faltando, são descartados e preenchidos por uma linha reta (interpolação) entre as fotos boas mais próximas naquela altura (a última foto é vizinha da primeira).

Duas células acima e abaixo de cada célula errada também são refeitas, porque a borda de uma mancha ruim geralmente está um pouco fora também.

A suavização (misturar cada célula com suas vizinhas) está disponível, mas **DESLIGADA** por padrão, veja G-3.

### PASSO 0 - Verifique a pasta

Coloque estes arquivos em `scanner3d`, substituindo as cópias mais antigas:
`detect_line.py`, `simulate_scan.py`, `plane_map.py` *(todos os três atualizados)*

e adicione os novos arquivos:
`cleanup.py`, `glitches.py`, `test_cleanup.py`.

> **IMPORTANTE:** `plane_map.py` agora precisa do **NOVO** `detect_line.py`. Se você substituir um deles, substitua ambos. Os arquivos das partes anteriores permanecem como estão.

### G-1 TESTE: UM ESCANEAMENTO DANIFICADO, DEPOIS O MESMO REPARADO

1. **Escaneamento danificado, não reparado (apenas dois tipos de problemas):**

```bash
python simulate_scan.py --glitches --glitch-kinds reflection,shadow --out messy.obj --preview messy.png
```

   Você deve ver (o resto como na Parte D):

```text
fake problems added to 13 of 60 photo pairs: reflection 5, shadow 8
volume  scanned 81,833 mm3   true 82,125 mm3   difference -0.36 %
distance between scanned and true surface: mean 0.074 mm, worst 13.954 mm
```

   O volume parece quase certo, mas o pior ponto está $14\text{ mm}$ fora. Abra `messy.png`: amassados e sulcos na superfície.

2. **Os mesmos tipos de problemas, mais pares de fotos mortos, SEM `--clean`:**

```bash
python simulate_scan.py --glitches
```

   Ele para com: `No laser line found at angle 18 deg.`

   Um par morto é suficiente para travar um escaneamento.

3. **Mesmos problemas, reparados:**

```bash
python simulate_scan.py --glitches --clean --out repaired.obj --preview repaired.png
```

   Você deve ver:

```text
fake problems added to 15 of 60 photo pairs: reflection 5, shadow 8, dead 2
clean-up: 112 points missing, 12 wrong, 164 of 2400 redone
volume  scanned 82,084 mm3   true 82,125 mm3   difference -0.05 %
distance between scanned and true surface: mean 0.018 mm, worst 1.820 mm
```

   Abra `repaired.png`: o vaso liso novamente, mesmo com dois pares de fotos mortos.

   **O que a linha clean-up diz:**
   * `112 points missing`: os 2 pares mortos ($2 \times 40$ pontos) mais 32 pontos em partes ocultas da linha
   * `12 wrong`: pontos distantes de seus vizinhos (reflexos)
   * `164 of 2400 redone`: todos os itens acima mais a expansão de duas células
   * *Por que o pior ponto ainda é* $1.8\text{ mm}$*:* alguns reflexos puxaram a linha apenas $1.5$ a $1.8\text{ mm}$ para fora. Isso está abaixo do limite de $2\text{ mm}$, então eles são deixados em paz. $1.8\text{ mm}$ é o pior de 2400 pontos; a média é $0.018\text{ mm}$.

   Também funciona com a câmera inclinada da Parte F (precisa de `plane_map.py`):

```bash
python simulate_scan.py --tilted --glitches --clean
```

   *(diferença de volume* $-0.17\%$*, média* $0.054\text{ mm}$*, pior* $0.612\text{ mm}$*)*

### G-2 O TESTE COM NÚMEROS

```bash
python test_cleanup.py
```

Leva cerca de 1.5 minuto (5 escaneamentos falsos por caso). Use `--seeds 2` para ser mais rápido (os números variarão um pouco). Ele imprime o erro de raio contra a forma verdadeira e salva `cleanup_demo.png`:

```text
case (radius error vs the truth)   mean mm  worst mm
  1  no problems, raw                  0.009      0.10
  1  no problems, cleaned              0.009      0.10
  1  no problems, cleaned+smooth 1     0.071      0.51
  2  reflections+shadows, raw          0.114     21.53
  2  reflections+shadows, cleaned      0.012      0.61
  3  + dead photo pairs, cleaned       0.013      0.61
  4  noisy camera, raw                 0.036      0.28
  4  noisy camera, cleaned             0.036      0.28
  4  noisy camera, cleaned+smooth 1    0.072      0.56
  5  rough, 0.3 mm noise, raw          0.239      1.19
  5  rough, 0.3 mm noise, smooth 1     0.114      0.78
  5  rough, 0.3 mm noise, smooth 2     0.145      1.01
```

`cleanup_demo.png`: à esquerda, onde estão os erros antes da limpeza (brilhante = grande); no meio, depois; à direita, uma fatia: verdadeiro (preto), medido (vermelho) e limpo (verde).

### G-3 O QUE OS NÚMEROS DIZEM

* **Caso 1:** em um bom escaneamento, a limpeza não muda nada. É seguro deixá-la ligada.
* **Casos 2 e 3:** o pior erro cai de cerca de $21\text{ mm}$ para $0.6\text{ mm}$ e pares de fotos mortos deixam de ser um problema (4 deles nesses 5 escaneamentos).
* **Suavização (*smoothing*):** fica DESLIGADA por padrão, porque em um bom escaneamento ela custa precisão (caso 1: de $0.009$ para $0.071\text{ mm}$, ela arredonda os três lóbulos). Ela só compensa quando a própria superfície está esburacada/áspera: o caso 5 adiciona $0.3\text{ mm}$ de ruído aleatório diretamente na tabela (colocado por mim, NÃO vindo das fotos, para mostrar o que a suavização faz, e não o quão ruidosa sua câmera é): uma passada reduz o erro pela metade (de $0.239$ para $0.114\text{ mm}$), uma segunda passada é pior que uma. **Regra:** escaneie primeiro, olhe para a malha e, somente se estiver áspera, adicione `--smooth 1`.
* Também tentei um limite de $1.5\text{ mm}$ em vez de $2\text{ mm}$: não ficou melhor (pior caso $0.89\text{ mm}$ contra $0.61\text{ mm}$), então $2\text{ mm}$ continua sendo o padrão.

### G-4 LIMITAÇÕES (por favor, leia)

* A limpeza assume que o objeto muda **SUAVEMENTE** de uma foto para a próxima. Detalhes mais finos do que alguns passos de foto parecem um erro e são removidos. Medido em tabelas perfeitas e sem erros: o vaso de 3 lóbulos com 60 fotos é deixado intacto, mas com 36 fotos, 42 pontos corretos são refeitos erroneamente (alterados em até $0.56\text{ mm}$), e um objeto com 8 protuberâncias ao redor com 60 fotos é danificado em até $4.6\text{ mm}$.
  *Proteção:* quando mais de $2\%$ dos pontos parecem errados, o programa imprime um AVISO (experimente: `python simulate_scan.py --angles 36 --clean` resulta em `"3.1 % of the points looked wrong ..."`). Quando vir isso, ou as fotos estão ruins ou você precisa de mais fotos por volta (`--angles`) ou de um limite maior (`--spike 3`).
* Erros menores que o limite ($2\text{ mm}$) não são reparados.
* Se mais de 3 fotos seguidas estiverem ruins na mesma altura, o reparo ali será um palpite e um `WARNING` avisará sobre isso.
* São necessárias pelo menos 7 fotos.
* Os problemas falsos são um palpite meu. Escaneamentos reais mostrarão quão bem isso funciona; espere ter que ajustar `--spike`.

### G-5 OPÇÕES DO `simulate_scan.py`

* `--glitches`: adiciona problemas falsos (reflexos, sombras, mortos)
* `--glitch-kinds a,b`: apenas alguns: escolha entre `reflection,shadow,dead`
* `--clean`: repara antes de construir a malha
* `--spike 2.0`: o limite em mm (menor = mais sensível, mas pode remover detalhes reais)
* `--smooth 1`: número de passadas de suavização (padrão 0)

Sem essas opções, tudo funciona como nas Partes D a F, com os mesmos números.

### G-6 USANDO COM FOTOS REAIS (mais tarde)

No seu próprio código, por par de fotos:

```python
r, z, _ = detect_profile(on, off, 40, 0, height, 3.0)
```

O `3.0` diz ao detector para deixar buracos maiores que $3\text{ mm}$ VAZIOS em vez de traçar uma linha reta através deles. Se ele não encontrar nenhuma linha, capture o erro (`try/except`) e use `r = np.full(40, np.nan)`. Depois, com todos os `r` em uma lista:

```python
from cleanup import clean_slices
R_clean, info = clean_slices(np.array(all_r))
print(info["warnings"])
```

Construa a malha a partir de `R_clean` (uma linha por foto). O próximo programa, `scan_folder.py` (Parte H), fará tudo isso para você.

### G-7 SE ALGO DER ERRADO

* `"No module named cleanup"` / `"glitches"`: o arquivo não está na pasta.
* `"cannot import name 'resample'"` (de `plane_map.py`): `detect_line.py` é o antigo. Substitua-o pelo novo.
* `"Unknown --glitch-kinds"`: existem apenas `reflection`, `shadow` e `dead`.
* `"need at least 7 photos to clean up"`: use `--angles 7` ou mais.
* `"a whole photo has no usable data and its neighbours have none either"`: muitas fotos ruins seguidas; o escaneamento em si precisa ser refeito.
* Linhas de `WARNING`: veja G-4.

## PARTE H - ESCANEANDO A PARTIR DE UMA PASTA DE FOTOS (`scan_folder.py`)

**Objetivo:** o programa que você executará nas fotos **REAIS**. Você fornece uma pasta com os pares de fotos; ele encontra a altura do objeto sozinho, mede cada foto, repara as ruins (Parte G), constrói a malha e desenha uma imagem. Ele funciona da mesma forma nas fotos falsas do simulador, então você pode testá-lo agora.

### AS FOTOS: O QUE O PROGRAMA ESPERA

* Uma pasta. Nela, um par por posição da plataforma:
  `on_00.png`, `off_00.png`, `on_01.png`, `off_01.png` ... (laser ligado, laser desligado; `.png` ou `.jpg`; números com ou sem zero à esquerda)
* As posições são **UNIFORMEMENTE** espaçadas ao longo de exatamente **UMA** volta completa. A foto número $k$ de $N$ está no ângulo $360 \times k / N$. Portanto, 60 fotos = uma a cada $6^\circ$. A foto `00` é a posição inicial. **NÃO** adicione uma foto nos $360^\circ$ completos: seria o mesmo lugar da foto `00`.
* Os números podem começar em `00` ou em `01`.
* Mesmas configurações de câmera e mesmo tamanho de imagem das fotos de calibração.
* Um número faltando (ou um par onde nenhuma linha é encontrada) é reparado como na Parte G. *Cuidado:* se as **ÚLTIMAS** fotos forem as que estão faltando, o programa não tem como saber. Sempre verifique a linha `"positions in one turn"` na saída contra o número de fotos que seu scanner tira por volta, e forneça esse valor com `--per-turn N` se eles diferirem.

### A FAIXA DE ALTURA

O programa não sabe a altura do objeto de antemão. Em cada foto, ele mede o ponto mais baixo e o mais alto da linha do laser, e usa a **MEDIANA** de todas as fotos (uma única foto com um reflexo perdido não consegue esticar a faixa). A base nunca é menor que a plataforma ($z = 0$). Você pode fornecer sua própria faixa com `--z-range BAIXO ALTO` (em milímetros).

### PASSO 0 - Verifique a pasta

Para o `scan_folder.py` sozinho, estes seis arquivos são suficientes:
`mesh.py`, `viewer.py`, `scanner_config.py`, `detect_line.py`, `cleanup.py`, `scan_folder.py` *(este é o novo; `simulate_scan.py` foi atualizado novamente)*.

Arquivos extras apenas para algumas opções:

* `--check-vase`: `laser_sim.py`
* `--map`: `plane_map.py`, `calibrate.py`, `laser_sim.py`

Para **CRIAR** fotos falsas você também precisa dos arquivos das Partes D e G (`simulate_scan.py` com `laser_sim.py`, e `glitches.py` para as danificadas).

### H-1 TESTE COM FOTOS FALSAS

1. **Crie uma pasta de fotos falsas (60 pares) e escaneie-a:**

```bash
python simulate_scan.py --save-photos scan_photos
python scan_folder.py scan_photos --check-vase
```

   O primeiro comando imprime o resultado habitual da Parte D e cria a pasta `scan_photos` (120 arquivos png). O segundo deve mostrar:

```text
folder 'scan_photos': 60 photo pairs
camera model: straight-on, numbers of scanner_config.py (...)
positions in one turn: 60 (6.00 degrees per photo) ...
height range: 0.0 to 60.2 mm (60.2 mm tall)  (found in the photos)
clean-up: 0 points missing, 0 wrong, 0 of 2400 redone
mesh: 2402 vertices, 4800 faces -> scan.obj
closed mesh: True, outward
volume 82,317 mm3
size: 56.6 x 59.7 mm across, 60.2 mm tall
distance to the TRUE fake vase: mean 0.012 mm, worst 0.229 mm
picture: scan_preview.png
```

   O programa não foi informado sobre a altura; ele encontrou $60.2\text{ mm}$ para um vaso de $60\text{ mm}$. Os $0.2\text{ mm}$ a mais são provavelmente a borda suave da linha do laser (a linha é borrada por alguns pixels, então parece alcançar um pouco além do topo do objeto).

   `"size"` é a largura do escaneamento em $x$ e $y$ (aqui o vaso não é redondo, então os dois números diferem) e sua altura. Para um objeto real, compare isso com uma régua.

2. **Fotos danificadas (problemas da Parte G), reparadas pelo mesmo programa:**

```bash
python simulate_scan.py --glitches --clean --save-photos messy_photos
python scan_folder.py messy_photos --check-vase
```

   Você deve ver:

```text
no laser line found in: on_03, on_45
clean-up: 112 points missing, 12 wrong, 164 of 2400 redone
distance to the TRUE fake vase: mean 0.020 mm, worst 1.541 mm
```

   Os dois pares mortos são nomeados, para que com fotos reais você saiba quais refazer.

3. **Uma câmera inclinada (Parte F):**

```bash
python simulate_scan.py --tilted --save-photos tilt_photos
python scan_folder.py tilt_photos --map tilt_photos/camera_map.json --check-vase
```

   Você deve ver:

```text
camera model: perspective map from tilt_photos/camera_map.json
height range: 0.0 to 60.0 mm (60.0 mm tall)  (found in the photos)
volume 81,947 mm3
distance to the TRUE fake vase: mean 0.049 mm, worst 0.130 mm
```

Os arquivos `scan.obj` e `scan_preview.png` são sobrescritos a cada execução; use `--out` e `--preview` para manter vários.

### H-2 O TESTE COM OBJETOS DE OUTRAS ALTURAS

```bash
python test_scan_folder.py
```

Leva cerca de 20 segundos. Três objetos falsos de diferentes alturas são fotografados, gravados em uma pasta temporária e escaneados **SEM** informar a altura ao programa.

```text
object                      true mm   height found   mean err    worst
short bowl                     35.0     0.0 to  35.0     0.009     0.12
tall column                    70.0     0.0 to  70.2     0.006     0.03
cup, tilted camera + map       45.0     0.0 to  45.0     0.049     0.14
```

A altura é encontrada dentro de $0.2\text{ mm}$. Os erros são raios comparados com a forma verdadeira, em milímetros.

### H-3 OPÇÕES DO `scan_folder.py`

* `--map ARQUIVO`: câmera inclinada: usa o mapa de perspectiva (Parte F). Sem isso, usa os números retos de `scanner_config.py` (Parte E)
* `--points 40`: pontos por fatia, de baixo para cima (mais = mais fino)
* `--z-range MIN MAX`: faixa de altura em mm em vez da automática
* `--per-turn N`: posições de foto em uma volta completa
* `--no-clean`: não repara fotos ruins (ele para na primeira que falhar)
* `--spike 2.0`: limite de limpeza em mm (Parte G)
* `--smooth 1`: passadas de suavização (Parte G, padrão 0)
* `--mirror`: espelha o resultado
* `--check-vase`: apenas para as fotos do vaso falso
* `--out ARQUIVO`: nome do `.obj` (padrão `scan.obj`)
* `--preview ARQUIVO`: nome da imagem (padrão `scan_preview.png`)
* E para o `simulate_scan.py`: `--save-photos PASTA` grava as fotos falsas.

### H-4 USANDO COM AS FOTOS REAIS (mais tarde)

1. **Calibre:** Parte E (coloque os quatro números em `scanner_config.py`) ou Parte F (`camera_map.json`, depois sempre adicione `--map camera_map.json`).
2. Coloque o objeto na plataforma. Tire $N$ pares de fotos ao longo de UMA volta completa (por exemplo, 60) em uma nova pasta, nomeadas `on_00.png` / `off_00.png` ... . *(Parte I: `capture.py` tira as fotos para você e as nomeia corretamente.)*
3. Execute:

```bash
python scan_folder.py PASTA
```

   *(ou com `--map camera_map.json`)*

4. **VERIFIQUE O TAMANHO.** A linha `"size"` e a altura encontrada devem bater com uma régua. Faça isso primeiro com um objeto de tamanho conhecido (um bloco de $50\text{ mm}$, uma lata).
5. Se a plataforma girar para o outro lado, o escaneamento de um objeto que não é simétrico (uma caneca com alça) parecerá espelhado. Adicione `--mirror`.

### H-5 LIMITAÇÕES (por favor, leia)

* **NÃO TESTADO COM FOTOS REAIS.** Tudo acima usa fotos falsas. Linhas reais podem precisar de ajuste no limiar do detector (Parte C-2), objetos reais têm pontos brilhantes, plataformas reais balançam.
* Um raio por altura e ângulo: o modelo não consegue representar um buraco, uma saliência suspensa (*overhang*) ou uma alça que se projeta.
* Cada ângulo recebe a mesma faixa de altura. Se a linha terminar em alturas claramente diferentes (espalhadas por mais de $3\text{ mm}$), um `WARNING` avisará e a malha poderá mostrar degraus.
* O topo e a base são fechados com uma tampa plana, independentemente de como seja o topo real do objeto.
* A calibração só é válida para a câmera, o laser e a plataforma exatamente como estavam quando você calibrou, e para o mesmo tamanho de imagem.

### H-6 SE ALGO DER ERRADO

* `"The folder 'x' does not exist"`: nome errado, ou o terminal não está no lugar certo (1.5).
* `"Need at least 3 on_/off_ photo pairs"`: os nomes devem se parecer com `on_00.png` e `off_00.png`.
* `"These photo numbers have only an on_ or only an off_ photo"`: um arquivo está faltando; cada `on_NN` precisa do seu `off_NN`.
* `"... have different sizes"`: as duas fotos de um par foram tiradas em resoluções diferentes.
* `"No laser line found in most of the photos"`: laser fraco ou muita luz (Parte C-2).
* `"The height range found is only X mm"`: calibração errada para essas fotos, ou nenhum objeto. Se você souber a faixa, use `--z-range`.
* Um `"size"` que é absurdo (por exemplo, $611\text{ mm}$ para um objeto pequeno): a calibração não pertence a essas fotos.

## PARTE I - O PI: CÂMERA, LASER, PLATAFORMA (`capture.py`, `test_capture.py`)

**Objetivo:** tirar as fotos. O `capture.py` liga o laser, tira uma foto, desliga o laser, tira uma foto, move a plataforma um passo e repete por uma volta completa. Ele grava a pasta que o `scan_folder.py` (Parte H) lê.

### LEIA ISTO PRIMEIRO - O QUE FOI TESTADO E O QUE NÃO FOI

* O código da câmera, laser e motor de passo foi escrito a partir da documentação do `picamera2` e `gpiozero`. Eu **NÃO** o executei em um Raspberry Pi, câmera, laser ou motor reais. Espere ter que corrigir pequenas coisas na primeira execução real; os passos em I-2 estão na ordem que encontra os problemas um de cada vez.
* O que **FOI** testado (`test_capture.py`, 37 verificações, I-1): toda a lógica própria do programa, usando SUBSTITUTOS (*mocks/stand-ins*) para `picamera2` e `gpiozero` que escrevi a partir da documentação.
* Quatro maneiras de mover a plataforma:
  * `uln2003`: o motor 28BYJ-48 + placa ULN2003 do seu projeto com Pico, acionado DIRETAMENTE pelos pinos GPIO do Pi (veja 2.5A)
  * `stepper`: um motor de passo com uma placa driver STEP/DIR (A4988 ...)
  * `manual`: você gira com a mão para cada posição (padrão, não precisa de nada além de uma marcação ou escala de ângulos)
  * `dry-run`: câmera, laser e plataforma falsos, no seu PC

### PASSO 0 - Verifique a pasta

Adicione `capture.py` e `test_capture.py` à pasta `scanner3d`. Para `--dry-run` e `--check` você também precisa de `laser_sim.py`, `scanner_config.py` e `detect_line.py` na pasta.

### I-1 TESTE NO SEU PC (sem hardware)

1. **Uma captura falsa completa e, em seguida, o escaneamento dela:**

```bash
python capture.py --dry-run --out dry_photos
python scan_folder.py dry_photos --check-vase
```

   O primeiro comando imprime:

```text
fake camera (laser_sim.py), 640 x 480
60 positions, one every 6.00 degrees -> folder 'dry_photos'
60 photo pairs in 0 min 4 s
```

   e cria 120 arquivos jpg (`on_00.jpg`, `off_00.jpg`, ...). Executar o primeiro comando novamente na mesma pasta para com a mensagem `"The folder 'dry_photos' already has photos."` para que nada seja sobrescrito; use outro nome em `--out`, ou adicione `--overwrite`.

2. **A verificação de foto em um par falso:**

```bash
python capture.py --dry-run --check
```

   Ele grava `check_photos/on_00.jpg` e `off_00.jpg` e imprime:

```text
rows with a laser line found: 76 % of the picture height
holes inside the line: 0 %
line brightness (laser on minus off, median): 116   (the detector needs 40 ...)
laser-OFF photo, pixels already at full red (255): 0.0 %
Looks fine. Open both photos and look at them yourself too.
```

   Com a câmera real, este relatório é como você ajusta a exposição (I-3).

3. **O teste com números:**

```bash
python test_capture.py
```

   Leva cerca de 1 minuto e termina com `"37 of 37 checks passed"`. A seção 7 da sua saída responde a uma pergunta para quem gira a plataforma manualmente: qual é o custo de um erro de ângulo?

```text
angle error (std)     mean mm  worst mm
  0.0 degrees           0.009      0.10
  0.5 degrees           0.042      0.24
  1.0 degrees           0.081      0.48
  2.0 degrees           0.159      0.98
```

   Portanto, manualmente, mire em uma precisão melhor que $1^\circ$: um disco graduado impresso sob a plataforma, um ponteiro e uma mão firme.

### I-2 O PI, PASSO A PASSO (faça nesta ordem)

#### 2.1 Copie a pasta para o Pi e instale as bibliotecas

Copie toda a pasta `scanner3d` para o Pi (usando um pendrive, ou do seu PC via SCP):

```bash
scp -r scanner3d pi@raspberrypi.local:~/
```

No Pi, em um terminal:

```bash
sudo apt update
sudo apt install python3-picamera2 python3-gpiozero python3-opencv python3-numpy python3-matplotlib
```

Use esses pacotes do sistema (`apt`), não o `pip`: o `picamera2` depende do sistema de câmera do Raspberry Pi OS. Depois faça `cd ~/scanner3d` e continue lá.

#### 2.2 O cabo da câmera (Pi DESLIGADO)

* Use o conector identificado como **CAMERA** na placa (não o identificado como DISPLAY).
* Levante a pequena trava com cuidado, deslize o cabo flat totalmente para dentro de modo que os contatos metálicos do cabo encontrem os contatos internos, e empurre a trava de volta. Para o Pi 4, os contatos metálicos do cabo ficam voltados para as portas HDMI.
* O desalinhamento é o motivo mais comum para `"no camera found"`.

Ligue o Pi e teste:

```bash
rpicam-hello --list-cameras
```

*(Em versões mais antigas do SO, chama-se `libcamera-hello`.)* Se nenhum comando existir, tente:

```bash
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"
```

Uma lista vazia significa que o Pi não vê a câmera: verifique o cabo primeiro.

#### 2.3 O circuito do laser (Pi DESLIGADO, laser desconectado da energia)

**NÃO** alimente o laser diretamente por um pino GPIO. Um pino GPIO deve fornecer apenas alguns mA ($8\text{ mA}$ é o limite sensato por pino). O laser deve ser chaveado através de um transistor:

```text
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

* Verifique a etiqueta do seu módulo laser: muitos módulos de linha vermelha pedem de $3\text{ V}$ a $5\text{ V}$; se o seu disser $3\text{ V}$, não dê $5\text{ V}$ a ele.
* **SEGURANÇA COM O LASER:** nunca olhe diretamente para o feixe ou para o seu reflexo, mesmo que seja fraco. Mantenha objetos brilhantes fora do caminho dele e o Pi desligado enquanto faz a fiação.
* Se o seu módulo for acionado com um sinal BAIXO, adicione `--laser-active-low`. Outro pino: `--laser-pin N` (número BCM).

#### 2.4 Teste o laser

```bash
python3 capture.py --laser-test
```

Ele pisca o laser 3 vezes ($1\text{ s}$ ligado, $1\text{ s}$ desligado). Se nada acontecer, ou se ele ficar ligado quando deveria estar desligado: verifique a fiação e as pernas do transistor.

#### 2.5A O 28BYJ-48 + ULN2003 do seu projeto (plataforma acionada pelo Pi)

Este é o motor do repositório (`scanner_v3/main.py`), agora acionado pelo Pi em vez do Pico. Com o **Pi DESLIGADO**, conecte as quatro entradas `IN1..IN4` da placa ULN2003 aos pinos padrão do programa:

* `ULN2003 IN1` $\rightarrow$ **GPIO5** (pino 29)
* `ULN2003 IN2` $\rightarrow$ **GPIO6** (pino 31)
* `ULN2003 IN3` $\rightarrow$ **GPIO13** (pino 33)
* `ULN2003 IN4` $\rightarrow$ **GPIO19** (pino 35)
* `GND da placa ULN2003` $\rightarrow$ qualquer pino **GND** do Pi (ex: pino 30 ou 34)

*(Outra fiação: `--coil-pins A B C D` usando números BCM, na ordem IN1..IN4).*

Os próprios pinos `+` e `-` da placa ULN2003 alimentam o motor. Dê à placa sua própria fonte de $5\text{ V}$ (no seu projeto, o conversor step-down) e una o GND dela ao GND do Pi.

> **ATENÇÃO:** NUNCA conecte o Pico e o Pi às mesmas entradas do ULN2003 ao mesmo tempo: desconecte os fios GP2-GP5 do Pico primeiro.

Teste, com uma marcação na plataforma:

```bash
python3 capture.py --platform uln2003 --turn-test
```

Uma volta completa deve terminar com a marca onde começou. O programa assume 4096 meios-passos por volta. Se a marca terminar um pouco antes ou depois do início, ajuste:

```bash
python3 capture.py --platform uln2003 --steps-per-turn 4076 --turn-test
```

Se o motor apenas zumbir ou engasgar: use `--step-delay 0.004` (mais lento; o padrão é `0.0025`), e verifique a ordem da fiação de `IN1..IN4`. Se girar para o lado errado, use `--reverse`.

#### 2.5 Apenas se sua plataforma tiver um motor de passo STEP/DIR (A4988, DRV8825, ...)

* `STEP` no **GPIO20** (pino 38), `DIR` no **GPIO21** (pino 40), opcionalmente `ENABLE` em outro pino (`--enable-pin N`).
* O terra (GND) do driver conectado ao terra do Pi; a alimentação do MOTOR vinda de sua própria fonte.
* `--steps-per-turn` = $\text{passos do motor por volta} \times \text{micropassos} \times \text{relação de engrenagens}$ (ex: $200 \times 16 = 3200$).

Teste:

```bash
python3 capture.py --platform stepper --steps-per-turn 3200 --turn-test
```

#### 2.6 Sem motor: girando manualmente

Nada para conectar. O `capture.py` pede cada posição informando seu ângulo:

```text
Turn the platform to position 7 of 60 (42.0 degrees from the start), then press Enter ...
```

### I-3 PRIMEIRAS FOTOS: FACILITE A DETECÇÃO DA LINHA DO LASER

Coloque um objeto na plataforma, escureça a sala, aponte o laser para que sua linha caia sobre o objeto de cima a baixo e execute:

```bash
python3 capture.py --check
```

Ele tira um par de fotos na pasta `check_photos`, imprime o que a câmera está usando e gera um relatório. Abra ambas as fotos e olhe para elas: a foto `on` deve mostrar uma linha clara, a foto `off` nenhuma.

**O que o relatório diz:**

* `NO LINE FOUND`: o laser está ligado e sobre o objeto? Tente `--laser-test`; depois mude `--exposure-us` (menor se a sala estiver clara, maior se estiver escura).
* `line WEAK`: escureça a sala, aumente `--exposure-us`, ou aumente um pouco `--gain`.
* `holes inside the line`: o objeto esconde parte da linha, ou a luz ambiente está ofuscando-a.
* `pixels already at full red in the laser-OFF photo`: ali o laser não consegue aparecer de jeito nenhum (Parte C); diminua `--exposure-us`, escureça a sala, cubra a lâmpada ou janela.

**Exposição padrão:** `8333` microssegundos ($1/120\text{ s}$). Lâmpadas na rede elétrica de $60\text{ Hz}$ (normal no Brasil) piscam a $120\text{ Hz}$, e uma exposição de períodos inteiros de oscilação tira a média disso. Em redes de $50\text{ Hz}$, use `10000`.

**Tamanho da imagem:** `--size L A`, padrão `1640 1232`. Use o **MESMO** tamanho para as fotos de calibração e para as fotos de escaneamento.

**Fotos de calibração:** use o `capture.py` também. Para cada cilindro da Parte E ou F:

```bash
python3 capture.py --out calib_A --photos 12
```

### I-4 O ESCANEAMENTO

```bash
# Manualmente:
python3 capture.py --out photos

# Com driver STEP/DIR:
python3 capture.py --out photos --platform stepper --steps-per-turn 3200

# Com seu 28BYJ-48 (ULN2003):
python3 capture.py --out photos --platform uln2003
```

Depois, no Pi ou no seu PC:

```bash
python3 scan_folder.py photos
```

*(ou adicione `--map camera_map.json`)*

### I-5 OPÇÕES DO `capture.py`

* `--out PASTA`: para onde vão as fotos (padrão: `photos`)
* `--photos 60`: posições em uma volta completa
* `--format jpg|png`: tipo de arquivo (padrão `jpg`; `png` é mais lento para salvar)
* `--overwrite`: permite usar uma pasta que já contenha fotos
* `--dry-run`: câmera, laser e plataforma falsos (no PC)
* `--laser-test`: pisca o laser 3 vezes
* `--turn-test`: uma volta completa do stepper / uln2003, sem fotos
* `--check`: um par de fotos e um relatório
* `--platform manual|stepper|uln2003`
* `--steps-per-turn N`: (`uln2003`: padrão 4096; `stepper`: obrigatório)
* `--step-pin 20 --dir-pin 21 --enable-pin N`: (stepper)
* `--coil-pins 5 6 13 19`: IN1 IN2 IN3 IN4 (uln2003)
* `--step-delay S`: segundos por passo (padrão `0.002` stepper, `0.0025` uln2003)
* `--reverse`: gira para o outro lado
* `--settle 0.7`: segundos de espera após a plataforma se mover
* `--laser-pin 17 --laser-active-low --laser-settle 0.3`
* `--size L A --exposure-us 8333 --gain 1.0 --colour-gains VERMELHO AZUL`
* `--discard 2`: quadros descartados antes de cada foto

### I-6 LIMITAÇÕES E COISAS QUE NÃO PUDE VERIFICAR

* Nada aqui foi executado em hardware real.
* O programa espera $1\text{ s}$ após a câmera iniciar, espera `--laser-settle` após cada mudança do laser e descarta `--discard` quadros antes de cada foto. Se uma foto `on` não mostrar nenhuma linha, aumente `--discard` (tente 4) e `--laser-settle` (tente 0.6).

### I-7 SE ALGO DER ERRADO

* `"Could not import 'gpiozero'"` / `"'picamera2'"`: execute o comando `apt` de 2.1 no Pi. No seu PC use `--dry-run`.
* *O motor ULN2003 zumbe, mas não gira*: deixe mais lento (`--step-delay 0.004`), verifique `IN1..IN4` contra `--coil-pins`, e a fonte própria de $5\text{ V}$ do motor.
* *O laser continua ligado quando o programa termina*: desconecte-o da fonte imediatamente e verifique a fiação do transistor.

## PARTE J - O PC DÁ A ORDEM, O PI ESCANEIA E CRIA O MODELO 3D

*(`pi_server.py`, `scanner_page.html`, `export_stl.py`, `pc_client.py`, `test_remote.py`, `test_web.py`, `test_stl.py`)*

**Objetivo:** você digita um comando no PC (ou clica na página web); o Pi gira a plataforma, tira as fotos, cria o modelo 3D (o `scan_folder.py` roda **NO PI**) e o PC recebe o arquivo `model.obj`. O PC não faz processamento algum.

```text
PC  --- "iniciar, 60 fotos" --->  Pi (pi_server.py inicia capture.py)
PC  <-- "12 de 60 prontas" -----  Pi          (consultado a cada segundo)
PC  <-- "criando o modelo" -----  Pi (scan_folder.py, no Pi)
PC  <-- model.obj (~140 KB) ----  Pi
```

As fotos ficam no Pi (`scans/scan_DATA_HORA/`); o PC também pode baixá-las com `--photos-zip` (dezenas de MB).

### J-1 TESTE EM UM ÚNICO COMPUTADOR (sem Pi, sem hardware)

```bash
python test_remote.py
```

Leva cerca de 1 a 2 minutos e deve terminar com `"79 of 79 checks passed"` (e `python test_web.py` com `"26 of 26"`; `python test_stl.py` com `"14 of 14"`).

### J-2A PRIMEIRO TESTE PELO WI-FI (sem necessidade de câmera, laser ou motor)

1. Conecte o Pi ao Wi-Fi. O PC deve estar no **MESMO** Wi-Fi (ou ambos no roteador/hotspot do seu celular).
2. A pasta `scanner3d` deve estar no Pi com TODOS os arquivos `.py` e `.html`.
3. No Pi, em um terminal:

```bash
hostname -I          # mostra o IP do Pi, por exemplo 192.168.0.50
cd ~/scanner3d
python3 pi_server.py --allow-dry-run
```

   Ele imprime `"Scanner server on port 8000. Token: ..."`. Deixe-o rodando.

4. No PC, dentro da pasta `scanner3d` (use o IP e o token mostrados no Pi):

```bash
python pc_client.py --host 192.168.0.50 --token TOKEN run --photos 36 --dry-run --out from_pi
```

   Você deve ver o progresso contando, depois `"the Pi is making the model"`, e por fim `"from_pi/model.obj: ... KB"`. Abra o modelo com:

```bash
python viewer.py from_pi/model.obj
```

### J-2 NO PI E PC REAIS

1. No Pi, na pasta `scanner3d`, com o hardware conectado (Parte I):

```bash
python3 pi_server.py
```

   *(Para manter o mesmo token sempre: `--token SEUTOKENLONGO`, com pelo menos 10 caracteres).*

2. No PC, na pasta `scanner3d`:

```bash
python pc_client.py --host 192.168.0.50 --token Xk3b0Q7rJ1 run
```

**Opções de `run` e `start`:** `--photos 60`, `--platform uln2003|stepper` (padrão `uln2003`), `--steps-per-turn N`, `--reverse`, `--format jpg|png`, `--map camera_map.json`, `--dry-run`. Apenas para `run`: `--out PASTA`, `--photos-zip`, `--stl`.

**Outros comandos:** `status | wait | stop | download`.

### J-2B ONDE O MODELO É CRIADO, E QUALIDADE

O modelo é criado **APENAS** no Pi. O modelo não fica pior porque é o Pi que o faz: é o mesmo programa rodando sobre as mesmas fotos. O que muda é apenas o tempo de processamento (cerca de $6\text{ s}$ em um PC contra uma estimativa de $20\text{ a }50\text{ s}$ em um Pi 4).

### J-2C A PÁGINA WEB (botão iniciar, progresso, visualização 3D) - `scanner_page.html`

A maneira mais fácil de usar tudo o que foi visto acima, de qualquer navegador, inclusive pelo celular.

O arquivo `scanner_page.html` deve estar na mesma pasta que o `pi_server.py` **NO PI**. Então:

* **Mesmo Wi-Fi:** abra `http://IP_DO_PI:8000/`
* **Internet:** abra o endereço `https://....trycloudflare.com` de J-4

1. Digite a senha (o token) na primeira caixa.
2. Escolha o número de fotos (60 normalmente; 36 para um teste rápido). A página sempre usa o motor 28BYJ-48 + ULN2003. `"Scan de teste"` só aparece se o servidor foi iniciado com `--allow-dry-run`.
3. Clique em **"Iniciar scan"**. A página mostra o progresso em tempo real.
4. O modelo aparece na caixa **"Modelo 3D"**: arraste para girá-lo, use a roda do mouse (ou dois dedos) para dar zoom. Clique em **"Baixar modelo (.obj)"** ou **"Baixar fotos"**.

### J-2D A PÁGINA, CONTINUAÇÃO: TESTES DE HARDWARE, SCANS ANTIGOS, `.STL`

O arquivo `export_stl.py` deve estar ao lado de `pi_server.py` no Pi.

* **TESTES DO EQUIPAMENTO (cartão "Testes do equipamento"):** faça-os ANTES de um escaneamento:
  * **Testar laser:** o laser pisca 3 vezes (cerca de $6\text{ s}$).
  * **Foto de teste:** tira uma foto com o laser ligado e outra com ele desligado, mostra ambas na tela e exibe o relatório do `capture.py --check`. Use isso para ajustar a exposição (Parte I-3) direto pelo navegador.
* **SCANS ANTERIORES (cartão "Scans anteriores"):** lista os escaneamentos salvos no Pi com data, tamanho e espaço livre em disco. Permite **Ver** na tela 3D, baixar **Fotos** (`.zip`) ou **Apagar** (clique duas vezes para confirmar).
* **.STL:** abaixo da visualização 3D, clique em **"Baixar .stl (impressao 3D)"**. Gera um arquivo STL binário em milímetros, pronto para o fatiador (*slicer*). Pela linha de comando: `python export_stl.py model.obj`.

### J-3 SEGURANÇA E LIMITAÇÕES

* No mesmo Wi-Fi o servidor usa `http` puro; pela internet, use o túnel de J-4 que fornece `https`.
* Quem tiver o token pode ligar o laser e mover o motor: mantenha-o em segredo (mínimo de 10 caracteres) e mantenha a área ao redor do scanner limpa.

### J-4 PELA INTERNET (não apenas no mesmo Wi-Fi): CLOUDFLARE TUNNEL

Um túnel dá ao seu Pi um endereço `https` público sem precisar abrir portas no roteador.

1. **Instale o `cloudflared` no Pi (uma única vez):**
   Digite `uname -m`:
   * Se `aarch64` (Raspberry Pi OS 64-bit):

```bash
curl -LO https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb
```

   * Se `armv7l` (32-bit): baixe a versão `armhf` na mesma página de releases.

2. **Terminal 1 no Pi (o servidor, escutando APENAS o túnel local):**

```bash
cd ~/scanner3d
python3 pi_server.py --host 127.0.0.1 --token SEUTOKENLONGO --allow-dry-run
```

   *(Remova `--allow-dry-run` para escaneamentos reais).*

3. **Terminal 2 no Pi (o túnel):**

```bash
cloudflared tunnel --url http://localhost:8000
```

   Após alguns segundos, ele imprimirá um endereço como `https://palavras-aleatorias-aqui.trycloudflare.com`.

4. **Em QUALQUER computador ou celular com internet:**
   Abra aquele endereço `https://...` diretamente no navegador para usar a interface web, ou via linha de comando:

```bash
python pc_client.py --url https://palavras-aleatorias-aqui.trycloudflare.com --token SEUTOKENLONGO run --photos 36 --dry-run
```

   *(Se existir um arquivo `~/.cloudflared/config.yaml`, o túnel rápido não funciona: renomeie esse arquivo. Pare o túnel com `Ctrl+C` quando não estiver apresentando).*

## PARTE K - O QUE VEM A SEGUIR (ainda não construído)

1. **SUA primeira execução real**, na ordem de I-2 e I-3: cabo da câmera e teste da câmera, `--check`, circuito do laser e `--laser-test`, motor (ou disco graduado), fotos de calibração (Parte E ou F), e então o escaneamento de um objeto de tamanho **CONHECIDO** (Parte H, H-4). Diga-me cada mensagem de erro e mostre o relatório do `--check`.
2. **Ajustes após as fotos reais:** limites do detector (Parte C-2), padrões de exposição, tempos de estabilização (*settle times*).
3. **Verificar a Parte J** contra os requisitos do T2 da sua disciplina. O túnel (J-4) e a página web (J-2C) colocam o projeto inteiramente "na web".
4. **Adições possíveis:** um comando único que captura e escaneia direto no Pi, ajustes de escala.

## SOLUÇÃO DE PROBLEMAS (TROUBLESHOOTING)

* **`"python is not recognized"` / `"command not found"`**
  Windows: reinstale o Python e marque `"Add python.exe to PATH"`, ou digite `py` em vez de `python`. Linux / macOS: digite `python3`.
* **`"No module named cv2"` / `"numpy"` / `"matplotlib"`**
  Execute novamente: `python -m pip install numpy matplotlib opencv-python`
* **`"No module named scanner_config"` (ou `detect_line`, `laser_sim`, `mesh`)**
  Os arquivos não estão todos na mesma pasta, ou o terminal não está aberto dentro dessa pasta. Veja 1.3 e 1.5.
* **A janela do visualizador não abre**
  Use `--save`, veja a Parte B.
* **Os números diferem ligeiramente deste guia**
  Normal: as fotos falsas contêm ruído aleatório. Diferenças grandes (erros acima de $1\text{ mm}$) não são normais; verifique se `scanner_config.py` não foi editado.

## LISTA DE ARQUIVOS

| Arquivo | Parte | Descrição |
| :--- | :--- | :--- |
| `GUIDE.txt` / `.md` | Geral | Este guia passo a passo |
| `mesh.py` | Parte A | Fatias $\rightarrow$ malha `.obj` |
| `viewer.py` | Parte B | Visualizar um arquivo `.obj` |
| `scanner_config.py` | Parte C | Números de câmera/calibração |
| `laser_sim.py` | Parte C | Gerador de fotos falsas |
| `detect_line.py` | Parte C | Detector da linha do laser |
| `test_detector.py` | Parte C | Teste com números de erro + `detector_demo.png` |
| `try_detector.py` | Parte C-2 | Teste prático com opções $\rightarrow$ `try_result.png` |
| `simulate_scan.py` | Parte D | Escaneamento simulado completo $\rightarrow$ `scan.obj` + `scan_preview.png` |
| `calibrate.py` | Parte E | Mede os 4 números da câmera a partir de fotos |
| `plane_map.py` | Parte F | Mapa de perspectiva para câmera inclinada $\rightarrow$ `camera_map.json` |
| `cleanup.py` | Parte G | Remove pontos errados / preenche buracos em um escaneamento |
| `glitches.py` | Parte G | Reflexos, sombras e fotos mortas falsas (para teste) |
| `test_cleanup.py` | Parte G | Teste com números de erro + `cleanup_demo.png` |
| `scan_folder.py` | Parte H | Pasta de pares de fotos $\rightarrow$ `.obj` (o programa para fotos reais) |
| `test_scan_folder.py` | Parte H | Teste em objetos de diferentes alturas |
| `capture.py` | Parte I | Tira os pares de fotos (laser, câmera, plataforma) |
| `test_capture.py` | Parte I | Testa o `capture.py` com substitutos, sem hardware |
| `pi_server.py` | Parte J | Servidor no Pi (ordens, escaneamentos, testes, scans antigos) |
| `scanner_page.html` | Parte J | A página web (servida por `pi_server.py`: mantenha AO LADO dele) |
| `export_stl.py` | Parte J | `.obj` $\rightarrow$ `.stl` (usado por `pi_server.py`: mantenha ao lado dele) |
| `pc_client.py` | Parte J | Cliente de linha de comando para o servidor (opcional) |
| `test_remote.py` | Parte J | Testes do servidor + cliente (79 verificações) |
| `test_web.py` | Parte J | Testes da página web em um navegador real (precisa do Playwright) |
| `test_stl.py` | Parte J | Testes do `export_stl.py` |
| `exemplos/` | Geral | Imagens às quais o guia se refere (não são necessárias para rodar nada) |

> **MANTENHA APENAS UMA CÓPIA DE CADA ARQUIVO.** Se o seu navegador salvou o mesmo arquivo várias vezes (`capture (1).py`, `capture (2).py` ...), apenas o mais recente é o correto e os outros podem ser apagados; o nome sem o número **NÃO** é necessariamente o mais novo (renomeie o mais recente para o nome original sem número). Os programas só precisam dos arquivos `.py` e de `scanner_page.html` na **MESMA** pasta. Os arquivos que os programas geram (`.obj`, `scan_preview.png`, `try_result.png`, `camera_map.json` ...) podem ser apagados a qualquer momento; a pasta `__pycache__` também.
