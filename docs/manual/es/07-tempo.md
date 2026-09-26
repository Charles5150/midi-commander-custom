# Tempo, reloj, LFO y secuenciador

[English](../en/07-tempo.md) · **Español**

La pedalera lleva un tempo propio: marcado con el pie, fijado por un banco al entrar en él o tomado del reloj MIDI del ordenador. Todo lo que marca el tiempo sale de él:

- el reloj MIDI que envía la pedalera, para que un delay o un looper que tengas detrás siga a tu pie;
- el LED del tap, que parpadea en cada pulso;
- los LFO, que mueven un CC arriba y abajo a tempo;
- las secuencias por pasos, que tocan un CC o una nota paso a paso.

Los comandos de tempo son comandos `Tap`, con una **Action** en el configurador (`KeyMode` en el CSV) que dice cuál: `Tap`, `Clock`, `Set`, `Up`, `Down`, `Up Repeat` o `Down Repeat`.

## Tap tempo

El botón que quiere todo el que toca con delay: lo pisas a tiempo y la pedalera coge el tempo.

Dale a un botón un comando `Tap` con **Action** `Tap`. La pedalera mide el tempo por el intervalo entre pulsaciones, promediando las cuatro últimas e ignorando lo que quede fuera de 30–300 BPM. El nuevo tempo aparece un momento en la pantalla.

El tempo no se guarda: empieza en 120 BPM cada vez que enciendes la pedalera.

## Reloj MIDI

Un comando `Tap` con **Action** `Clock` pone en marcha o para el reloj MIDI de la pedalera: MIDI Start o Stop, y después 24 bytes de reloj por negra hacia USB y DIN mientras está en marcha. El tempo aparece un momento en la pantalla, con un `*` delante mientras el reloj está en marcha.

En la demo, el banco 6 tiene tap tempo, arranque y parada del reloj y botones de transporte uno al lado del otro.

## Fijar el tempo

Cada canción tiene su tempo. Pon un comando `Tap` con **Action** `Set` en los [comandos de entrada](04-banks.md#comandos-al-entrar-y-al-salir-de-un-banco) de un banco y cada banco, o cada canción de un setlist, empieza con su tempo; en un botón, sirve para volver a un tempo conocido.

| Action | Qué hace | Valor |
|---|---|---|
| `Set` | Fija el tempo | **BPM**, 30–300, 120 si se deja vacío (`OnValue`) |
| `Up`, `Down` | Sube o baja el tempo, parando en 30 y en 300 | **Step** en BPM, 1 si se deja vacío (`OffValue`) |
| `Up Repeat`, `Down Repeat` | Lo mismo, y sigue moviéndose mientras mantienes el botón, cada vez más rápido, como se explica en [Repetir mientras se mantiene](06-commands.md#repetir-mientras-se-mantiene) | **Step**, como arriba |

- Todos muestran el nuevo tempo en la pantalla, y el reloj en marcha y el LED del tap lo siguen al instante.
- Mientras `Clock_Follow` sigue el reloj del ordenador, manda el tempo del ordenador.
- Estos botones no parpadean con el pulso.

En la demo, el banco 6 tiene BPM+ y BPM- en C y D, y mantener SYNC fija 120 BPM.

*Firmware 0.37 o posterior.*

<details><summary>Por dentro</summary>

Se guarda en el nibble bajo del comando `Tap`: 2 para `Set`, con los BPM en los bytes 2 (los 7 bits bajos) y 3 (el resto); 3 para `Up` y 4 para `Down`, con el paso en el byte 2 y su bit alto puesto para repetir. El firmware anterior a 0.37 toma los tres como un tap normal, así que actualiza antes el firmware.

</details>

## Seguir el reloj del ordenador

Cuando un DAW o un secuenciador lleva el directo, la pedalera puede tomar el tempo del ordenador. Marca **Follow the host's clock** en la pestaña **Global**, `Clock_Follow` en el CSV.

- La pedalera mide el reloj MIDI que llega por USB, durante dos pulsos, y adopta su tempo. La pantalla lo muestra como `EXT` y un tempo durante 1,5 segundos cuando engancha el reloj, o cuando su tempo cambia en dos BPM o más.
- Mientras ese reloj sigue llegando, la pedalera no envía reloj propio. Con `RealTime_Passthrough` activado, el reloj del ordenador ya llega a la salida DIN; con él desactivado, la pedalera vuelve a generar el reloj en la salida DIN al tempo del ordenador.
- Medio segundo sin reloj cuenta como parado, y el reloj propio de la pedalera, si está en marcha, sigue al tempo adoptado, así que un looper que tengas detrás no pierde el tiempo.

Ver [`Clock_Follow`](12-configuration-file.md#global_settings) en los ajustes.

## LED del tap

El LED del botón de tap parpadea en cada pulso, así que ves el tempo desde el suelo.

- Cada botón del banco actual con un comando `Tap` en modo `Tap`, en cualquiera de sus listas, hace parpadear su LED al principio de cada pulso, durante un cuarto de pulso y como mucho 100 ms, con el nivel de `LED_Brightness`.
- Un botón `Clock` parpadea igual, pero solo mientras el reloj está en marcha, así que su LED también te dice que el reloj está en marcha.
- El pulso con el que parpadea depende de dónde sale el tempo:
  - con el reloj parado, el pulso corre libre al tempo y cada tap lo vuelve a poner en fase, así que el destello cae con tu pie;
  - con el reloj en marcha, el destello es el primero de cada 24 bytes de reloj, contando desde el Start;
  - mientras `Clock_Follow` sigue el reloj del ordenador, es el pulso del ordenador, contado desde su Start.
- El destello va encima de lo que muestre el LED, así que un LED en Reverse o AlwaysOn encendido en reposo tan brillante como `LED_Brightness` no muestra destello: baja **Brightness at rest** (`LED_Rest_Brightness`) para verlo.
- Se para mientras la pedalera duerme.

**Cualquier botón puede parpadear con el pulso**, sean cuales sean sus comandos: marca **Flash at the tempo** en el editor de botones del configurador, o pon `Tempo_Flash` a `Y` en el CSV. Parpadea siempre, como un botón `Tap`, porque es decisión tuya y no del reloj. En la demo lo usa el botón B del banco 6, SYNC, un toggle de CC normal.

*Firmware 0.36 o posterior; **Flash at the tempo** 0.48 o posterior.*

<details><summary>Por dentro</summary>

`Tempo_Flash` es el bit 2 del byte de modo de LED del botón, que las configuraciones siempre han dejado a cero. El firmware anterior a 0.48 lo ignora.

</details>

## LFO sincronizado al tempo

Un trémolo, un barrido de filtro o un auto-pan que sigue tu tap o el reloj del ordenador. Un comando `LFO` no envía nada por sí mismo: convierte el comando `CC` que tiene justo debajo en un LFO. Mientras mantienes el botón, o mientras un toggle está encendido, el CC oscila solo entre su `OffValue` y su `OnValue`.

En el configurador, pon un comando `LFO` encima de un `CC` y elige:

- **Every**, lo que dura un ciclo (`OnValue` del `LFO`), una figura: `1/16T`, `1/16`, `1/8T`, `1/8`, `1/4T`, `1/8.`, `1/4`, `1/2T`, `1/4.`, `1/2`, `1/2.`, `1/1`, `2/1` o `4/1`, donde `.` es con puntillo y `T` un tresillo. `1/4` si se deja vacío.
- **Shape** (`KeyMode`), la forma de onda: `Sine`, `Triangle` y `SawUp` empiezan abajo, `SawDown` y `Square` arriba, y `Random` salta a un valor nuevo en cada ciclo. `Sine` si se deja vacío.

Cómo se comporta:

- El LFO va enganchado al pulso con el que parpadea el LED del tap, el reloj del ordenador mientras se sigue ([Clock_Follow](12-configuration-file.md#global_settings)). Los ciclos empiezan en un pulso, contando desde el pulso de la pulsación, y un tap, tempo o reloj nuevo se sigue al momento, así que un trémolo de `1/8` en un toggle siempre va a tiempo con el delay.
- Al soltar, o con la pulsación que apaga el toggle, el LFO se para y el CC recibe su `OffValue` como siempre.
- Un CC sin valor de apagado oscila desde 0. Poner `OnValue` por debajo de `OffValue` invierte la forma.
- Envía un mensaje como mucho cada 5 ms y solo cuando cambia el valor. Pueden ir ocho LFO a la vez.
- Un pedal de expresión puede marcar la velocidad con el pie: mira [Velocidad de los LFO y las secuencias](08-expression.md#velocidad-de-los-lfo-y-las-secuencias).
- Un LFO sigue funcionando al cambiar de banco, como cualquier CC que un botón deja encendido, y los que van en un toggle vuelven a arrancar al apagar y encender la pedalera.
- Una `Ramp` en el mismo canal y CC toma el relevo de un LFO, y al revés; una secuencia por pasos en él también toma el relevo. `Panic` y un cambio de configuración los paran todos.

En la demo, el banco 6 tiene TREM en A, un trémolo senoidal de `1/8` en el CC 14.

*Firmware 0.43 o posterior.*

<details><summary>Por dentro</summary>

Igual que `Wait`, un `LFO` se marca con el nibble bajo del tipo de comando vacío, 6, con el índice de la figura en el byte 2 y el de la forma en el byte 3. El firmware anterior a 0.43 ignora el `LFO` y envía el CC como siempre.

</details>

## Secuenciador por pasos

La misma idea, paso a paso: un filtro entrecortado, un arpegio, un patrón de cambios de canal del ampli, todo a tempo. Una serie de comandos `Seq` encima de un comando `CC` o `Note` toca ese comando paso a paso mientras mantienes el botón, o mientras un toggle está encendido, dando vueltas hasta que lo sueltas.

En el configurador, pon los comandos `Seq` encima del `CC` o la `Note` y rellena:

- **Steps** (`OnValue`): dos pasos por comando `Seq`, como `100 -`. Una secuencia más larga son varios comandos `Seq` seguidos, hasta nueve encima del comando que tocan, dieciocho pasos en total. Un paso es un valor 0–127, o `-` para un paso que no envía nada, así que los silencios forman parte del ritmo.
- **Every** (`KeyMode` del primer comando de la serie): lo que dura un paso, las mismas figuras que el LFO, `1/8` si se deja vacío.

Lo que significa un paso depende del comando de debajo:

- bajo un `CC`, el valor es lo que recibe el controlador;
- bajo una `Note`, es la nota que suena, con la `Velocity` del comando, y cada paso suelta la nota anterior: un arpegio.

Cómo se comporta:

- Como el LFO, va enganchado al pulso con el que parpadea el LED del tap, el reloj del ordenador mientras se sigue: el primer paso cae en el pulso de la pulsación, y un tap o tempo nuevo se sigue al momento.
- Al soltar, o con la pulsación que apaga el toggle, la secuencia se para, un CC recibe su `OffValue` como siempre y la nota que suena se suelta.
- Un pedal de expresión en Speed marca cuánto dura un paso, como marca el ciclo de un LFO: mira [Velocidad de los LFO y las secuencias](08-expression.md#velocidad-de-los-lfo-y-las-secuencias).
- Pueden ir cuatro secuencias a la vez. Siguen funcionando al cambiar de banco, y las que van en un toggle vuelven a arrancar al apagar y encender la pedalera.
- Una `Ramp` o un `LFO` en el mismo canal y CC ceden el paso a una secuencia. `Panic` y un cambio de configuración las paran todas.

En la demo, mantener STRT en el banco 6 toca un arpegio de cuatro notas.

*Firmware 0.52 o posterior.*

<details><summary>Por dentro</summary>

`Seq` se marca con el nibble bajo del tipo de comando vacío, 10, con la figura en el byte 1 y los dos pasos en los bytes 2 y 3, `0xFF` donde termina la secuencia, así que la disposición no cambia. El firmware anterior a 0.52 ignora los comandos `Seq` y envía el comando de debajo como siempre.

</details>

---

[← Comandos](06-commands.md) · [Índice](README.md) · [Pedales de expresión →](08-expression.md)
