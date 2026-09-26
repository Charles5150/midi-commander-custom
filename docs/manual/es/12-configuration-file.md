# El archivo de configuración

[English](../en/12-configuration-file.md) · **Español**

Una configuración es un CSV con varias secciones, cada una introducida por una línea que empieza por `*` y el nombre de la sección. Las líneas que contienen `#` son comentarios. El configurador lee y escribe este formato, y también lo puedes editar en una hoja de cálculo.

| Sección | Qué contiene | Se explica en |
|---|---|---|
| `Global_Settings` | Los ajustes de toda la pedalera | [más abajo](#global_settings) |
| `Bank_Naming` | El nombre y la línea de información de cada banco | [Bancos](04-banks.md#bank_naming) |
| `Button_Settings` | La etiqueta, la luz, las opciones y los comandos de pulsación corta de cada botón | [Botones](05-buttons.md#button_settings), [Comandos](06-commands.md) |
| `LongPress_Settings`, `DoublePress_Settings` | Los comandos de pulsación larga y doble | [Botones](05-buttons.md#longpress_settings) |
| `Combo_Settings` | Dos pulsadores pisados a la vez | [Botones](05-buttons.md#combo_settings) |
| `SysEx_Strings` | Dieciséis mensajes SysEx guardados | [Comandos](06-commands.md#sysex_strings) |
| `BankEnter_Settings` | Lo que envía cada banco al entrar y al salir | [Bancos](04-banks.md#bankenter_settings) |
| `BankSwitch_Settings` | Lo que envían Bank Up y Bank Down | [Bancos](04-banks.md#bankswitch_settings) |
| `Setlist` | El orden que siguen Bank Up / Down | [Bancos](04-banks.md#setlist) |
| `Expression_Settings`, `BankExpression_Settings` | Los dos pedales de expresión, y por banco | [Pedales de expresión](08-expression.md) |

## La configuración de demostración

**`python/demo-all-features.csv`** es la referencia: una configuración que usa todas las funciones, con un banco por función y etiquetas en los botones que dicen qué hace cada uno. Cárgala en el configurador para ver cómo está montada cualquier cosa, o flashéala para probar todo el firmware en la pedalera.

| Banco | Qué enseña |
|---|---|
| 0 | Un índice de comandos `Bank` que saltan a los demás bancos |
| 1 | Una distribución de looper: toggles de CC, los cuatro botones de pista como grupo exclusivo y una pulsación larga en un botón |
| 2 | Los tres modos de LED uno al lado del otro, y momentáneo frente a toggle |
| 3 | Program Change, con y sin Bank Select, y un patch seleccionado al entrar |
| 4 | Teclas del teclado: sencillas, con modificadores, mantenidas y una combinación Down/Up |
| 5 | Teclas multimedia; si las mantienes, los mismos botones controlan una grabadora, con MMC, Song Select y Song Position |
| 6 | Tap tempo, arranque y parada del reloj, transporte, BPM arriba y abajo (mantén SYNC para 120 BPM), TREM, un trémolo en el CC 14 que sigue el tempo, y un arpegio de cuatro notas manteniendo STRT |
| 7 | CC relativo, arriba y abajo, con y sin vuelta, VOL+ y VOL- que se repiten mientras se mantienen, y dos rampas de CC: un swell en toggle y una subida momentánea |
| 8 | Mensajes SysEx guardados, incluida una entrada vacía que no envía nada; un WAH en D que el pedal 1 enciende y apaga solo; VOL en C, que convierte el pedal 1 en pedal de volumen (CC 7) mientras está encendido; y P2 X en B, que silencia el pedal 2 mientras está encendido |
| 9 | Notas y pitch bend, con duraciones y toggles |
| 10 | Navegar entre bancos desde botones, absoluta y relativa; B, PREV, vuelve al banco de donde venías |
| 11 | Varios comandos encadenados en un botón, pulsación corta frente a larga, un botón de ciclo que recorre cuatro canales de ampli (D) y un boost que se enclava con un toque y es momentáneo si lo mantienes (4). Al entrar en el banco se envía CC 59 127 y al salir CC 59 0; mantener A silencia los canales 1, 2 y 3 con un solo CC |
| 12–29 | Un setlist: cada banco selecciona su patch al entrar y tiene controles de looper. En la canción 1 (banco 12), D es PG 2, que muestra el banco 31 como su segunda página; en las demás canciones D es un botón global, el tap del banco 30 |
| 30 | El banco reservado para los botones globales (`Global_Bank`): el tap en D, un toggle de mute en C y HOME en A. También las listas que ejecutan las dos combinaciones: un toggle de afinador en B (CC 68) y el borrado del looper en 4 (CC 5) |
| 31 | La segunda página de la canción 1: siete toggles, FX1 a FX7 en los CC 60–66, y BACK en D. Al entrar en la página se envía CC 70 127 y al volver CC 70 0 |

Los dos pedales de expresión están configurados, uno lineal y otro logarítmico e invertido, con la punta y el talón funcionando como pulsadores. El pedal 1 activa solo el botón D, el WAH del banco 8 (y TRK4 en el banco 1), y lo apaga tras 600 ms en el talón. El pedal 2 envía una pareja de CC de 14 bits, CC 4 y 36. Los CC 102–111 por el canal 16 pulsan los diez pulsadores desde el ordenador. Los pulsadores 3 y 4 pisados a la vez activan y desactivan el afinador en todos los bancos, salvo en la canción 1, donde la misma pareja borra el looper. El banco 2 convierte el pedal 1 en una rueda de modulación entre 20 y 100, y el banco 7 lo silencia y hace del pedal 2 un volumen por el canal 2 que nunca baja de 40, CC 7 y 39. Regenera el archivo con `python3 python/make_demo_config.py` después de añadir una función, para que siga cubriéndolo todo.

(`python/MeloConfig_10_Cmds - RC-600.csv` es una configuración real para una Boss RC-600. La plantilla de Google Sheets del proyecto original ya no está en línea, y además era anterior a varias columnas; empieza mejor por uno de los CSV.)

## Global_Settings

Los ajustes de toda la pedalera, como filas `Label,Value`. En el configurador son la pestaña **Global**, en los mismos grupos que aquí abajo: cada ajuste aparece ahí con el nombre de la segunda columna, y debajo, en letra pequeña, su etiqueta del CSV.

### Configuración

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `ConfigName` | Configuration name | hasta 16 caracteres | Se muestra en la pantalla al arrancar. |
| `Boot_Banner` | Banner at power on | Off / Slow / Normal / Fast | Al encender, el `ConfigName`, o el [texto propio](09-the-display.md#el-texto-propio-del-banner) de la pedalera si tiene uno, y la versión de firmware cruzan la pantalla una vez en letra grande, de derecha a izquierda, en lugar del nombre bajo la animación de arranque: a unos 37, 74 o 110 píxeles por segundo, unos cuatro segundos para un nombre completo en Normal. La pedalera funciona todo el rato: cualquier pulsador, o una pulsación desde el ordenador, lo corta en el acto y hace lo de siempre, y la pantalla del banco vuelve por debajo con lo que haya cambiado mientras tanto. El modo seguro se muestra encima. Por defecto Off. Necesita firmware 0.62 (byte global 46); un firmware anterior muestra el nombre como antes. |
| `MIDI_Channel` | MIDI channel | 1–16 | Canal que usan los pedales de expresión (salvo que un pedal tenga el suyo). Los botones usan el canal de cada comando. |
| `Global_Channel` | Global channel | Off / 1–16 | Lleva toda la configuración a un solo canal: todos los mensajes salen por él en lugar del canal guardado en cada comando, pedales incluidos. Off deja cada comando en el suyo. Un comando `Chan` nombra sus canales a propósito, así que no se toca. Por defecto Off. |
| `Exp1_CC`, `Exp2_CC` | Expression pedal 1 CC, Expression pedal 2 CC | 0–127 | Número de CC que envía cada pedal de expresión. Por defecto 11 y 4. |

### Pulsaciones

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `Long_Press_ms` | Long press after | 100–2500 | Tiempo que hay que mantener para que una pulsación sea larga, en los botones de comandos y en Bank Up / Down. Por defecto 500. |
| `Double_Press_ms` | Double press within | 100–1000 | Tiempo que puede tardar la segunda pulsación de una pulsación doble. Un botón con comandos de pulsación doble en el banco actual espera este tiempo tras un toque antes de enviar su pulsación corta. Por defecto 300. |
| `Combo_ms` | Two switches together within | 20–250 | Cuánto espera un pulsador de una [combinación](05-buttons.md#combo_settings) a que llegue el otro. Solo esperan los pulsadores que forman parte de una combinación en el banco actual, y solo este tiempo, antes de hacer lo que hacen por separado. Por defecto 80, que un pie sobre dos pulsadores consigue sin problema. |
| `Remember_State` | Remember state | Y / N | Arrancar en el último banco con todos los toggles como estaban. |
| `Edit_Lock` | Lock on-pedal editing | Y / N | Impide que los dos pulsadores de banco mantenidos a la vez abran el [editor de la pedalera](10-editing-on-the-pedal.md), para una pedalera que no debe cambiar bajo el pie de nadie. Solo se puede desbloquear desde aquí, o durante una sesión arrancando en [modo seguro](10-editing-on-the-pedal.md#modo-seguro). Por defecto N. |

### LEDs

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `LED_Brightness` | Brightness | 1–100 | Brillo de un LED encendido, en porcentaje. Por defecto 100. Las configuraciones escritas antes de la 0.9 se leen como 100. |
| `LED_Rest_Brightness` | Brightness at rest | 1–100 | Brillo de los LEDs encendidos en reposo por los modos Reverse y AlwaysOn. Por defecto 100; bájalo para distinguir un botón activo de uno en reposo. |
| `Bank_Up_LED_Mode`, `Bank_Down_LED_Mode` | Bank Up LED, Bank Down LED | Normal / Reverse / AlwaysOn | Comportamiento del LED de los pulsadores de banco (mira [Modos de LED](05-buttons.md#modos-de-led)). |
| `LED_Feedback` | Follow the computer | Y / N | Un Control Change, Note On o Note Off que llega por USB pone en el estado que describe a todos los toggles cuyo comando `CC` o `Note` tenga el mismo canal y número: su LED, su casilla de la pantalla y lo que enviará su siguiente pulsación lo siguen. Se actualizan todos los bancos, y también la lista de pulsación larga. Un CC cuenta como «on» cuando su valor está más cerca del `OnValue` del comando que de su `OffValue`; un comando sin `OffValue` solo reacciona a su `OnValue`. Un Note On con velocidad es «on», y un Note Off o velocidad 0 es «off». Solo cambia el estado: no se envía nada, así que un ordenador que devuelve como eco los mensajes de la pedalera no provoca ningún bucle. Mientras duerme se guarda el estado, y los LEDs vuelven bien al despertar. Una lista con un comando [`Listen`](06-commands.md#escuchar-otro-cc) sigue a ese en su lugar, esté activado o no. Por defecto N. |

### Bancos

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `Bank_Switch_Mode` | Bank switches | Bank / Bank+MIDI / MIDI only | Qué hacen los pulsadores Bank Up / Down. `Bank` es el comportamiento original: solo cambian de banco. `Bank+MIDI` además envía sus comandos de `BankSwitch_Settings`. `MIDI only` hace que dejen de cambiar de banco, y queda una controladora de diez pulsadores. Por defecto `Bank`. |
| `Bank_Jump_Step` | Long press jumps | 1–31 | Bancos que salta una pulsación larga en Bank Up / Down. Por defecto 8. |
| `Bank_Preview` | Preview banks | 0–60 | Bank Up / Down solo enseñan el banco. Una pulsación, o una pulsación larga, mueve un candidato igual que movería el banco, setlist incluido, y la pantalla muestra el nombre de ese banco invertido, blanco con letras negras, sobre las etiquetas de sus botones; no se envía nada, ni los comandos del banco ni los del propio pulsador de banco. El primero de los ocho botones que baja lo confirma: la pedalera va allí, el banco que dejas envía su lista de salida y el banco al que entras su lista de entrada, y esa pulsación no hace nada más, ni al pisar ni al soltar. Los comandos propios de los pulsadores de banco de `BankSwitch_Settings` no se envían con la vista previa activada. Volver al banco en el que estás quita la vista previa, y también dejarla ese número de segundos sin tocar un botón: vuelve a verse en pantalla el banco en el que estás. Un cambio de banco por MIDI, o abrir el editor, también la quitan. Los avisos del tempo y los textos del ordenador esperan a que termine. Con `Bank_Switch_Mode` en MIDI only los pulsadores de banco no cambian de banco, así que no hay nada que enseñar. 0 es desactivado, el valor por defecto. Necesita firmware 0.66 (byte global 47). |
| `Setlist_Mode` | Follow the setlist | Y / N | Bank Up / Down, y los comandos `Bank` relativos, siguen el orden de la sección `Setlist` en lugar de los números de banco. Desde un banco que no está en la lista, Up entra por su primera entrada y Down por la última. `GoTo` y la selección de banco por MIDI entrante siguen yendo al banco exacto. Por defecto N. |
| `Bank_Change_Mode` | Change bank from MIDI | Off / PC / CC | Deja que un Program Change, o un Control Change, que llega elija un banco. |
| `Bank_Change_Channel` | … listening on channel | Any / 1–16 | Canal en el que la pedalera escucha esos mensajes. |
| `Bank_Change_CC` | … with CC number | 0–127 | Número de CC que elige un banco, cuando el modo es CC. Su valor es el banco. |
| `Global_Bank` | Global buttons bank | Off / 0–31 | El banco reservado para los botones globales: un botón marcado `Global` en cualquier otro banco toma sus listas de comandos, su etiqueta, su luz y su estado del mismo botón de este. Mira [Botones globales](05-buttons.md#botones-globales). Por defecto Off, sin redirigir nada. |

### USB MIDI

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `USB_MIDI_Thru` | USB to DIN thru | Y / N | Reenvía a la salida DIN todos los demás mensajes MIDI que llegan por USB (notas, CC, PC, pitch bend, system common, SysEx de otros aparatos). |
| `RealTime_Passthrough` | Clock and transport thru | Y / N | Reenvía a la salida DIN el MIDI Clock, Start, Continue y Stop que llegan por USB. |
| `Clock_Follow` | Follow the host's clock | Y / N | Mide el reloj MIDI que llega por USB, durante dos tiempos, y adopta su tempo; la pantalla lo muestra como `EXT` y un tempo durante 1,5 segundos cuando engancha el reloj o su tempo cambia dos BPM o más. Mientras ese reloj sigue llegando, la pedalera no envía reloj propio: con `RealTime_Passthrough` activado el reloj del ordenador ya llega a la salida DIN, y con él desactivado la pedalera vuelve a generar el reloj en la salida DIN al tempo del ordenador. Medio segundo sin reloj cuenta como parado, y el reloj propio de la pedalera, si estaba en marcha, sigue al tempo adoptado. Por defecto N. |
| `Remote_Mode` | Press from the computer | Off / CC / Note | Deja que el ordenador pise los pulsadores. Diez números seguidos a partir de `Remote_First` corresponden a 1, 2, 3, 4, A, B, C, D, Bank Down y Bank Up. Un CC de 64 o más, o un Note On, mantiene el pulsador pisado; un CC por debajo de 64, un Note Off o un Note On con velocidad 0 lo suelta. La pulsación va por el mismo camino que la de un pie, así que mantener da una pulsación larga, dos toques rápidos una doble, y Bank Up / Down siguen `Bank_Switch_Mode` y el setlist. Un ordenador que solo envía la pulsación, nunca la suelta, deja el pulsador pisado hasta que se suelta solo pasados 10 segundos, así que envía las dos cosas. Los mensajes que se usan así no van más allá: ni a la salida DIN, ni a `LED_Feedback`, ni a la selección de banco. Por defecto Off. |
| `Remote_Channel` | … listening on channel | Any / 1–16 | Canal en el que la pedalera escucha esos mensajes. Mantenlo aparte de los canales por los que envían los botones si `LED_Feedback` está activado. |
| `Remote_First` | … from number | 0–118 | Número de CC o de nota del pulsador 1; los otros nueve van a continuación. Por defecto 102, o sea CC 102–111, números que por convención no usa ningún aparato. |
| `Kemper_Mode` | Talk to a Kemper | Y / N | Habla con un Kemper Profiler en las dos direcciones: la pedalera le pide al ampli que informe de sí mismo y sigue lo que le llega, con el rig en el que estás escrito junto al nombre del banco y los módulos de efectos encendiendo los botones que los activan. Mira [Kemper en las dos direcciones](11-devices.md#kemper-en-las-dos-direcciones). Por defecto N; activado en la plantilla del Kemper Player. |

### Alimentación

| Etiqueta | En el configurador | Valores | Qué hace |
|---|---|---|---|
| `Sleep_After_Min` | Sleep after | 0–60 | Minutos sin actividad antes de que se apaguen la pantalla y los LEDs. 0 lo desactiva. Una pulsación o un pedal de expresión que se mueve la despiertan, y además hace lo que se le pidió. |

---

[← Plantillas y equipos](11-devices.md) · [Índice](README.md) · [Herramientas de línea de comandos →](13-command-line-tools.md)
