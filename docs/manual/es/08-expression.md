# Pedales de expresión

[English](../en/08-expression.md) · **Español**

Se pueden conectar dos pedales de expresión a los jacks de 6,3 mm de la pedalera. Cada uno envía un CC por su propio canal, con los extremos calibrados y una curva de respuesta. Además, cada uno puede servir de par de pulsadores extra, encender y apagar un wah por sí solo y enviar algo distinto en cada banco. Un jack también puede llevar una [caja de hasta tres pulsadores](#una-caja-de-pulsadores-en-el-jack) en lugar de un pedal.

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
| Canal | `Channel` | 1–16, o Global para usar **MIDI channel** (`MIDI_Channel`) de la pestaña Global. El canal que dé un banco al pedal, o un comando `Exp`, gana a este, y `Global_Channel`, si está puesto, a todos. |
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

## Velocidad de los LFO y las secuencias

Un pedal puede no enviar nada de MIDI y marcar en cambio la velocidad de la modulación de la propia pedalera: todos los [LFO](07-tempo.md#lfo-sincronizado-al-tempo) y [secuencias por pasos](07-tempo.md#secuenciador-por-pasos) en marcha lo siguen, un trémolo que pasa de lento a rápido bajo tu pie, siempre a tempo.

Se pone ahí de tres maneras:

- **Output** `Speed` en la pestaña Expression, para siempre;
- `Speed` como CC del pedal en un banco, en la pestaña Banks (`Exp1_CC` o `Exp2_CC` en [BankExpression_Settings](#bankexpression_settings)), para ese banco;
- un [comando `Exp`](06-commands.md#cambiar-el-destino-de-un-pedal-de-expresión) con `KeyMode` `Speed`, desde un botón.

Cómo se comporta:

- El talón es lo más lento y la punta lo más rápido, y cada posición intermedia es una división de nota, de cuatro compases a un tresillo de semicorchea, así que la velocidad nunca se sale de tempo.
- El rango de salida lo acota: cada división ocupa su parte de 0–127, como en la tabla de abajo, así que `Out_Min` 37 y `Out_Max` 118 van de una blanca en el talón a una semicorchea en la punta.
- Todos los LFO y secuencias van a la división del pedal, los que ya suenan y los que arrancan mientras el pedal está en Speed, sea cual sea la división de su propio comando. Cada uno sigue desde donde está en su ciclo, solo que más rápido o más lento, así que el sonido no salta.
- El pedal toma el control en su primer movimiento, como en cualquier cambio de destino. Llevarlo a otro sitio, con un cambio de banco o un `Exp`, devuelve a cada LFO y secuencia su propia división.
- La pantalla enseña la división un momento, `Sp 1/8`.
- La curva, Invert, los pulsadores de punta y talón y el auto-engage funcionan igual que antes.

| Rango del pedal | División |
|---|---|
| 0–9 | `4/1` |
| 10–18 | `2/1` |
| 19–27 | `1/1` |
| 28–36 | `1/2.` |
| 37–45 | `1/2` |
| 46–54 | `1/4.` |
| 55–63 | `1/2T` |
| 64–73 | `1/4` |
| 74–82 | `1/8.` |
| 83–91 | `1/4T` |
| 92–100 | `1/8` |
| 101–109 | `1/8T` |
| 110–118 | `1/16` |
| 119–127 | `1/16T` |

En el banco 6 de la demo, el pedal 1 marca la velocidad de TREM y del arpegio que suena al mantener STRT, de `1/2` a `1/16`.

*Firmware 0.70 o posterior; un firmware anterior envía en su lugar el CC propio del pedal.*

<details><summary>Por dentro</summary>

Se guarda en el byte 15 del registro de cada pedal: 0 para CC, 1 para Pitch Bend, 2 para CC de 14 bits, 3 para Speed, 4 para Wheel y 5 para Arrows, donde las herramientas antiguas escribían un cero.

</details>

## Hacer scroll en el ordenador

Un pedal puede ir pasando la letra, una partitura o un teleprompter en el ordenador sin usar las manos: cuanto más lo pisas, más rápido va la página, y al volver al talón se para. No envía MIDI; el pedal teclea en el ordenador como los [comandos de teclado](06-commands.md).

Hace scroll de una de dos maneras:

- `Arrows` pulsa la flecha abajo. Va a la ventana que está delante, como un teclado. **La que hay que usar en un Mac.**
- `Wheel` gira una rueda de ratón. Va a la ventana que hay bajo el puntero, aunque haya otra delante. Bien en Windows. macOS acelera la rueda según lo seguido que gira, así que allí apenas se mueve por debajo de la mitad y se dispara pasada la mitad.

Se pone igual que Speed:

- **Output** `Wheel` o `Arrows` en la pestaña Expression, para siempre;
- `Wheel` o `Arrows` como CC del pedal en un banco, en la pestaña Banks, para ese banco: un banco para la letra de cada canción;
- un [comando `Exp`](06-commands.md#cambiar-el-destino-de-un-pedal-de-expresión) con `KeyMode` `Wheel` o `Arrows`, desde un botón: con toggle, enciende y apaga el scroll.

Cómo se comporta:

- En el talón no se mueve nada. A partir de ahí acelera poco a poco, así que el primer tramo va despacio: a un cuarto del recorrido da un paso por segundo, a la mitad cinco y en la punta veinte.
- Sigue mientras el pedal está quieto: déjalo donde lo pida la canción.
- Un rango con el valor de punta por debajo del de talón hace scroll hacia arriba, con la flecha arriba o la rueda al revés. `Out_Min` 127 y `Out_Max` 0 suben a toda velocidad.
- Un rango más corto limita la velocidad: `Out_Min` 0 y `Out_Max` 64 llegan a cinco pasos por segundo en la punta.
- En un Mac con desplazamiento natural (lo normal), `Wheel` sube donde en otros baja; dale la vuelta al rango.
- La curva, Invert, los pulsadores de punta y talón y el auto-engage funcionan igual que antes, y el scroll no deja que la pedalera se duerma.

En el banco 5 de la demo, una doble pulsación en PLAY pone el pedal 1 en `Arrows`, y otra le devuelve su CC.

*Firmware 0.95 o posterior; un firmware anterior envía en su lugar el CC propio del pedal.*

<details><summary>Por dentro</summary>

Output 4 es Wheel y 5 Arrows; en un banco o un comando `Exp`, 0x84 y 0x85. La rueda es un tercer informe del teclado USB de la pedalera, un ratón que solo tiene rueda (informe 3). Sale un paso cada 806450 / d² ms, siendo d lo lejos que está el pedal de su valor de talón, 0–127, y nada por debajo de 3.

</details>

## Pulsadores de punta y talón

Un pedal puede darte dos pulsadores más sin dejar de enviar su CC: llegar a la punta pulsa un botón y volver al talón pulsa otro.

En la pestaña Expression, elige un botón de **toe** (punta) y el nivel que debe alcanzar el pedal para pulsarlo (`Toe_Button`, `Toe_Level`, por defecto 120), y un botón de **heel** (talón) y el nivel al que debe bajar (`Heel_Button`, `Heel_Level`, por defecto 7).

- El pedal pulsa un botón del **banco actual**, que envía lo que tenga configurado, estado de toggle y LED incluidos.
- Cada dirección solo se rearma cuando el pedal vuelve a pasar su nivel con cierto margen, así que quedarse justo en el borde no lo vuelve a disparar.
- Los niveles se refieren a la posición del pedal, sea cual sea su rango de salida.
- Un pedal silenciado en un banco sigue funcionando como pulsador: sus botones de punta y talón siguen funcionando.

*Firmware 0.15 o posterior.*

## Una caja de pulsadores en el jack

Un jack no necesita un pedal: una cajita de hasta tres pulsadores enchufada en su lugar le da a la pedalera tres pulsadores más, sin tocar nada por dentro. Pon el **Sends** del jack en **Switches** (`Output` `Switches`) y elige qué mantiene pulsado cada pulsador de la caja: **1**–**4**, **A**–**D**, o Bank **Down** o **Up** (`Box_1`, `Box_2`, `Box_3`).

- Un pulsador de la caja es un pulsador de la pedalera bajo otro pie: mientras lo mantienes, mantiene ese pulsador pisado, así que sus listas de pulsación corta y larga, la doble pulsación, el momentáneo al mantener y el salto de un Bank Up mantenido funcionan igual que desde la propia pedalera, en el **banco actual**. Sigue pisado mientras lo esté el de la caja: un boost, un freeze o una nota mantenidos durante toda una estrofa se mantienen (antes de 1.15 se soltaba a los 10 segundos, como una pulsación desde el ordenador).
- El jack no envía MIDI propio, y sus pulsadores de punta y talón y el auto-engage no se aplican.
- Un pulsador en **None** no hace nada.

**Cómo montar la caja.** Se cablea como un pedal de expresión, así que va en el mismo jack con el mismo cable:

- cuatro resistencias iguales, por ejemplo de 10 kΩ, en cadena entre los dos contactos a los que van los extremos del potenciómetro de un pedal;
- cada pulsador entre el tercer contacto, al que va el cursor del pedal, y una unión de la cadena: el pulsador 1 a la unión más cercana al extremo del talón, el 2 a la del medio y el 3 a la más cercana al extremo de la punta;
- y una resistencia de 100 kΩ del contacto del cursor al extremo del talón, para que sin nada pulsado el jack lea como un pedal en el talón.

Así el pulsador 1 pone el jack a un cuarto del recorrido entre talón y punta, el 2 a la mitad y el 3 a tres cuartos, y la pedalera toma el nivel más cercano. Los niveles cuentan sobre el recorrido calibrado, así que **calibra** el jack también con la caja: nada pulsado para el talón y luego el pulsador 3 mantenido para la punta. Una lectura por encima de tres cuartos, como un pedal en la punta, no pulsa nada.

Un nivel tiene que leerse igual dos veces seguidas, con unos 25 ms entre ellas, para contar, así que un contacto que rebota no pulsa nada; pasar de un pulsador a otro suelta el primero antes de pisar el segundo. Pulsar dos a la vez no está contemplado: el jack lee entonces algo intermedio.

Para probar el ajuste con un pedal de expresión, llévalo rápido a un cuarto, a la mitad o a tres cuartos de su recorrido: si lo mueves despacio, mantiene pulsado cada nivel por el que pasa.

*Firmware 1.10 o posterior. Probado con un pedal de expresión y con el pedal movido desde el ordenador; todavía no con una caja.*

<details><summary>Por dentro</summary>

El jack se lee como para un pedal, cada 24 ms más o menos con los dos jacks en uso, y la media de 16 muestras se sitúa en el recorrido calibrado, de 0 a 1024. El más cercano de 0, 256, 512 y 768 es el nivel, y una lectura por encima de 896 es el nivel 0. Un nivel mantenido es una pulsación del pulsador por la misma cola que las del pedal virtual (`sw_virtual_hold`), así que el escaneo de pulsadores lo ve como un pie; a diferencia de una pulsación desde el ordenador, no tiene el límite de 10 segundos. Se guarda en el registro de calibración del jack: `Output` 6, y los bytes 7 a 9, que un pedal usa para sus pulsadores de punta y talón, guardan lo que pulsan los de la caja: 0–7 para 1–D, 8 para Bank Down, 9 para Bank Up y 0xFF para ninguno.

</details>

## Auto-engage

Un wah que se enciende y se apaga solo, como en los equipos de Fractal y Line 6: sin tener que pisar el wah antes de usarlo.

Pon los comandos de encendido y apagado del wah en un botón toggle y elige ese botón en **Auto-engage**, en la pestaña Expression (`Auto_Button`), junto con cuánto tiempo tiene que quedarse el pedal en el talón antes de que se apague (`Auto_Off_ms`, de 10 a 2540, por defecto 500).

- Subir el pedal por encima de `Heel_Level` enciende el botón, justo antes de que se envíe el primer valor del pedal.
- Quedarse en `Heel_Level` o por debajo durante `Auto_Off_ms` lo apaga.
- El botón se pulsa como si lo pisaras, así que sus comandos, su LED y su casilla de la pantalla lo siguen.
- Lo puedes seguir pisando a mano: las dos direcciones solo actúan en el momento en que el pedal sale del talón o lleva ahí el tiempo suficiente, así que un wah que apagas a mano con el pedal arriba, o que enciendes a mano en el talón, se queda como lo dejaste.
- El botón es el mismo en todos los bancos, y no pasa nada en un banco donde no sea un toggle, así que pon el wah en el mismo botón en los bancos que lo necesiten.
- También funciona cuando un banco silencia el pedal.
- Mientras un comando `Exp` tiene el pedal en otro destino, el auto-engage no toca su botón, y tampoco mientras se ve una [página](04-banks.md#segunda-página): sus botones son de otro banco.

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
- Tras un cambio de banco, el pedal no se envía a su nuevo CC, canal o rango en la posición en la que esté parado; sigue al siguiente movimiento, salvo que [envíe al entrar en un banco](#enviar-la-posición-al-entrar-en-un-banco).
- Un [comando `Exp`](06-commands.md) en un botón puede volver a cambiar el destino hasta el siguiente cambio de banco.
- Un `Exp` en modo `Add` hace que un pedal envíe [varios CC a la vez](06-commands.md#un-pedal-a-varios-cc), cada uno con su rango y su sentido.

En la demo, el banco 2 convierte el pedal 1 en una rueda de modulación entre 20 y 100, y el banco 7 lo silencia y hace del pedal 2 un volumen por el canal 2 que nunca baja de 40, CC 7 y 39.

*Firmware 0.28 o posterior; el rango por banco necesita la 0.33.*

<details><summary>Por dentro</summary>

Las configuraciones escritas antes de la 0.28 no tienen nada guardado aquí y se comportan como si todas las casillas estuvieran vacías, y las escritas antes de la 0.33 no tienen rango aquí. El CC y el canal son cuatro bytes por banco después del setlist; la flash borrada (`0xFF`) mantiene los del propio pedal y `0x80` lo silencia. El rango es una tabla propia a continuación, de cuatro bytes por banco, así que su formato no cambia.

</details>

## Enviar la posición al entrar en un banco

Cambias de preset en el ampli y su volumen salta a lo que guardaba el preset, mientras tu pedal de volumen está en otra posición; los dos no vuelven a coincidir hasta que mueves el pedal. Marcando **Send on entering a bank** para un pedal en la pestaña Expression (`Send_On_Bank` `Y`), el pedal envía dónde está en cuanto se entra en un banco, como en las controladoras de Morningstar y Fractal, así que el preset nuevo toma el volumen de tu pie.

- Sale después de los [comandos de entrada](04-banks.md#comandos-al-entrar-y-al-salir-de-un-banco) del banco, así que un Program Change enviado ahí llega antes al aparato.
- Va a lo que el pedal envíe en el banco nuevo: su propio CC, el del banco, el de un `Exp` de la lista de entrada, y los CC que le dé un `Exp` en modo `Add`. En `Speed`, los LFO y las secuencias toman su velocidad al momento.
- Se envía aunque el banco nuevo tenga el mismo destino que el anterior.
- No sale nada en un banco que silencia el pedal, y pasar de página no envía nada, porque una página se queda con los pedales de su banco.
- Déjalo apagado en un jack sin pedal: el jack vacío se lee como el talón, y su valor de talón saldría en cada cambio de banco.
- Sin él, como siempre, el pedal sigue a su siguiente movimiento.

En la pedalera los ajustes son `EXP1SEND` y `EXP2SEND` en el [editor](10-editing-on-the-pedal.md). La demo los deja apagados, porque sus jacks pueden estar vacíos.

*Firmware 0.87 o posterior.*

<details><summary>Por dentro</summary>

Como los bytes globales y los registros de los pedales están todos ocupados, se guarda en los bits 2 y 3 del byte global 35, junto a `LED_Feedback` y `Link_Toggles`, para los pedales 1 y 2. El firmware anterior deja esos bits en paz y espera a que se mueva el pedal.

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
| `Output` | CC, PitchBend, CC14, Speed, Wheel, Arrows o Switches | Qué envía el pedal: su CC con 7 bits, Pitch Bend, una pareja de CC de 14 bits, nada más que la [velocidad de los LFO y las secuencias](#velocidad-de-los-lfo-y-las-secuencias), o [scroll en el ordenador](#hacer-scroll-en-el-ordenador); Switches para una [caja de pulsadores](#una-caja-de-pulsadores-en-el-jack) en el jack. Por defecto CC. |
| `Send_On_Bank` | Y / N | Enviar la posición del pedal al entrar en un banco, después de sus comandos de entrada. Por defecto N. Firmware 0.87. |
| `Box_1`, `Box_2`, `Box_3` | None, 1–4, A–D, Down o Up | Con `Output` Switches, el pulsador que mantiene pisado cada pulsador de la caja. Por defecto None. Firmware 1.10. |

### BankExpression_Settings

Opcional; una fila por `Bank_Number` (0–31); pueden faltar filas o venir en cualquier orden.

| Columna | Valores | Significado |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | vacío, 0–127, Off, Speed, Wheel o Arrows | El CC que envía el pedal mientras este banco está seleccionado. Vacío mantiene `Exp1_CC` / `Exp2_CC` de `Global_Settings`; Off silencia el pedal en este banco; Speed hace que marque la [velocidad de los LFO y las secuencias](#velocidad-de-los-lfo-y-las-secuencias), guardado como 0x82 (firmware 0.70); Wheel y Arrows hacen que haga [scroll en el ordenador](#hacer-scroll-en-el-ordenador), 0x84 y 0x85 (firmware 0.95). |
| `Exp1_Channel`, `Exp2_Channel` | vacío o 1–16 | Canal de ese pedal en este banco. Vacío mantiene el `Channel` del pedal de `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | vacío o 0–127 | Valores que envía el pedal en el talón y en la punta en este banco. Vacío mantiene su `Out_Min` / `Out_Max` de `Expression_Settings`; cada extremo se toma por separado. Firmware 0.33 o posterior. |

---

[← Tempo, reloj, LFO y secuenciador](07-tempo.md) · [Índice](README.md) · [La pantalla →](09-the-display.md)
