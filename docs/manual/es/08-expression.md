# Pedales de expresión

[English](../en/08-expression.md) · **Español**

Se pueden conectar dos pedales de expresión a los jacks de 6,3 mm de la pedalera. Cada uno envía un CC por su propio canal, con los extremos calibrados y una curva de respuesta. Además, cada uno puede servir de par de pulsadores extra, encender y apagar un wah por sí solo y enviar algo distinto en cada banco.

## Conectar y calibrar

Todo lo de los pedales está en la pestaña **Expression** del configurador, con un panel por pedal.

1. Conecta la pedalera por USB y pulsa **Connect live view**. Muestra la posición del pedal y el CC que se envía, leídos de la pedalera en tiempo real.
2. Pulsa **Calibrate**, mueve el pedal despacio de talón a punta y vuelta un par de veces, y pulsa **Done**.
3. Los extremos se rellenan con un pequeño margen, para que siempre se lleguen a alcanzar 0 y 127.

**Si un pedal no genera ningún CC**, abre la pestaña Expression y pulsa **Connect live view**:

- si el valor en bruto no sigue al pedal, el problema es el cable o el jack;
- si lo sigue pero no llega ningún CC a tu monitor MIDI, revisa el canal y el número de CC, y los ajustes propios del banco (mira [Otro destino en cada banco](#otro-destino-en-cada-banco)).

*Calibración: firmware 0.8 o posterior.*

<details><summary>Por dentro</summary>

Los dos jacks se leen con el ADC uno detrás de otro. Entre lectura y lectura cada pin se lleva a masa, para evitar diafonía entre las dos entradas y para que un jack vacío lea cero; cada lectura se toma 12 ms después de soltar su pin, mientras el resto de la pedalera sigue a lo suyo. Las lecturas se suavizan con un filtro adaptativo y una pequeña histéresis, para que un pedal en reposo no baile. Solo se envía un CC cuando cambia su valor de 7 bits.

</details>

## Qué envía cada pedal

| Ajuste | En el CSV | Qué hace |
|---|---|---|
| **Expression pedal 1 CC**, **2 CC** (pestaña Global) | `Exp1_CC`, `Exp2_CC` | El CC que envía cada pedal. Por defecto 11 y 4. |
| Canal | `Channel` | 1–16, o Global para usar **MIDI channel** (`MIDI_Channel`) de la pestaña Global. |
| Curva | `Curve` | Linear, Log o Exp. Log va rápida al principio del recorrido y Exp va lenta al principio. |
| Invertir | `Invert` | Intercambia talón y punta. |

## Rango de salida

Un pedal puede enviar solo parte del rango: de 40 a 127 para un pedal de volumen que nunca llega al silencio, por ejemplo, o de 127 a 0 para darle la vuelta sin tocar Invert.

Pon el **output range** (rango de salida) en la pestaña Expression (`Out_Min` y `Out_Max`, por defecto 0 y 127).

- El recorrido del pedal, después de la curva y de Invert, se reparte entre `Out_Min` en el talón y `Out_Max` en la punta.
- Los extremos se alcanzan siempre exactamente.
- `Toe_Level` y `Heel_Level` siguen refiriéndose a la posición del pedal, de 0 a 127, envíe lo que envíe.
- Un banco puede cambiar cualquiera de los dos extremos; mira [Otro destino en cada banco](#otro-destino-en-cada-banco).

*Firmware 0.33 o posterior; un firmware anterior ignora el rango.*

<details><summary>Por dentro</summary>

Se guarda en dos bytes que estaban reservados en el registro de cada pedal, los bytes 11 y 12, donde las herramientas antiguas escribían ceros: el firmware 0.33 lee 0 y 0 como el rango completo, así que las configuraciones antiguas no cambian.

</details>

## Pitch Bend y CC de 14 bits

Un pedal puede enviar Pitch Bend, para un whammy, o una pareja de CC de 14 bits, con 16384 pasos en lugar de 128, para barridos sin escalones en sintes y plugins que los entienden.

Elige qué envía con **Output** en la pestaña Expression (`Output`: `CC`, `PitchBend` o `CC14`; por defecto CC).

- **PitchBend** envía Pitch Bend por el canal del pedal en lugar de su CC.
- **CC14** envía una pareja de CC de 14 bits: los 7 bits altos en su CC y los 7 bajos en ese CC más 32, como los empareja el estándar MIDI. Así, el CC 4 sale como CC 4 y CC 36, primero el byte alto.
- Los dos tienen 16384 pasos en lugar de 128, y el pedal envía cada paso fino que es capaz de medir: su banda muerta contra el ruido es cuatro veces más estrecha en estos modos, y un pedal en reposo sigue sin enviar nada.
- `Out_Min` y `Out_Max` siguen contando de 0 a 127, y cada uno se toma como sus 7 bits altos, así que 64 es el centro del bend: de 64 a 127 solo sube, desde el talón en reposo, y 127 es el tope.
- La curva, Invert y los niveles de punta y talón funcionan igual que antes.
- Un banco o un comando `Exp` que lleva el pedal a otro CC envía ese CC: como pareja cuando `Output` es `CC14` y el CC es menor de 32, que es lo que necesita un CC de 14 bits, y con 7 bits en cualquier otro caso. Así, un pedal de Pitch Bend puede seguir siendo un pedal de volumen en otro banco. Un CC de 14 bits por encima de 31 también sale con 7 bits.

El pedal 2 de la demo envía una pareja de CC de 14 bits, CC 4 y 36.

*Firmware 0.44 o posterior; un firmware anterior ignora el ajuste y envía el CC.*

<details><summary>Por dentro</summary>

Se guarda en el byte 15 del registro de cada pedal: 0 para CC, 1 para Pitch Bend y 2 para CC de 14 bits, donde las herramientas antiguas escribían un cero.

</details>

## Pulsadores de punta y talón

Un pedal puede darte dos pulsadores más sin dejar de enviar su CC: llegar a la punta pulsa un botón y volver al talón pulsa otro.

En la pestaña Expression, elige un botón de **toe** (punta) y el nivel que debe alcanzar el pedal para pulsarlo (`Toe_Button`, `Toe_Level`, por defecto 120), y un botón de **heel** (talón) y el nivel al que debe bajar (`Heel_Button`, `Heel_Level`, por defecto 7).

- El pedal pulsa un botón del **banco actual**, que envía lo que tenga configurado, estado de toggle y LED incluidos.
- Cada dirección solo se rearma cuando el pedal vuelve a pasar su nivel con cierto margen, así que quedarse justo en el borde no lo vuelve a disparar.
- Los niveles se refieren a la posición del pedal, sea cual sea su rango de salida.
- Un pedal silenciado en un banco sigue funcionando como pulsador: sus botones de punta y talón siguen funcionando.

*Firmware 0.15 o posterior.*

## Auto-engage

Un wah que se enciende y se apaga solo, como en los equipos de Fractal y Line 6: sin tener que pisar el wah antes de usarlo.

Pon los comandos de encendido y apagado del wah en un botón toggle y elige ese botón en **Auto-engage**, en la pestaña Expression (`Auto_Button`), junto con cuánto tiempo tiene que quedarse el pedal en el talón antes de que se apague (`Auto_Off_ms`, de 10 a 2540, por defecto 500).

- Subir el pedal por encima de `Heel_Level` enciende el botón, justo antes de que se envíe el primer valor del pedal.
- Quedarse en `Heel_Level` o por debajo durante `Auto_Off_ms` lo apaga.
- El botón se pulsa como si lo pisaras, así que sus comandos, su LED y su casilla de la pantalla lo siguen.
- Lo puedes seguir pisando a mano: las dos direcciones solo actúan en el momento en que el pedal sale del talón o lleva ahí el tiempo suficiente, así que un wah que apagas a mano con el pedal arriba, o que enciendes a mano en el talón, se queda como lo dejaste.
- El botón es el mismo en todos los bancos, y no pasa nada en un banco donde no sea un toggle, así que pon el wah en el mismo botón en los bancos que lo necesiten.
- También funciona cuando un banco silencia el pedal.
- Mientras un comando `Exp` tiene el pedal en otro destino, el auto-engage no toca su botón.

En la demo, el pedal 1 activa solo el botón D, el WAH del banco 8 (y TRK4 en el banco 1), y lo apaga tras 600 ms en el talón.

*Firmware 0.41 o posterior.*

<details><summary>Por dentro</summary>

Se guarda en los bytes 13 y 14 del registro de cada pedal: el botón más uno y el retardo en pasos de 10 ms, donde las herramientas antiguas escribían ceros, que significan sin auto-engage.

</details>

## Otro destino en cada banco

El mismo pedal puede ser un wah en un banco y un volumen en otro, o quedarse callado donde no hace falta.

En la pestaña **Banks** del configurador, cada banco tiene por pedal un CC y un canal, cada uno en `Default` para mantener los del propio pedal, u `Off` en el CC para silenciar el pedal en ese banco; y el valor más bajo y el más alto que envía ahí, que se dejan vacíos para mantener el rango del propio pedal.

- Una casilla vacía mantiene el ajuste del propio pedal; cada extremo del rango se toma por separado.
- Un pedal silenciado sigue funcionando como pulsador: sus botones de punta y talón siguen funcionando.
- Tras un cambio de banco, el pedal no se envía a su nuevo CC, canal o rango en la posición en la que esté parado; sigue al siguiente movimiento.
- Un [comando `Exp`](06-commands.md) en un botón puede volver a cambiar el destino hasta el siguiente cambio de banco.

En la demo, el banco 2 convierte el pedal 1 en una rueda de modulación entre 20 y 100, y el banco 7 lo silencia y hace del pedal 2 un volumen por el canal 2 que nunca baja de 40, CC 7 y 39.

*Firmware 0.28 o posterior; el rango por banco necesita la 0.33.*

<details><summary>Por dentro</summary>

Las configuraciones escritas antes de la 0.28 no tienen nada guardado aquí y se comportan como si todas las casillas estuvieran vacías, y las escritas antes de la 0.33 no tienen rango aquí. El CC y el canal son cuatro bytes por banco después del setlist; la flash borrada (`0xFF`) mantiene los del propio pedal y `0x80` lo silencia. El rango es una tabla propia a continuación, de cuatro bytes por banco, así que su formato no cambia.

</details>

## En el CSV

### Expression_Settings

Opcional; dos filas, `Pedal` 1 y 2.

| Columna | Valores | Significado |
|---|---|---|
| `Min_ADC`, `Max_ADC` | 0–4095 | Lecturas calibradas de talón y punta. Por defecto 80 y 3900. |
| `Curve` | Linear / Log / Exp | Log va rápida al principio del recorrido y Exp va lenta al principio. |
| `Invert` | Y / N | Intercambia talón y punta. |
| `Channel` | Global o 1–16 | Global usa `MIDI_Channel`. |
| `Toe_Button` | None o 1–4, A–D | Botón que se pulsa cuando el pedal llega a la punta. |
| `Toe_Level` | 1–127 | Valor que tiene que alcanzar el pedal para eso. Por defecto 120. |
| `Heel_Button` | None o 1–4, A–D | Botón que se pulsa cuando el pedal vuelve al talón. |
| `Heel_Level` | 0–127 | Valor al que tiene que bajar para eso. Por defecto 7. |
| `Out_Min`, `Out_Max` | 0–127 | Valores que se envían en el talón y en la punta. Por defecto 0 y 127. |
| `Auto_Button` | None o 1–4, A–D | Botón que se enciende cuando el pedal sale del talón y se apaga tras quedarse ahí (auto-engage). |
| `Auto_Off_ms` | 10–2540 | Cuánto tiempo tiene que quedarse el pedal en el talón antes de que se apague ese botón. Por defecto 500. |
| `Output` | CC, PitchBend o CC14 | Qué envía el pedal: su CC con 7 bits, Pitch Bend o una pareja de CC de 14 bits. Por defecto CC. |

### BankExpression_Settings

Opcional; una fila por `Bank_Number` (0–31); pueden faltar filas o venir en cualquier orden.

| Columna | Valores | Significado |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | vacío, 0–127 u Off | El CC que envía el pedal mientras este banco está seleccionado. Vacío mantiene `Exp1_CC` / `Exp2_CC` de `Global_Settings`; Off silencia el pedal en este banco. |
| `Exp1_Channel`, `Exp2_Channel` | vacío o 1–16 | Canal de ese pedal en este banco. Vacío mantiene el `Channel` del pedal de `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | vacío o 0–127 | Valores que envía el pedal en el talón y en la punta en este banco. Vacío mantiene su `Out_Min` / `Out_Max` de `Expression_Settings`; cada extremo se toma por separado. Firmware 0.33 o posterior. |

---

[← Tempo, reloj, LFO y secuenciador](07-tempo.md) · [Índice](README.md) · [La pantalla →](09-the-display.md)
