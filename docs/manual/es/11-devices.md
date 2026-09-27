# Plantillas y equipos

[English](../en/11-devices.md) · **Español**

La pedalera habla con un ordenador por USB y con el resto de tu equipo por su toma MIDI OUT. Todo lo que envía un botón sale por las dos; lo que llega por USB puede cambiar de banco, encender LED, pisar pulsadores, fijar el tempo o seguir hacia la salida DIN.

![Por dónde entra y sale el MIDI](../images/midi-routes-es.svg)

Hay configuraciones listas en `python/templates/` que ponen los controles principales de un equipo bajo tus pies sin tener que configurar nada, o casi nada, en el equipo: el [Fractal FM3](#plantilla-para-fractal-audio-fm3), el [Line 6 HX Stomp](#plantilla-para-line-6-hx-stomp), el [Neural DSP Quad Cortex](#plantilla-para-neural-dsp-quad-cortex), el [Eventide H90](#plantilla-para-eventide-h90), los Strymon [TimeLine](#timeline), [BigSky](#bigsky), [Volante](#volante) e [Iridium](#iridium), el [Hotone Ampero II](#plantilla-para-hotone-ampero-ii), la [Boss RC-600](#plantilla-para-boss-rc-600) y el [Kemper Player](#plantilla-para-kemper-profiler-player), y en el ordenador [MainStage](#apple-mainstage), [Gig Performer](#gig-performer), [Cantabile](#cantabile) y [Ableton Live](#ableton-live). Para usar una, ábrela con **Load CSV** en el configurador y pulsa **Flash to Device**, o desde un terminal:

```bash
.venv/bin/python python/CSV_to_Flash.py python/templates/FM3.csv
```

Cada una la genera un script a partir del mapa MIDI del propio equipo, así que otro canal u otro CC es cambiar una constante y volver a ejecutar el script, como explica cada apartado. O cambia los botones en el configurador como en cualquier otra configuración.

## Plantilla para Fractal Audio FM3

**`python/templates/FM3.csv`** está lista para grabar y manejar una Fractal Audio FM3 por la salida DIN, y debería valer también para una Axe-Fx III o una FM9, que se configuran igual. Conecta el MIDI OUT de la pedalera al MIDI IN de la FM3 y alimenta la pedalera por USB.

| Bancos | Botones |
|---|---|
| 0–29, `P000`–`P029` | Al entrar en el banco se carga el preset de la FM3 con el mismo número. 1 2 3 4 A B son las escenas 1–6, C enclava el afinador y D marca el tap tempo |
| 30, `LOOP` | Looper: Record, Play/Stop, Undo, Once, Reverse, Half Speed, y luego afinador y tap |
| 31, `FX` | Activa y desactiva Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1 y Pitch 1 |

Bank Up / Down recorren los presets, y una pulsación larga salta diez. Los botones de escena forman un grupo exclusivo, así que el LED y la pantalla muestran la última escena elegida; pisar otra vez la que está encendida la apaga sin enviar nada. Los pedales de expresión son External 1 y 2, para asignarlos como modificador a cualquier parámetro.

La FM3 viene sin ningún CC MIDI asignado, así que en la FM3, en **SETUP > MIDI/Remote**, pon su canal MIDI en 1 y asigna:

| Página | Función | CC |
|---|---|---|
| Other | Tempo Tap | 14 |
| Other | Tuner | 15 |
| Other | Scene Select | 34 |
| External | External 1, External 2 | 16, 17 |
| Looper | Record, Play, Undo, Once, Reverse, Half Speed | 20–25 |
| Bypass | Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1, Pitch 1 | 40–47 |

Para usar otros números, u otro canal, cambia las constantes al principio de `python/make_fm3_template.py` y vuelve a ejecutarlo, o edita los botones en el configurador. Los presets por encima del 29, o de los bancos B a D de la FM3, necesitan un Program Change con `BankSelect_(PC)` a 128 veces el banco de la FM3 y `BankSelectHighByte_(PC)` a `Y`, para que el CC#0 lleve el banco.

## Plantilla para Line 6 HX Stomp

**`python/templates/HX_Stomp.csv`** está lista para grabar y manejar una Line 6 HX Stomp por la salida DIN. Conecta el MIDI OUT de la pedalera al MIDI IN de la HX Stomp y alimenta la pedalera por USB.

| Bancos | Botones |
|---|---|
| 0–29, `01A`–`10C` | Al entrar en el banco se carga el preset de la HX Stomp con el mismo nombre, de 01A a 10C. 1 2 3 son los snapshots 1–3, 4 abre y cierra el afinador, A B C pisan FS1–FS3 y D marca el tap tempo |
| 30, `LOOP` | Looper: Record, Overdub, Play/Stop, Half Speed, Play Once, Undo, Reverse, y luego tap |
| 31, `FS` | FS1–FS5, snapshot anterior y siguiente, y el afinador |

Bank Up / Down recorren los presets, y una pulsación larga salta diez. Los botones de snapshot forman un grupo exclusivo, así que el LED y la pantalla muestran el último snapshot elegido; pisar otra vez el que está encendido lo apaga sin enviar nada. FS1–FS5 funcionan como si pisaras el pulsador de la HX Stomp en modo Stomp, así que activan lo que tenga asignado, y los pedales de expresión mueven los controladores EXP 1 y EXP 2 de la HX Stomp.

La HX Stomp tiene un mapa MIDI fijo, así que no hay que asignar nada: en **Global Settings > MIDI/Tempo**, pon el MIDI Base Channel en 1 y activa MIDI PC Receive. La plantilla envía:

| Función | CC | Valores |
|---|---|---|
| EXP 1, EXP 2 | 1, 2 | los pedales |
| FS1–FS5 | 49–53 | 127 y 0, cada uno una pisada |
| Looper Record / Overdub | 60 | 127 graba, 0 sobregraba |
| Looper Play / Stop, Play Once, Undo | 61, 62, 63 | |
| Tap Tempo | 64 | 127, solo al pisar |
| Looper Reverse, Half Speed | 65, 66 | |
| Tuner | 68 | |
| Snapshot | 69 | 0–2 snapshots 1–3, 8 siguiente, 9 anterior |

Para usar otro canal, cambia `CHANNEL` al principio de `python/make_hx_stomp_template.py` y vuelve a ejecutarlo, o edita los botones en el configurador. Los presets por encima de 10C necesitan un Program Change con el número del preset, de 0 a 125.

## Plantilla para Neural DSP Quad Cortex

**`python/templates/Quad_Cortex.csv`** está lista para grabar y manejar un Neural DSP Quad Cortex por la salida DIN. Conecta el MIDI OUT de la pedalera al MIDI IN del Quad Cortex y alimenta la pedalera por USB.

| Bancos | Botones |
|---|---|
| 0–29, `P000`–`P029` | Al entrar en el banco se carga el preset con el mismo número del setlist My Presets. 1 2 3 4 A B son las escenas A–F, C abre y cierra el afinador, D marca el tap tempo |
| 30, `LOOP` | Looper X: Record / Overdub, Play / Stop, Undo / Redo, la vista del Looper X, One Shot, Half Speed, Reverse y tap |
| 31, `FS` | Los pulsadores A–H, colocados como en el Quad Cortex: A–D en la fila de abajo, E–H en la de arriba |

Bank Up / Down recorren los presets, y una pulsación larga salta diez. Los botones de escena forman un grupo exclusivo, así que el LED y la pantalla muestran la última escena elegida; pisar otra vez la que está encendida la apaga sin enviar nada. Los botones de pulsador actúan como si pisaras los del Quad Cortex, así que conmutan lo que tengan asignado en el modo en que esté, y los pedales de expresión mueven su Expression Pedal 1 y 2. El botón 4 del banco del looper abre la vista del Looper X con una pulsación y la cierra con la siguiente; One Shot, Half Speed y Reverse se encienden mientras están activos, contando desde que se abrió el looper.

El Quad Cortex tiene un mapa MIDI fijo, así que no hay que asignar nada: en **Settings > Device > MIDI**, pon su MIDI Channel en 1, u OMNI. La plantilla envía, según el manual del Quad Cortex (CorOS 4.1.1):

| Función | CC | Valores |
|---|---|---|
| Bank Select antes de cada preset | 0, 32 | 0 y 1: presets 0–127 de My Presets |
| Expression Pedal 1, 2 | 1, 2 | los pedales |
| Pulsadores A–H | 35–42 | 127 y 0, cada uno una pisada |
| Escena | 43 | 0–5, escenas A–F |
| Tap Tempo | 44 | 127, solo al pisar |
| Afinador | 45 | 127 abre, 0 cierra |
| Vista del Looper X | 48 | 0 abre, 127 cierra |
| Looper X One Shot, Half Speed, Reverse | 50, 51, 55 | 127, cada uno un cambio |
| Looper X Record / Overdub, Play / Stop, Undo / Redo | 53, 54, 56 | 127, solo al pisar |

Para usar otro canal, u otro setlist, cambia `CHANNEL` o `SETLIST` al principio de `python/make_quad_cortex_template.py` y vuelve a ejecutarlo: `SETLIST` es el LSB del Bank Select, 0 para Factory Presets, 1 para My Presets y de 2 a 12 para los setlists del usuario. Las escenas G y H son el CC 43 con 6 y 7, para cualquier botón en el configurador.

## Plantilla para Eventide H90

**`python/templates/H90.csv`** está lista para grabar y manejar un Eventide H90 por la salida DIN. Conecta el MIDI OUT de la pedalera al MIDI IN del H90 y alimenta la pedalera por USB.

| Bancos | Botones |
|---|---|
| 0–30, `P001`–`P031` | Al entrar en el banco se carga el Program 1 a 31 de la Playlist actual. 1 y 2 activan y desactivan el Preset A y el Preset B, 3 el Program entero, 4 A B son los HotSwitches 1–3, C abre y cierra el afinador, D marca el tap tempo |
| 31, `PERF` | PERFORM 1–6, los Performance Parameters del Program, y afinador y tap |

El H90 cambia cada uno de estos con un valor de 64 o más, esté como esté, así que cada pulsación envía 127 y el LED solo se va alternando: puede quedar desfasado del H90 tras cargar un Program. Los pedales de expresión mueven el HotKnob del Program y su ganancia de salida.

El H90 viene sin ningún CC MIDI asignado, así que en **System > MIDI** pon su canal MIDI en 1 y, en **Global Control**, asigna:

| Global Control | CC |
|---|---|
| P HotKnob, P Out Gain | 16, 17 (los pedales de expresión) |
| P Act/Byp, A Act/Byp, B Act/Byp | 20, 21, 22 |
| HS1, HS2, HS3 | 23, 24, 25 |
| Tuner, Tap Tempo | 26, 27 |
| PERFORM 1–6 | 40–45 |

El H90 cuenta los Program Change desde 1 de fábrica, así que el primero de la plantilla, el PC 0, es el que el H90 muestra como PC 1. Si cada banco carga el Program de al lado del que dice su nombre, cambia **PC Offset** en System > MIDI. Para usar otros números, cambia las constantes al principio de `python/make_h90_template.py` y vuelve a ejecutarlo.

## Plantillas para Strymon

Cuatro plantillas para los pedales MIDI de Strymon, cada una con el mapa MIDI propio del pedal, así que no hay que asignar nada en él. Cada una carga un preset por banco, los 30 primeros más o menos; el Strymon cuenta sus presets en bancos MIDI de 128, así que un preset por encima del 127 lleva un Program Change con `BankSelect_(PC)` a 128 por el banco MIDI y `BankSelectHighByte_(PC)` a `Y`, que envía el CC#0 con el banco, como piden los manuales.

Un Strymon carga los presets activos, así que su botón de bypass se enciende mientras está **en bypass**. El tap es el Remote Tap, CC 93, enviado solo al pisar.

### TimeLine

**`python/templates/TimeLine.csv`**, según el manual del TimeLine, rev H. Conecta el MIDI OUT de la pedalera al MIDI IN del TimeLine y, en sus Globals, pon MIDI Channel en 1 y activa MIDI Continuous Controllers y MIDI Patch Change.

| Bancos | Botones |
|---|---|
| 0–29, `00A`–`14B` | Al entrar en el banco se carga el preset con el mismo nombre. 1 pone el bypass, 2 activa Infinite Repeats, D marca el tap tempo |
| 30, `LOOP` | El looper: Record, Play, Stop, Undo, Redo, Reverse, Half Speed y tap |
| 31, `FS` | Los pulsadores A y B del TimeLine, el Pre/Post del looper, bypass, repeticiones infinitas y tap |

| Función | CC | Valores |
|---|---|---|
| Bypass | 102 | 0 bypass, 127 activo |
| Infinite Repeats | 97 | 127 activo, 0 apagado |
| Looper Stop, Play, Record, Undo, Redo | 85, 86, 87, 89, 90 | cualquier valor |
| Looper Reverse, Half Speed, Pre/Post | 94, 95, 96 | cualquier valor lo cambia |
| Pulsadores A y B | 80, 82 | 0 al pisar, 127 al soltar, el "down=0 up=127" del manual |
| Pedal de expresión 1, 2 | 100, 14 | la expresión del TimeLine, y Mix |

### BigSky

**`python/templates/BigSky.csv`**, según el manual del BigSky, rev D. Se prepara como el TimeLine.

| Bancos | Botones |
|---|---|
| 0–30, `00A`–`10A` | Al entrar en el banco se carga el preset con el mismo nombre. 1 pone el bypass, 2 sostiene la reverb mientras está pisado, 3 la deja sostenida, D marca el tap tempo |
| 31, `FS` | Los pulsadores A, B y C del BigSky, bypass, sostenido y tap |

El sostenido es el Press/Hold switch del BigSky, CC 97: que sea infinito o congele depende del ajuste del preset. Los pulsadores A, B y C son los CC 80, 82 y 81, enviados como los del TimeLine; el bypass es el CC 102, y los pedales de expresión son la expresión del BigSky, CC 100, y Mix, CC 15.

### Volante

**`python/templates/Volante.csv`**, según el manual del Volante, rev E. Conecta el MIDI OUT de la pedalera al MIDI IN del Volante; de fábrica escucha en el canal 1.

| Bancos | Botones |
|---|---|
| 0–29, `P000`–`P029` | Al entrar en el banco se carga el preset con el mismo número; del 0 al 7 son los ocho de los botones del Volante. 1 pone el bypass, 2 invierte, 3 pausa con rampa, 4 sostiene el eco, oscilando, mientras está pisado, D marca el tap tempo |
| 30, `SOS` | El looper SOS: activar y desactivar el modo SOS, Record / Splice / Clear, Exit, invertir, pausa y tap |
| 31, `HEAD` | Las cuatro cabezas de reproducción, eco y reverb activos o no, y tap |

| Función | CC | Valores |
|---|---|---|
| Cabezas de reproducción 1–4 | 21–24 | 127 activa, 0 apagada |
| SOS mode, Pause (ramp), Reverse, Infinite Hold | 41, 43, 44, 45 | 127 activo, 0 apagado |
| SOS Record / Splice / Clear, Exit SOS Looper | 49, 50 | cualquier valor |
| Echo, Reverb | 78, 79 | 127 activo, 0 apagado |
| Bypass | 102 | 0 bypass, 127 activo |
| Pedal de expresión 1, 2 | 100, 12 | la expresión del Volante, y Echo Level |

Los botones de cabezas, eco y reverb empiezan apagados, tenga el preset lo que tenga activo.

### Iridium

**`python/templates/Iridium.csv`**, según el manual del Iridium, rev D. El Iridium no tiene conector DIN: su MIDI entra por la toma EXP, con el cable MIDI EXP de Strymon o cualquier adaptador MIDI TRS desde el MIDI OUT de la pedalera. Pon antes la toma en modo Digital: enciende el Iridium con FAV pisado y gira LEVEL hasta que el LED ON se ponga azul. De fábrica escucha en el canal 1.

| Bancos | Botones |
|---|---|
| 0–31, `P000`–`P031` | Al entrar en el banco se carga el preset con el mismo número; el 0 es el de FAV. 1 2 3 eligen el ampli, Round, Chime o Punch, A B C la sala, pequeña, mediana o grande, y D pone el bypass |

Los botones de ampli y de sala forman dos grupos exclusivos, así que los LED muestran la última elección; empiezan apagados, porque no se sabe la del preset. El ampli es el CC 19 con 1 a 3, el tamaño de sala el CC 18 con 1 a 3, el bypass el CC 102. Los pedales de expresión son el pedal de volumen del Iridium, CC 7, y Drive, CC 13.

## Plantilla para Hotone Ampero II

**`python/templates/Ampero_II.csv`** está lista para grabar y manejar un Hotone Ampero II, según su MIDI Control Information List (firmware V1.0.2). Conecta el MIDI OUT de la pedalera al MIDI IN del Ampero II; de fábrica escucha en todos los canales, Omni, tanto por MIDI IN como por USB.

| Bancos | Botones |
|---|---|
| 0–29, `01-1`–`08-2` | Al entrar en el banco se carga el patch con el mismo nombre. 1 2 3 4 son las escenas 1–4, A y B los slots de efecto de FS1 y FS2, C abre y cierra el afinador, D marca el tap tempo |
| 30, `LOOP` | El looper: su menú, Record / Overdub, Play / Stop, Undo / Redo, Clear, Half Speed y Reverse, encendidos mientras están activos, y tap |
| 31, `FS` | El menú de la caja de ritmos y su Play / Stop, el afinador, el bypass, encendido mientras está en bypass, y los slots de efecto de FS1–FS4 |

| Función | CC | Valores |
|---|---|---|
| Patch Volume, Expression Pedal (EXP 3) | 7, 11 | los pedales de expresión; el volumen va de 0 a 100 |
| Escena | 25 | 1–4 |
| Menú de la caja de ritmos, Play / Stop | 36, 37 | 127 activo, 0 apagado |
| Afinador, menú del looper | 60, 62 | 127 activo, 0 apagado |
| Looper Rec / Overdub, Undo / Redo, Clear | 63, 67, 68 | 127, solo al pisar |
| Looper Play / Stop | 64 | 127 reproduce, 0 para |
| Looper Speed, Playback | 65, 66 | 0 media velocidad, al revés; 127 vuelve a lo normal |
| Tap Tempo | 76 | 127, solo al pisar |
| Engage / Bypass | 78 | 0 bypass analógico, 2 activo |
| FS 1–4 Effect Slot | 79–82 | 127, luego 0 |

Un patch por encima del 128 lleva un Program Change con `BankSelect_(PC)` a 128 y `BankSelectHighByte_(PC)` a `Y`, 256 por encima del 256, que envía el CC#0 con 1 o 2. El Ampero II Stomp y el Stage tienen mapas propios, con tres y cinco patches por banco y cinco escenas, así que los nombres de los patches no coincidirían.

## Plantilla para Boss RC-600

**`python/templates/RC-600.csv`** está lista para grabar y manejar una Boss RC-600 Loop Station. Conecta el MIDI OUT de la pedalera al MIDI IN de la RC-600; de fábrica escucha en el canal 1 (MENU > MIDI > RX CH CTL).

| Bancos | Botones |
|---|---|
| 0–30, `M001`–`M031` | Al entrar en el banco se recupera la memoria 01 a 31. 1 2 3 graban y reproducen las pistas 1–3, 4 deshace y rehace, A arranca todas las pistas, B las para, C borra la pista actual, D marca el tap tempo |
| 31, `TRKS` | Las pistas 4–6, y los mismos deshacer, arrancar, parar, borrar y tap |

Las memorias y el arranque y la parada no necesitan nada: un Program Change del 0 al 98 recupera la memoria 01 a 99, y MIDI Start y Stop arrancan y paran las pistas según los ajustes ALL START y ALL STOP de la memoria. El resto no tiene CC MIDI de fábrica: prepáralo en **MEMORY > ASSIGN**, cada ASSIGN con SW ON, SOURCE MODE MOMENT, y ACT LOW 0 y ACT HIGH 127:

| SOURCE | TARGET |
|---|---|
| MIDI CC#80, 81, 82 | TRK1 REC/PLY, TRK2 REC/PLY, TRK3 REC/PLY |
| MIDI CC#86, 87, 88 | TRK4 REC/PLY, TRK5 REC/PLY, TRK6 REC/PLY |
| MIDI CC#83, 84, 85 | CUR.TRK UN/RED, CUR.TRK CLEAR, TAP TEMPO |
| MIDI CC#70, 71 | los pedales de expresión: LOOP LEVEL, o el nivel de una pista |

La RC-600 guarda los ajustes de ASSIGN en cada memoria, así que tienen que estar, y escritos, en cada memoria que recupera la plantilla. Todos los botones envían 127 al pisar y 0 al soltar.

## Plantilla para Kemper Profiler Player

**`python/templates/Kemper_Player.csv`** está lista para grabar y manejar un Kemper Profiler Player. El Player no tiene tomas DIN: conecta el USB de la pedalera a la toma USB A del Player, que hace de ordenador y la alimenta. Ese es el enlace cuyo Active Sensing, un byte cada 300 ms, atasca el firmware de fábrica; este lo lee y lo vacía todo según llega, así que el enlace nunca se atasca.

| Bancos | Botones |
|---|---|
| 0–9, `BK01`–`BK10` | Los diez bancos de cinco rigs del Player. Al entrar en el banco se preselecciona, 1 2 3 4 A cargan sus rigs 1–5, B y C pisan los botones de efecto I y II del Player, y D marca el tap tempo |
| 10, `FX` | Módulos A, B, DLY y REV, y luego los cuatro botones de efecto I a IIII |
| 11, `TOOL` | Afinador, velocidad del rotary, delay infinity, freeze, todos los efectos a la vez, delay y reverb otra vez pero conservando sus colas, y tap |

Solo se usan esos doce bancos, así que la plantilla activa `Setlist_Mode` y Bank Up / Down los recorren saltándose los vacíos; una pulsación larga salta cinco. Los botones de rig forman un grupo exclusivo, así que el LED y la pantalla muestran el último rig elegido y pisar otra vez el que está encendido no envía nada. Entrar en un banco solo lo preselecciona en el Player: el rig cambia cuando pisas uno de los cinco, y eso es lo que evita que el sonido vaya dando saltos mientras recorres los bancos con el pie.

El Player tiene un mapa MIDI fijo, así que no hay que asignar nada: escucha en los dieciséis canales salvo que **System Settings > MIDI In Channel** diga otra cosa. La plantilla envía:

| Función | CC | Valores |
|---|---|---|
| Pedal de wah, pedal de volumen | 1, 7 | los dos pedales de expresión |
| Todos los módulos a la vez | 16 | 127 invierte todos los módulos |
| Módulo A, módulo B | 17, 18 | 127 y 0 |
| Delay, reverb | 26, 28 | 127 y 0, cortando las colas |
| Delay, reverb conservando las colas | 27, 29 | 127 y 0 |
| Tap Tempo | 30 | 127, solo al pisar |
| Afinador | 31 | 127 lo abre, 0 lo cierra |
| Velocidad del rotary, delay infinity, freeze | 33, 34, 35 | 127, y cada pisada lo cambia |
| Preselección de banco | 47 | 0–9, se envía al entrar en uno de los diez bancos de rigs |
| Rigs 1–5 del banco | 50–54 | 1, que es lo que carga el rig |
| Botones de efecto I–IIII | 75–78 | 127 y 0 |

Para usar otro canal, cambia `CHANNEL` al principio de `python/make_kemper_player_template.py` y vuelve a ejecutarlo, o edita los botones en el configurador. Los cincuenta rigs también responden a un Program Change normal: el manual del Player los numera del 1 al 50, que aquí es `Number` del 0 al 49.

## Plantillas para programas del ordenador

Cuatro plantillas para los programas que tocan en directo desde un ordenador, con la pedalera en su USB. Se apoyan en lo que funciona sin aprender nada: un Program Change donde el programa responde a uno, y sus propios atajos de teclado, que la pedalera teclea como lo haría un teclado USB. Los atajos van a la ventana que está delante, así que en el escenario deja el programa ahí. Lo que un programa no tiene como atajo sale como un CC, para aprenderlo una vez; los pedales de expresión envían los CC 11 y 1, expresión y rueda de modulación, a los que la mayoría de instrumentos responden tal cual.

En las tablas, Ctrl, Shift y Cmd son las teclas que la pedalera mantiene con la tecla; los modificadores del comando Key están en [Teclas del teclado](06-commands.md#teclas-del-teclado).

### Apple MainStage

**`python/templates/MainStage.csv`**. MainStage responde de fábrica a los Program Change de cualquier controlador y da a cada patch un número; **Reset Program Change Numbers**, Opción-Mayúsculas-Comando-R, los numera en el orden de la Patch List.

| Bancos | Botones |
|---|---|
| 0–30, `P000`–`P030` | Al entrar en el banco se selecciona el patch con ese número de programa. 1 y 2 el patch anterior y el siguiente (↑ ↓), 3 y 4 el primer patch del set anterior y del siguiente (← →), A reproducir / parar (Espacio), B grabar (Ctrl+R), C el afinador (Cmd+T), D tap tempo (Ctrl+T) |
| 31, `CTRL` | Pánico (Ctrl+P), silencio general (Ctrl+M), patch anterior y siguiente, y FX1–FX4, CC 20–23, 127 activo y 0 apagado, para asignarlos a controles de pantalla con **Assign & Map** |

### Gig Performer

**`python/templates/Gig_Performer.csv`**. Gig Performer da de fábrica un Program Change a cada rackspace, desde 0 y en su orden.

| Bancos | Botones |
|---|---|
| 0–31, `R000`–`R031` | Al entrar en el banco se selecciona el rackspace con ese número. 1 y 2 la parte de canción de arriba y de abajo en la vista Setlist (↑ ↓), 3 reproducir / parar, 4 pánico, A y B FX1 y FX2, C el afinador (Shift+T), D tap tempo |

Aprende los CC una vez en **Options > Global MIDI**, con **Momentary** marcado, porque cada pulsación envía 127 y al soltar 0: Tap Tempo CC 20, Play/Stop CC 21 y Panic CC 22. FX1 y FX2, CC 24 y 25, 127 activo y 0 apagado, son para widgets.

### Cantabile

**`python/templates/Cantabile.csv`**, para Cantabile en Windows.

| Bancos | Botones |
|---|---|
| 0–31, `S000`–`S031` | Al entrar en el banco se carga la canción del set list con ese número de programa. 1 y 2 el estado anterior y el siguiente (Shift+T, T), 3 reproducir / parar, 4 pánico, A B C FX1–FX3, D tap tempo |

Cantabile responde a los Program Change mediante un binding: añade uno en el background rack desde la entrada MIDI de la pedalera, con Program Change, al set list, cargando la canción por su número de programa. Asigna el resto igual, con **Learn Binding**: tap tempo CC 20, reproducir / parar CC 21 y pánico CC 22, cada uno 127 al pisar y 0 al soltar. FX1–FX3, CC 24–26, 127 activo y 0 apagado, son para parámetros de plugins.

### Ableton Live

**`python/templates/Ableton_Live.csv`**. Live no responde a los Program Change, así que esta tiene dos bancos, y un setlist mantiene en ellos Bank Up y Bank Down.

| Bancos | Botones |
|---|---|
| 0, `LIVE` | La vista Session y el transporte: 1 y 2 la escena de arriba y la de abajo (↑ ↓), 3 lanza la escena seleccionada (Enter), 4 el metrónomo (O, Live 12), A reproducir / parar (Espacio), B continuar (Shift+Espacio), C grabar (F9), D tap tempo |
| 1, `FX` | FX1–FX8, CC 21–28, 127 activo y 0 apagado |

Asigna los CC una vez en el modo MIDI Map, **Cmd+M** (Ctrl+M en Windows): haz clic en el botón Tap y pisa D, haz clic en un parámetro y pisa un botón FX, y sal del modo. La entrada MIDI de la pedalera necesita **Remote** activado en Settings > Link, Tempo & MIDI.

## Kemper en las dos direcciones

Todo lo anterior va en una sola dirección: la pedalera le dice al ampli qué hacer y confía en que haya hecho caso. A un Kemper Profiler también se le puede preguntar por su estado, y entonces la pedalera muestra lo que el ampli está haciendo de verdad, llegue como llegue a ello.

**Para activarlo**, marca **Talk to a Kemper** en la pestaña **Global** del configurador (`Kemper_Mode` `Y` en el CSV), o parte de la [plantilla del Kemper Player](#plantilla-para-kemper-profiler-player), que lo trae activado. El editor de la pedalera lo ofrece como `KEMPER`.

Vuelven dos cosas que merece la pena ver desde el suelo:

- **El rig en el que estás**, en la línea pequeña junto al nombre del banco, y ahí se queda, banco tras banco, hasta que cambia el rig. Caben once caracteres; un nombre más largo, de hasta 32, [se desplaza por la pantalla una vez](09-the-display.md#texto-desde-el-ordenador) cuando cambia el rig y cada vez que entras en un banco. La pedalera lo pregunta cada segundo, así que acierta aunque el rig se haya cambiado en el propio ampli.
- **Qué módulos de efecto están funcionando.** Un módulo que se enciende o se apaga se convierte en el Control Change que activa ese módulo —17 y 18 para los stomps A y B, 19, 20, 22 y 24 para C, D, X y MOD, 26 y 28 para delay y reverb, y 27 y 29, que conservan las colas— y se pasa al mismo mecanismo que [`LED_Feedback`](12-configuration-file.md#global_settings). Cualquier botón toggle que envíe uno de esos queda encendido o apagado igual que el ampli, en todos los bancos, tanto si el módulo se cambió con tu pie como con los botones del propio ampli o desde otro sitio. No se envía nada de vuelta por ello, así que los dos no pueden perseguirse, y el canal no tiene por qué coincidir: las respuestas del ampli no llevan canal.

**Qué Kempers.** Las respuestas llegan por USB. En un **Profiler Player** es la misma toma a la que ya está conectada la pedalera: el Player hace de ordenador, alimenta la pedalera y habla MIDI por ahí, así que no hace falta nada más. Un Profiler en cabezal o un Stage tendrían que llegar a la entrada MIDI propia de la pedalera, que el hardware no tiene, así que ahí la pedalera sigue hablando en una sola dirección, como antes.

<details><summary>Por dentro</summary>

La pedalera envía al ampli el mensaje que le pide que informe de lo que hace a partir de ese momento, y lo repite cada cinco segundos, que es lo que le dice al ampli que sigue habiendo alguien al otro lado. De los ocho módulos, el ampli informa de seis por su cuenta; del delay y la reverb no, así que la pedalera pregunta por esos dos cada segundo, y por el nombre del rig también cada segundo. Pregunta por los ocho al arrancar y cada vez que cambia el rig. El modo seguro deja `Kemper_Mode` desactivado, así que no sale ni la baliza ni ninguna pregunta.

</details>

*Firmware 0.55 o posterior.*

### Probado sin ampli

La conversación se probó contra `python/Kemper_Sim.py`, un Kemper de mentira que responde por el mismo enlace USB que usaría un Player: contesta a lo que pregunta la pedalera y te deja cambiar el rig o activar un módulo para ver cómo lo sigue la pedalera.

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

Todavía no se ha probado con un Kemper de verdad. Los números que usa —el `00 20 33` del fabricante, las funciones, las páginas de módulos y la baliza— son los de la documentación MIDI del Profiler y los de los controladores abiertos que hablan con él, y un test compara la lista del firmware con la de las herramientas, así que si algún ampli no está de acuerdo, el arreglo estará en esa tabla de números y en ningún otro sitio.


## Tres puertos USB

Con `USB_Ports` a 3 la pedalera aparece en el ordenador como tres puertos MIDI USB en vez de uno:

| Puerto | Nombre en macOS | Qué es |
|---|---|---|
| 1 | `MIDI Commander Custom Pedal` | La pedalera, como con un puerto. |
| 2 | `MIDI Commander Custom DIN` | Directo a la toma MIDI OUT. |
| 3 | `MIDI Commander Custom Config` | Otra vez la pedalera, para un segundo programa. |

**El puerto 2** convierte la pedalera en una interfaz MIDI USB para el equipo de su salida DIN. Lo que un programa manda ahí sale por la toma MIDI OUT tal como llegó, reloj y SysEx incluidos, y la pedalera no lo ve: no cambia de banco, no pisa pulsadores ni sigue ese reloj, y no se aplican `USB_MIDI_Thru`, `RealTime_Passthrough` ni el mapa MIDI. Así una DAW puede tocar el sinte que hay detrás de la pedalera por el puerto 2 y hablar con la pedalera por el puerto 1, cada cosa por su lado. Por el puerto 2 no vuelve nada, porque la pedalera no tiene toma MIDI IN.

**El puerto 3** es la misma pedalera que el puerto 1: lo que manda la pedalera sale por los dos, y escucha a los dos por igual. Un configurador recibe las respuestas por el puerto por el que preguntó. Está para un segundo programa: en Windows un puerto solo lo puede abrir un programa a la vez, así que mientras una DAW tiene el puerto 1, el configurador, la [página del navegador](14-in-the-browser.md) o las [herramientas de línea de comandos](13-command-line-tools.md) usan el 3. Las herramientas lo eligen solas cuando está, y nunca el puerto 2. Deja el puerto 3 desactivado en la DAW, o lo oirá todo dos veces.

Los puertos cambian la próxima vez que arranca la pedalera; flashear una configuración la reinicia. Una DAW configurada con un puerto necesita que vuelvas a elegírselo, porque cambian los nombres, y por eso un puerto sigue siendo lo normal. Con tres puertos la pedalera da además un número de serie USB propio, para que macOS y Windows la configuren como un aparato nuevo en vez de quedarse con el único puerto que recuerdan; la entrada de un puerto se queda en Configuración de Audio MIDI, desconectada, para cuando vuelvas. Cambiar de configuración en la pedalera (`NextConfig`) mantiene los puertos con los que arrancó.

Windows numera los puertos en vez de nombrarlos, `MIDIOUT2 (MIDI Commander Custom)` y así, y los núcleos de Linux antiguos los llaman `MIDI 1` a `MIDI 3`; las herramientas también conocen esos nombres, pero los tres puertos solo se han probado en macOS por ahora.

Necesita el firmware 1.04 (el bit 1 del byte global 6, junto a `USB_MIDI_Thru` en el bit 0).


## Traducir lo que llega

Un DAW, un secuenciador o un teclado conectados por USB rara vez hablan el idioma del pedal antiguo que cuelga del cable DIN: el DAW cambia de escena con un Program Change y el delay quiere dos CC; la rueda de modulación del teclado es el CC 1, y el volumen del ampli el CC 11 y al revés. El **mapa MIDI** pone la pedalera en medio y traduce.

Cada entrada dice **cuándo**, un mensaje que llega por USB, y en qué **se convierte**:

- **Cuándo**: su tipo, `Note`, `CC`, `PC`, `Pressure` (Channel Pressure) o `PitchBend`; su canal o cualquiera; su número (la nota, el CC, el programa) o cualquiera; y un rango de valores, de 0 a 127 si no se estrecha. Un `Note Off` cuenta como una nota de velocidad 0, el valor de un PC es su programa, y el de un pitch bend sus siete bits altos.
- **Se convierte** en otro mensaje por la salida DIN: otro tipo, canal o número, vacío para el mismo, y el rango de valores llevado a otro. De 127 a 0 le da la vuelta, un solo valor envía siempre ese valor, y nada deja el valor como llegó. Un PC hecho sin número toma el valor como programa, así que `CC 20` se convierte en el `PC` de su valor.
- O **ejecuta la lista de un botón**, indicada por banco, botón y pulsación corta, larga o doble, como hace un [`Macro`](06-commands.md#macros). La lista se ejecuta como la ejecutaría una pulsación, con sus comandos por USB y DIN; un `Note Off`, una velocidad 0 o un valor por debajo de 64 la ejecutan con sus toggles apagados, así que un pad pisado mantiene un toggle encendido.
- O **Nothing**, que solo detiene el mensaje.

Actúan todas las entradas que casan, así que un mensaje puede dar varios: dos entradas con el mismo PC envían dos CC. Un mensaje que ha casado con alguna entrada ya no sigue tal cual, salvo que una de ellas tenga marcado **also as it came**; lo que hacen las entradas sale tanto si `USB_MIDI_Thru` está activado como si no, y un mensaje que no casa con ninguna sigue por el thru como siempre. Hasta 32 entradas por configuración.

El mapa convive con todo lo demás que escucha la pedalera. [`Remote_Mode`](12-configuration-file.md#usb-midi) va primero, y un mensaje que pisa un pulsador no sigue; la selección de banco por PC o CC, `LED_Feedback` y el seguimiento de los programas del host siguen viendo un mensaje que el mapa ha traducido.

**En el configurador** es la pestaña **MIDI Map**, cada entrada con su **When** y su **Becomes**; el configurador web también la tiene.

**En el demo**, un PC en el canal 15 se convierte en CC 20 = 127 y CC 21 = el programa en el canal 2, la rueda de modulación en el canal 14 se convierte en el CC 11 del canal 1 dado la vuelta y además sigue tal cual, la nota 36 en el canal 14 mantiene encendido el afinador del banco global mientras está pisada, y el pitch bend del canal 14 se convierte en el CC 4.

### MidiMap_Settings

Una fila por entrada. Las celdas vacías toman el valor por defecto indicado.

| Columna | Valores | Significado |
|---|---|---|
| `In_Type` | `Note`, `CC`, `PC`, `Pressure`, `PitchBend` | El mensaje con el que casa. Una fila sin él se ignora. |
| `In_Channel` | `Any`, 1–16 | Por defecto cualquiera. |
| `In_Number` | `Any`, 0–127 | La nota, el CC o el programa. `Pressure` y `PitchBend` no tienen: déjalo vacío. |
| `In_Min`, `In_Max` | 0–127 | Los valores con los que casa. Por defecto 0 y 127. |
| `Out_Type` | `Note`, `CC`, `PC`, `Pressure`, `PitchBend`, `Run`, `Nothing` | En qué se convierte. Por defecto el mismo tipo. |
| `Out_Channel` | `Same`, 1–16 | Por defecto el mismo. |
| `Out_Number` | `Same`, 0–127 | Por defecto el mismo; un `Note` o `CC` hecho a partir de un `Pressure` o `PitchBend` necesita uno. |
| `Out_Min`, `Out_Max` | 0–127 | `In_Min`..`In_Max` llevado a estos. Los dos vacíos: el valor como llegó; solo uno: siempre ese valor. |
| `Run_Bank`, `Run_Button`, `Run_List` | 0–31, `1`–`D`, `Short` / `Long` / `Double` | La lista que ejecuta un `Out_Type` `Run`. |
| `Keep` | Y / N | Además tal cual llegó. |

<details><summary>Por dentro</summary>

Las páginas de un slot estaban llenas, así que el mapa vive en una segunda zona de extensión, dos páginas de flash por slot por encima de la página del banner de arranque, que las herramientas ven como la configuración que sigue tras la zona de doble pulsación. Empieza con la marca `EXT2` y solo cuenta si está. Una entrada ocupa 12 bytes, descritos en `flash_midi_settings.h`. El mapa se consulta en la interrupción USB, igual que el thru; una lista a ejecutar se pone en cola allí, ocho como mucho, y la ejecuta el bucle principal.

</details>

*Firmware 0.90 o posterior; un firmware anterior recibe todo lo demás y las herramientas avisan de que el mapa se ha quedado fuera.*

---

[← Editar en la pedalera](10-editing-on-the-pedal.md) · [Índice](README.md) · [El archivo de configuración →](12-configuration-file.md)
