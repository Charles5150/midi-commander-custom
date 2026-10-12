# En el navegador

[English](../en/14-in-the-browser.md) · **Español**

El configurador web hace en una página del navegador lo mismo que el configurador de escritorio y las herramientas de línea de comandos: editar una configuración, leer y escribir los slots de la pedalera, hacer copias de seguridad, tocar la pedalera desde la pantalla, mostrar en grande para el escenario la canción en la que estás y actualizar su firmware. Sin instalar nada: ni Python ni `dfu-util`. Y sin pedalera, ejecuta en la página el propio firmware de la pedalera: mira [Sin pedalera](#sin-pedalera).

**https://charles5150.github.io/midi-commander-custom/**

Hace falta un navegador con Web MIDI y WebUSB: **Chrome**, **Edge** u **Opera**, en un ordenador. Safari no tiene ninguno de los dos; en un iPad, mira [En un iPad o un iPhone](#en-un-ipad-o-un-iphone). Firefox tiene Web MIDI, mediante un complemento de permiso del sitio que ofrece la primera vez que la página lo pide, pero no WebUSB, así que la actualización del firmware necesita Chrome, Edge u Opera. La página ejecuta dentro del navegador el mismo código Python de las herramientas, con [Pyodide](https://pyodide.org), así que una configuración se comprueba y se empaqueta exactamente igual que en el configurador, y los ficheros CSV son los mismos: uno guardado en uno se abre en el otro. La primera visita descarga unos 20 MB, Python y pandas, que el navegador guarda; a partir de ahí abre en unos segundos.

## Conectar

Pulsa **Connect the pedal**. El navegador pregunta una vez si la página puede usar dispositivos MIDI, con SysEx: acéptalo. La cabecera muestra entonces el firmware y el slot que tiene en marcha la pedalera. Cuando la pedalera se reinicia, la página vuelve a encontrarla sola.

Cierra antes el configurador de escritorio y cualquier otro programa que use la pedalera: en Windows un puerto MIDI solo puede estar abierto en un programa a la vez. O dale a la pedalera [tres puertos USB](11-devices.md#tres-puertos-usb): la página usa entonces el tercero, y una DAW puede quedarse con el primero.

## Sin pedalera

**Try without a pedal**, junto a **Connect the pedal**, pone en marcha una pedalera simulada: el propio firmware, el mismo código que ejecuta la pedalera, compilado para el navegador. Todo lo de la página funciona con ella igual que con la de verdad: leer y escribir sus cuatro slots, hacer copias, la vista en directo, pulsar sus interruptores. Sirve para probar una configuración antes de escribirla en la pedalera, o para probar el firmware antes de comprarla.

- La primera vez no tiene nada, así que la página escribe la demo en su slot 1. Lo que escribas en ella después se guarda en el navegador y sigue ahí en la siguiente visita.
- La cabecera dice **Simulated pedal**, con el firmware que ejecuta. **Stop** la apaga; lo escrito en ella se queda.
- Bajo la vista en directo, **What the pedal sends** muestra cada mensaje que manda y por dónde: por USB, por la salida DIN o como tecla del teclado del ordenador (**Keys**). **Expression pedals** mueve sus dos pedales de talón a punta; si no, sus jacks están vacíos.
- La pestaña **Firmware** no tiene nada que actualizar: la pedalera simulada ejecuta el firmware con el que vino la página, que es el más nuevo, a veces más nuevo que la última release.

Lleva el tiempo como la pedalera, milisegundo a milisegundo, pero la ejecuta el navegador: una pestaña en segundo plano la hace ir más lenta. No le llega nada de fuera de la página y nada le contesta: ni un Kemper, ni reloj o respuesta para sus LEDs desde el ordenador, ni otro programa MIDI. Tampoco hay bootloader que actualizar.

## Abrir una configuración

- **Read from pedal** lee un slot, el que está en marcha u otro.
- **Open CSV** abre un fichero de configuración, del configurador o de las herramientas de línea de comandos.
- **Demo** abre la configuración de demostración, que usa todas las funciones.
- **Your rig** abre una de las plantillas que vienen con las herramientas, hechas para un aparato o un programa: una Quad Cortex, un BigSky, Ableton Live y el resto de [las plantillas](11-devices.md). Hasta tres aparatos más, cada uno en su canal, le añaden sus pulsadores o su looper en bancos propios, como explica [Tu equipo](11-devices.md#tu-equipo-varios-aparatos-a-la-vez), y luego una lista dice qué poner en cada aparato. Se abre sin nombre de fichero, así que **Save CSV** le pone el de la configuración.

La página de inicio tiene los mismos cuatro, y ninguno se puede pulsar mientras se lee o se escribe la pedalera.

El nombre de la configuración está arriba, seguido de **changed** hasta que se guarda o se escribe; un cambio hecho mientras se escribe en la pedalera sigue marcado, porque no está en ella. Salir de la página con cambios sin guardar, o mientras se escribe o se actualiza la pedalera, pregunta antes.

## Editar

Las pestañas siguen las del configurador de escritorio:

- **Banks**: los 32 bancos a la izquierda; el nombre y la línea de información del banco; sus ocho botones colocados como en la pedalera, 1 a 4 arriba y A a D abajo, cada uno con su etiqueta y su primer comando. Pulsa un botón para editarlo: **Press**, **Long press** y **Double press** tienen diez comandos cada una, de A a J, y **Press** además la etiqueta, el modo del LED, el grupo exclusivo y las opciones del botón. Cada comando muestra los campos que necesita su tipo, como en el configurador, con una línea que dice qué hace. **Device…**, junto al tipo, rellena un comando desde el mapa MIDI de un equipo, y un CC o un Program Change muestra el nombre que le da el equipo, como [en el configurador](03-the-configurator.md#desde-el-mapa-midi-de-un-equipo); su última opción, **More devices…**, busca uno de los 571 equipos de la comunidad por fabricante o modelo, y solo entonces los carga, unos 170 kB. Debajo de los botones, **On entering this bank** y **Expression pedals in this bank**. **Save song** y **Load song**, junto al nombre del banco, guardan el banco como [archivo de canción](04-banks.md#canciones-un-banco-en-un-archivo-propio) y cargan uno en él. **Notes for the Stage view** guarda la nota del banco para [Stage](#stage).
- **Global**: todos los ajustes globales, en los grupos del configurador, con las mismas opciones y rangos.
- **Expression**, **Bank switches**, **SysEx**, **Setlist**, **Combos**, **MIDI map** y **Preset names**, como en el configurador.

Cada cambio se comprueba al hacerlo. Si la configuración no se puede empaquetar, una línea roja bajo la barra de herramientas dice qué está mal y dónde, y no se puede guardar ni escribir hasta arreglarlo.

Toda la página funciona con el teclado y con un lector de pantalla: cada campo tiene nombre, la pestaña, el banco, el botón y la pulsación que se editan van marcados como los actuales, y tras un clic o un cambio el foco se queda donde estaba. Los mensajes se leen en voz alta al aparecer.

## Guardar y escribir

- **Save CSV** descarga la configuración como fichero CSV.
- **Cheat sheet** abre la configuración en una pestaña nueva como una página para imprimir, con un botón **Print**: los pulsadores de cada banco como en la pedalera y lo que envían en palabras, el setlist con sus tempos, los pedales y las combinaciones, como la hace [Cheat_Sheet](13-command-line-tools.md#cheat_sheet-una-página-para-imprimir). Si el navegador bloquea la pestaña, descarga la página.
- **Write to pedal** pregunta en qué slot escribir, lo lee, lo que tarda unos segundos, y lista lo que va a cambiar en él al escribir, como hace [Diff_Config](13-command-line-tools.md#diff_config-qué-cambia): el slot equivocado o un archivo viejo se ven antes de escribir nada. Si eliges otro slot, lee ese. **Write** no espera a la lista. Luego lo escribe y reinicia la pedalera: unos 12 segundos. Como con el configurador, escribir el slot que está en marcha pone la pedalera en pausa hasta el reinicio. Si la pedalera no acepta el slot pedido, no se escribe nada; si una escritura falla después de borrar el slot, la página lo dice, y hay que volver a escribirlo. El firmware anterior a 0.24 tiene una sola configuración, así que la página solo ofrece el slot 1.
- **Back up all slots** lee todos los slots que tienen configuración y luego los lista, un fichero CSV por slot: **Save all** los descarga juntos, o haz clic en uno para descargarlo solo. Puede que el navegador pregunte una vez si la página puede descargar varios ficheros. Si ningún slot tiene configuración, lo dice.

## La pedalera en directo

La pantalla de la pedalera, sus LEDs y sus diez interruptores, como están en la pedalera, varias veces por segundo. Necesita firmware 0.27 o posterior; con uno más antiguo la pestaña lo dice. Pulsa un interruptor en la pantalla, con el ratón o con el dedo, para pulsarlo en la pedalera: queda pisado mientras lo mantienes, así que las pulsaciones largas también funcionan. Con el teclado, llega a un interruptor con Tab y mantén Espacio o Intro.

## Stage

La canción en la que estás, legible a unos pasos, para una tablet o un portátil en un pie de micro. **Full screen** la pone a pantalla completa, y la página impide que la pantalla se apague mientras la pestaña está abierta. Sigue a la pedalera varias veces por segundo, desde el firmware 0.27:

- el nombre del banco, en grande, y su línea de información;
- su puesto en el setlist, `FULL SET · 3 of 10`, y la canción siguiente, `Next: S04 · song 4`, o `Last song`;
- el tempo, `120 BPM`, mientras la pedalera manda clock MIDI por USB, y el compás y el tiempo, `bar 5 · 3`, mientras el clock corre tras un Start; los tiempos del compás son los de **Bar and beat on the display**, 4 si no se ha puesto;
- el banco que **Bank Up** o **Bank Down** muestran antes de confirmarlo, con `Bank_Preview` activado;
- la nota del banco, de **Notes for the Stage view** en la pestaña Banks: la tonalidad, una cejilla, entradas, la letra;
- los ocho botones como recuadros grandes, 1 a 4 arriba y A a D abajo, con sus etiquetas como las muestra la pedalera y los toggles encendidos en color.

El setlist, la línea de información y las notas salen de la configuración abierta en la página, así que abre la que lleva la pedalera, o léela de la pedalera y abre luego el CSV con las notas. Si el nombre del banco ahí no es el de la pedalera, la vista la toma por otra configuración y muestra solo el banco y los botones de la pedalera. Un banco que está en varios setlists se sitúa en el primero que lo tiene, y sigue en ese mientras los bancos siguientes también estén en él; **Setlist** elige uno a mano.

Las notas se guardan en el CSV, en una columna `Notes` de `Bank_Naming`, y en el archivo de canción guardado desde el banco; la pedalera nunca las tiene, así que escribirlas no cambia nada en ella, y leer una configuración de la pedalera no trae ninguna. El configurador de escritorio las conserva al guardar. En un iPad, Safari no tiene Web MIDI: mira [En un iPad o un iPhone](#en-un-ipad-o-un-iphone).

## En un iPad o un iPhone

Safari no tiene Web MIDI, y en iOS todos los navegadores son Safari por dentro. Algunas apps añaden Web MIDI a las páginas que abren: **Web MIDI Browser**, gratis en el App Store, es una. Abre la página en ella y conecta la pedalera al puerto USB-C del iPad, o mediante el adaptador de Lightning a USB 3 para cámaras de Apple con su cargador enchufado; la pedalera funciona con la corriente de su cable USB.

Conectar, leer y escribir slots, editar, **Live pedal** y **Stage** funcionan como en un ordenador. **Full screen** cubre la página en vez de la pantalla, que estas apps no dan a una página, con **×** en la esquina para salir. **Save CSV**, un archivo de canción y la chuleta abren el menú de compartir, donde **Guardar en Archivos** los guarda. El firmware no se puede actualizar: ningún navegador de iOS tiene WebUSB, así que usa un ordenador. La primera visita descarga Python y pandas, unos 20 MB; mejor con wifi.

## Firmware

Elige un fichero `.dfu` de las [releases](https://github.com/Charles5150/midi-commander-custom/releases) y pulsa **Update**. La página comprueba antes el fichero, como `Update_Firmware.py`, y rechaza uno que no sea una imagen para esta pedalera. Después:

1. Pide a la pedalera que se reinicie en su modo de actualización (firmware 0.58 o posterior).
2. La primera vez, el navegador pregunta qué dispositivo puede usar la página: elige el que se llama **STM32 BOOTLOADER** o **DFU in FS Mode**.
3. Borra las páginas del firmware, escribe el fichero, lo vuelve a leer entero para comprobarlo y arranca otra vez la pedalera. Unos 15 segundos.

El bootloader y las configuraciones no se tocan nunca. Una pedalera con firmware más antiguo, o con el de fábrica, se pone en modo de actualización a mano: mantén **Bank Down** y **D** mientras la enchufas, pulsa **Update** y elígela. Así tampoco la primera grabación necesita tener nada instalado.

En Windows el bootloader necesita el controlador WinUSB, igual que para `dfu-util`: instálalo una vez con [Zadig](https://zadig.akeo.ie) para el dispositivo `STM32 BOOTLOADER`. En Linux el navegador necesita la regla de udev de [Primeros pasos](02-getting-started.md#1-flashea-el-firmware) para llegar a él.

## Cuando algo falla

- **No se pudo cargar el Python del configurador.** La página lee, comprueba y empaqueta las configuraciones con el mismo Python de las herramientas, que el navegador descarga de cdn.jsdelivr.net la primera vez. Sin conexión, o con ese sitio bloqueado por una extensión o una red de empresa, la página de inicio lo dice en rojo, con **Reload the page**. La pedalera en directo y el firmware funcionan sin él; abrir, leer y escribir una configuración no, y una pedalera simulada arranca vacía.
- **Un archivo que no es una configuración** se rechaza diciendo lo que le falta, y la configuración abierta sigue abierta.
- **La demo o una plantilla no se descarga**, sin conexión por ejemplo: la página lo dice, y la configuración abierta sigue abierta.
- **Una parte de la configuración se queda fuera.** El firmware anterior a 0.90 no admite el mapa MIDI ni las etiquetas de pulsación larga, y el anterior a 0.26 no admite la doble pulsación: **Write to pedal** escribe el resto, dice qué ha dejado fuera y mantiene la configuración marcada como **changed**, porque la pedalera no la tiene entera.
- **Una cadena SysEx que la pedalera no enviaría tal cual**, con un byte que no es hexadecimal, uno mayor que `7F` o más de 23 bytes, se señala en la línea roja bajo la barra de herramientas, y la configuración no se puede guardar ni escribir hasta corregirla.
- **El navegador no permitió el MIDI.** Chrome recuerda la negativa. La página dice cómo volver a permitirlo: el icono a la izquierda de la barra de direcciones, la configuración del sitio, **Dispositivos MIDI** («Controlar y reprogramar tus dispositivos MIDI» en Chrome) en Permitir, y recargar.
- **La pedalera no contesta.** Una Midi Commander que aparece pero no responde casi seguro lleva el firmware de MeloAudio: la página lo dice y abre la pestaña Firmware, donde se actualiza poniendo la pedalera en modo de actualización a mano.
- **Una actualización falló** con la pedalera ya en su modo de actualización: se queda en él, con la pantalla apagada, y la pestaña Firmware lo dice. Pulsa **Update** otra vez con el mismo archivo; no hace falta conectar antes la pedalera.

Un mensaje que hay que leer con calma se queda bajo la barra de herramientas hasta cerrarlo con ×, o hasta que se conecta la pedalera. Un error en la esquina también se queda hasta cerrarlo con ×; los demás mensajes de ahí se van a los pocos segundos.

## Ejecutarlo desde el repositorio

La página es `web/index.html`, y carga los ficheros Python de `python/lib`. La pedalera simulada es `web/pedal-sim.wasm`, compilada a partir de las fuentes del firmware con `firmware/sim/build.sh` (mira [su README](../../../firmware/sim/README.md)). Para probar un cambio, sirve la raíz del repositorio y abre la página allí:

```bash
python3 -m http.server 8000
```

y luego `http://localhost:8000/web/`. Web MIDI y WebUSB funcionan en `localhost` sin HTTPS.

---

[← Herramientas de línea de comandos](13-command-line-tools.md) · [Índice](README.md)
