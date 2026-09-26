# Editar en la pedalera

[English](../en/10-editing-on-the-pedal.md) · **Español**

Con el configurador todo es más fácil, pero el configurador no siempre está a mano: el Program Change equivocado aparece en la prueba de sonido, sin un portátil a la vista. La pedalera tiene un editor propio, en su propia pantalla, que se maneja con los pies.

## Abrirlo y cerrarlo

Mantén **Bank Down y Bank Up a la vez durante dos segundos** y la pedalera abre el editor sobre la configuración que está usando; mantener otra vez los mismos dos pulsadores lo cierra.

- Los diez LED se encienden mientras está abierto.
- Mientras está abierto, ningún pulsador envía nada, así que no puede salir nada por error.
- Si hay una [vista previa de banco](04-banks.md#vista-previa-de-banco) en pantalla, abrir el editor la quita.

## Los pulsadores

La pantalla es una lista de campos con nombre, con el cursor en uno de ellos:

| Pulsador | Qué hace |
| --- | --- |
| **1** / **2** | mueven el cursor arriba y abajo por la lista |
| **3** / **4** | cambian el valor bajo el cursor; si los mantienes, repiten y aceleran |
| **A** / **B** | pasan al comando anterior o siguiente de la lista del botón |
| **C** | envía el comando tal como está, para oírlo |
| **D** | cambia entre los comandos y los ajustes |
| **Bank Down** / **Bank Up** | pasan al banco anterior o siguiente |

## Editar los comandos de un botón

En la pantalla de comandos, los primeros campos dicen qué estás editando:

1. el banco;
2. el botón;
3. pulsación corta o larga;
4. cuál de los diez comandos.

Después vienen el tipo del comando y los campos que tiene ese tipo —canal, número de CC o de nota, valores de encendido y apagado, si hace toggle, etc.— y debajo los cuatro caracteres de la etiqueta del botón, un campo cada uno.

El editor escribe estos tipos:

`---` (sin comando), `PC`, `CC`, `Note`, `Bank`, `Tap`, `Start`, `Stop`, `Panic` y `Wait`.

Un comando de cualquier otro tipo se muestra por su nombre y se deja exactamente como está hasta que cambias el campo del tipo, que lo sustituye. Las listas de doble pulsación no aparecen: viven en una zona que las herramientas escriben de una vez.

## Editar los ajustes

**D** pasa a la pantalla de ajustes, con los ajustes globales que son un número o una opción. El resto, los que necesitan texto o una lista, se quedan para el configurador.

| En la pedalera | En el configurador (CSV) |
|---|---|
| `LONGPRES` | el tiempo de la pulsación larga (`Long_Press_ms`) |
| `DBLPRESS` | el tiempo de la doble pulsación (`Double_Press_ms`) |
| `COMBO` | el tiempo de la combinación (`Combo_ms`) |
| `BRIGHT`, `RESTBRIG` | los dos brillos de los LED (`LED_Brightness`, `LED_Rest_Brightness`) |
| `BANKJUMP` | cuánto salta una pulsación larga en Bank Up / Down (`Bank_Jump_Step`) |
| `SLEEP` | el tiempo hasta dormirse (`Sleep_After_Min`) |
| `GLOBCHAN` | el canal global (`Global_Channel`) |
| `GLOBBANK` | el banco reservado para los botones globales (`Global_Bank`), con su número tal como lo muestra el editor, 0 para ninguno |
| `BANK SW` | qué hacen los pulsadores de banco (`Bank_Switch_Mode`) |
| `PREVIEW` | el tiempo de la vista previa de banco (`Bank_Preview`) |
| `SETLIST` | seguir el setlist (`Setlist_Mode`) |
| `REMEMBER` | recordar el estado (`Remember_State`) |
| `CLOCKFLW` | seguir el reloj (`Clock_Follow`) |
| `LEDFEEDB` | LED que siguen al ordenador (`LED_Feedback`) |
| `USB THRU`, `RT THRU` | los dos thru (`USB_MIDI_Thru`, `RealTime_Passthrough`) |
| `KEMPER` | modo Kemper (`Kemper_Mode`) |
| `EXP1 CC`, `EXP2 CC` | los números de CC de los pedales de expresión (`Exp1_CC`, `Exp2_CC`) |

## Cuándo se guarda un cambio

Lo que cambias se escribe en la flash en cuanto el cursor sale del comando, la etiqueta o el ajuste, así que si te vas no pierdes nada. Una estrella en la línea del título indica que hay algo sin escribir todavía.

- Una escritura tarda una décima de segundo, durante la cual la pedalera está ocupada: cambia lo que necesites entre canciones, no en mitad de una.
- Después la pedalera vuelve a leer la configuración, así que el comando nuevo funciona al momento.
- Si vuelves a leer la configuración con `Flash_to_CSV.py`, o con **Read from Device** en el configurador, obtienes un CSV con el cambio.

*Firmware 0.53 o posterior.*

<details><summary>Por dentro</summary>

Un cambio se escribe reescribiendo la página de flash de 2 kB en la que está, y después se vuelve a construir todo lo que se deriva de la configuración.

</details>

## Bloquear el editor

Para una pedalera que no debe cambiar bajo el pie de nadie, marca **Lock on-pedal editing** en la pestaña **Global** del configurador, `Edit_Lock` en el CSV. Entonces los dos pulsadores de banco mantenidos a la vez ya no abren el editor. Solo se puede desbloquear desde el configurador, o durante una sesión desde el [modo seguro](#modo-seguro).

## Modo seguro

Para la configuración que silencia el ampli o le lía el equipo al arrancar, sin un ordenador a mano. Mantén pisado **uno cualquiera de los ocho pulsadores de comando** (1–4, A–D) mientras enciendes la pedalera, y suéltalo cuando la pantalla diga **SAFE MODE**. La pedalera arranca entonces sin enviar nada, y sigue así hasta que la apagas:

- no se ejecuta ninguna lista de entrada ni de salida de banco, ni al arrancar ni al cambiar de banco;
- el banco y los estados de toggle guardados no se recuperan, aunque `Remember_State` esté activado: arranca en el banco 0 con todo apagado;
- `Kemper_Mode` se queda desactivado, así que al ampli no le llega ni la baliza ni ninguna pregunta;
- los pedales de expresión se guardan su posición hasta que los mueves;
- el pulsador pisado al encender no cuenta como pulsación, y soltarlo no hace nada.

Todo lo demás funciona: los botones envían sus comandos, los pulsadores de banco cambian de banco, se puede grabar una configuración desde el ordenador y el [editor](#editar-en-la-pedalera) se abre incluso con `Edit_Lock` activado, así que un comando de entrada de banco equivocado se puede encontrar y cambiar desde la propia pedalera.

- Para salir del modo seguro, apaga y enciende la pedalera sin pisar nada.
- Un cambio de banco hecho en modo seguro se recuerda como siempre, así que con `Remember_State` activado la pedalera vuelve allí.
- Bank Down y D pisados a la vez al encender siguen siendo el modo DFU del bootloader, como en la pedalera de fábrica: eso no es el modo seguro.

*Firmware 0.60 o posterior.*

<details><summary>Por dentro</summary>

`GET_STATE` indica el modo seguro en su último byte (firmware 0.60).

</details>

---

[← La pantalla](09-the-display.md) · [Índice](README.md) · [Plantillas y equipos →](11-devices.md)
