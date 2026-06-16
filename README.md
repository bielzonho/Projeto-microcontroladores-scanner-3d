# EEN251 - Microcontroladores e Sistemas Embarcados
---

# Projeto Scanner 3D

Desenvolvimento de um scanner 3D com microcontroladores para digitalização de objetos físicos.

---

# T1: Base
## Diagrama de blocos inicial
![Diagrama de blocos 1](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/diagrama%20de%20blocos%20antigo.jpeg)

## Diagrama de blocos final para a base
![Diagrama de blocos 2](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/Diagrama%20de%20blocos%20T1%20rev.png)

## Fluxo
1. Botão 1 pressionado → Servo eleva a haste, display OLED indica a altura atual
2. Botão 2 pressionado → Servo rebaixa a haste, display OLED indica a altura atual
3. Botão 1 e botão 2 pressionados → Servo trava sua posição e o motor de passo realiza 2 rotações completas, display OLED indica o progresso 
4. Motor de passo para → Display OLED mostra tela DONE; Sistema encerra

## Demonstração (YouTube)
[![demo](https://img.youtube.com/vi/T0Oqt0K6fJw/maxresdefault.jpg)](https://youtu.be/T0Oqt0K6fJw)

## Fotos
![pics](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/1.jpeg)
![pics](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/2.jpeg)
![pics](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/3.jpeg)
![pics](https://github.com/bielzonho/Projeto-microcontroladores-scanner-3d/blob/main/img/4.jpeg)

# T2: Scanner
TBD

---
# Integrantes:
Joaquim Anderlini Alves da Cunha - 22.00536-6

Gabriel Giardino Sprotte - 23.00964-0

Gabriel Fernandes Sabino - 23.01062-2

Guilherme Gonsales de Sá - 23.00882-2

Thiago Espigado Miras - 22.01836-0

### Créditos
Drivers para o display OLED: https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/display/ssd1306/ssd1306.py
