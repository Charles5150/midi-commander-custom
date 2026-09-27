# En el navegador

[English](../en/14-in-the-browser.md) · **Español**

El configurador web hace en una página del navegador lo mismo que el configurador de escritorio y las herramientas de línea de comandos: editar una configuración, leer y escribir los slots de la pedalera, hacer copias de seguridad, tocar la pedalera desde la pantalla y actualizar su firmware. Sin instalar nada: ni Python ni `dfu-util`. Y sin pedalera, ejecuta en la página el propio firmware de la pedalera: mira [Sin pedalera](#sin-pedalera).

**https://charles5150.github.io/midi-commander-custom/**

Hace falta un navegador con Web MIDI y WebUSB: **Chrome**, **Edge** u **Opera**, en un ordenador. Safari y Firefox no tienen ninguno de los dos. La página ejecuta dentro del navegador el mismo código Python de las herramientas, con [Pyodide](https://pyodide.org), así que una configuración se comprueba y se empaqueta exactamente igual que en el configurador, y los ficheros CSV son los mismos: uno guardado en uno se abre en el otro. La primera visita descarga unos 20 MB, Python y pandas, que el navegador guarda; a partir de ahí abre en unos segundos.

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
- **Open CSV** abre un fichero de configuración, del configurador, de las herramientas de línea de comandos o una plantilla.
- **Demo** abre la configuración de demostración, que usa todas las funciones.

El nombre de la configuración está arriba, seguido de **changed** hasta que se guarda o se escribe. Salir de la página con cambios sin guardar pregunta antes.

## Editar

Las pestañas siguen las del configurador de escritorio:

- **Banks**: los 32 bancos a la izquierda; el nombre y la línea de información del banco; sus ocho botones colocados como en la pedalera, 1 a 4 arriba y A a D abajo, cada uno con su etiqueta y su primer comando. Pulsa un botón para editarlo: **Press**, **Long press** y **Double press** tienen diez comandos cada una, de A a J, y **Press** además la etiqueta, el modo del LED, el grupo exclusivo y las opciones del botón. Cada comando muestra los campos que necesita su tipo, como en el configurador, con una línea que dice qué hace. Debajo de los botones, **On entering this bank** y **Expression pedals in this bank**.
- **Global**: todos los ajustes globales, en los grupos del configurador, con las mismas opciones y rangos.
- **Expression**, **Bank switches**, **SysEx**, **Setlist**, **Combos** y **MIDI map**, como en el configurador.

Cada cambio se comprueba al hacerlo. Si la configuración no se puede empaquetar, una línea roja bajo la barra de herramientas dice qué está mal y dónde, y no se puede guardar ni escribir hasta arreglarlo.

## Guardar y escribir

- **Save CSV** descarga la configuración como fichero CSV.
- **Write to pedal** pregunta en qué slot escribir, dice qué tiene ahora ese slot, lo escribe y reinicia la pedalera: unos 12 segundos. Como con el configurador, escribir el slot que está en marcha pone la pedalera en pausa hasta el reinicio.
- **Back up all slots** descarga todos los slots que tienen configuración, un fichero CSV por slot.

## La pedalera en directo

La pantalla de la pedalera, sus LEDs y sus diez interruptores, como están en la pedalera, varias veces por segundo. Pulsa un interruptor en la pantalla, con el ratón o con el dedo, para pulsarlo en la pedalera: queda pisado mientras lo mantienes, así que las pulsaciones largas también funcionan.

## Firmware

Elige un fichero `.dfu` de las [releases](https://github.com/Charles5150/midi-commander-custom/releases) y pulsa **Update**. La página comprueba antes el fichero, como `Update_Firmware.py`, y rechaza uno que no sea una imagen para esta pedalera. Después:

1. Pide a la pedalera que se reinicie en su modo de actualización (firmware 0.58 o posterior).
2. La primera vez, el navegador pregunta qué dispositivo puede usar la página: elige el que se llama **STM32 BOOTLOADER** o **DFU in FS Mode**.
3. Borra las páginas del firmware, escribe el fichero, lo vuelve a leer entero para comprobarlo y arranca otra vez la pedalera. Unos 12 segundos.

El bootloader y las configuraciones no se tocan nunca. Una pedalera con firmware más antiguo, o con el de fábrica, se pone en modo de actualización a mano: mantén **Bank Down** y **D** mientras la enchufas, pulsa **Update** y elígela. Así tampoco la primera grabación necesita tener nada instalado.

En Windows el bootloader necesita el controlador WinUSB, igual que para `dfu-util`: instálalo una vez con [Zadig](https://zadig.akeo.ie) para el dispositivo `STM32 BOOTLOADER`. En Linux el navegador necesita la regla de udev de [Primeros pasos](02-getting-started.md#1-flashea-el-firmware) para llegar a él.

## Ejecutarlo desde el repositorio

La página es `web/index.html`, y carga los ficheros Python de `python/lib`. La pedalera simulada es `web/pedal-sim.wasm`, compilada a partir de las fuentes del firmware con `firmware/sim/build.sh` (mira [su README](../../../firmware/sim/README.md)). Para probar un cambio, sirve la raíz del repositorio y abre la página allí:

```bash
python3 -m http.server 8000
```

y luego `http://localhost:8000/web/`. Web MIDI y WebUSB funcionan en `localhost` sin HTTPS.

---

[← Herramientas de línea de comandos](13-command-line-tools.md) · [Índice](README.md)
