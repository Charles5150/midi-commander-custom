# Primeros pasos

[English](../en/02-getting-started.md) · **Español**

Este capítulo lleva una pedalera del firmware de fábrica a tu primera configuración: flasheas el firmware una vez a mano, instalas las herramientas y cargas una configuración. A partir de ahí, las actualizaciones no necesitan mantener nada pisado.

**Sin instalar nada.** En Chrome, Edge u Opera, el [configurador web](14-in-the-browser.md) hace todo este capítulo desde una página del navegador, incluida la primera grabación: pon la pedalera en modo de actualización a mano como en el paso 1, abre la pestaña **Firmware** de la página y elige el fichero `.dfu`. El resto del capítulo es el camino con las herramientas de escritorio.

**Qué necesitas**

- la pedalera, una MeloAudio Midi Commander o una Harley Benton MP-100;
- un cable USB;
- un ordenador con macOS, Windows o Linux, y Python 3.12 para las herramientas de escritorio;
- `dfu-util`, para la primera actualización del firmware.

Flashear el firmware no borra tu configuración, y el bootloader de la pedalera nunca se escribe, así que siempre puedes volver a poner el firmware de fábrica.

## 1. Flashea el firmware

La primera vez hay que poner la pedalera en su modo de actualización a mano. El firmware viene como un archivo `.dfu` ya compilado, adjunto a la [última release](https://github.com/Charles5150/midi-commander-custom/releases/latest). Las imágenes anteriores están en la página de [releases](https://github.com/Charles5150/midi-commander-custom/releases). Si lo prefieres, puedes compilar tú la imagen, como explica [CONTRIBUTING](../../../CONTRIBUTING.md) (en inglés); los dos caminos llegan al mismo sitio.

1. Instala `dfu-util`:
   - macOS: `brew install dfu-util`;
   - Linux: el gestor de paquetes de tu distribución, por ejemplo `sudo apt install dfu-util`;
   - Windows: descárgalo de [dfu-util.sourceforge.net](https://dfu-util.sourceforge.net/releases/) y pon `dfu-util.exe` en una carpeta del `PATH`, o en la carpeta del repositorio del paso 2, donde también lo buscan las herramientas.

   En Windows, la pedalera en modo DFU necesita además el controlador WinUSB, una sola vez: con la pedalera en modo DFU como en el paso 2, abre [Zadig](https://zadig.akeo.ie), elige **STM32 BOOTLOADER** (en **Options → List All Devices** si no aparece), **WinUSB** como controlador e **Install Driver**. En Linux, o ejecutas `dfu-util` con `sudo`, o dejas que tu usuario llegue a la pedalera con una regla de udev, una sola vez:

   ```bash
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="df11", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/70-midi-commander.rules
   sudo udevadm control --reload-rules
   ```

2. Con la pedalera apagada, mantén pisados **Bank Down** y **D**, los dos pulsadores de abajo a la derecha, y enciéndela. La pantalla se queda a oscuras y se enciende el LED 3: la pedalera está en modo DFU.
3. Conéctala por USB y comprueba que se ve:

   ```text
   $ dfu-util --list
   Found DFU: [0483:df11] ... alt=0, name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", ...
   ```

4. Flashéala con `--alt 0`, la entrada de la flash interna en esa lista:

   ```bash
   dfu-util -d 0483:df11 --alt 0 --download midi-commander-custom-<version>.dfu
   ```

5. Apaga y vuelve a encender la pedalera. Después de una descarga con `dfu-util` a secas se queda en modo DFU hasta que lo hagas. La versión del firmware sale un momento en la pantalla, y luego el primer banco.

Cuando tengas instaladas las herramientas del paso 2, `Update_Firmware.py` puede hacer los pasos 3 a 5 por ti: flashea una pedalera que ya está en modo DFU y la vuelve a arrancar sola.

## 2. Instala las herramientas de Python

El configurador y las herramientas de línea de comandos son programas en Python de este repositorio.

1. **Consigue los archivos.** Descarga [el repositorio en un ZIP](https://github.com/Charles5150/midi-commander-custom/archive/refs/heads/main.zip) y descomprímelo donde quieras, o, con git, `git clone https://github.com/Charles5150/midi-commander-custom.git`.
2. **Instala Python 3.12.**
   - macOS y Windows: desde [python.org](https://www.python.org/downloads/). Su instalador trae Tk, que necesita la ventana del configurador.
   - Linux: el Python 3 de tu distribución y, en Debian o Ubuntu, `sudo apt install python3-venv python3-tk`.

   También valen Python 3.10 y 3.11. Con un Python más nuevo, python-rtmidi, la librería que habla MIDI, no viene ya compilada y hay que compilarla, y para eso hace falta un compilador: en Windows las C++ Build Tools de Microsoft, en macOS `xcode-select --install`, en Linux `build-essential libasound2-dev libjack-jackd2-dev`. Puedes tener varias versiones de Python a la vez, y el lanzador elige la 3.12 si está.
3. **Abre el lanzador** que hay en la carpeta del repositorio:
   - macOS: doble clic en **Start Configurator.command**. La primera vez, macOS puede negarse a abrir un archivo descargado de internet: clic derecho, **Abrir**, y **Abrir** otra vez.
   - Windows: doble clic en **Start Configurator.bat**. Si lo para Windows SmartScreen, **Más información** y **Ejecutar de todas formas**.
   - Linux: `./start-configurator.sh` en un terminal.

   La primera vez crea un entorno de Python en la carpeta `.venv` e instala lo que necesitan las herramientas, un minuto o dos; después abre el configurador directamente. Si falta algo, te dice qué instalar en tu sistema. `--check` lo prepara y lo comprueba sin abrir el configurador.

<details><summary>Lo mismo a mano, en un terminal</summary>

Desde la carpeta del repositorio, en macOS y Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
.venv/bin/python python/gui_configurator.py
```

En Windows:

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r python\requirements.txt
.venv\Scripts\python python\gui_configurator.py
```

Este manual escribe los comandos a la manera de macOS y Linux, `.venv/bin/python python/...`; en Windows son `.venv\Scripts\python python\...`.

</details>

## 3. Configura la pedalera

En el configurador es donde se monta una configuración y se envía a la pedalera. Lo abre el lanzador del paso 2; desde un terminal es `.venv/bin/python python/gui_configurator.py`.

1. Conecta la pedalera en modo normal, no en modo DFU.
2. Carga un punto de partida:
   - el configurador se abre con `python/demo-all-features.csv`, una configuración que usa todas las funciones, con etiquetas que dicen qué hace cada botón;
   - o una de las [plantillas](11-devices.md) listas para un Fractal FM3, Line 6 HX Stomp, Neural DSP Quad Cortex, Eventide H90, pedal Strymon, Hotone Ampero II, Boss RC-600 o Kemper Player, o MainStage, Gig Performer, Cantabile o Ableton Live, con **Load CSV…**;
   - o **Read from Device**, para partir de lo que tiene ahora la pedalera.
3. Edítala.
4. Pulsa **Flash to Device**.

[El configurador](03-the-configurator.md) recorre todas las pestañas.

## Actualizar el firmware más adelante

Con el firmware 0.58 o posterior en la pedalera, una actualización no necesita mantener nada pisado ni apagar y encender, y tarda unos quince segundos. Conecta la pedalera como siempre y ejecuta

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

o usa **Update Firmware…** en el apartado PEDAL del configurador.

1. Primero comprueba el archivo, y rechaza uno que no sea una imagen para esta pedalera.
2. Pregunta antes de flashear; `--yes` se salta la pregunta.
3. Pide a la pedalera que se reinicie en modo DFU, la flashea y la vuelve a arrancar.
4. Te dice con qué versión ha vuelto la pedalera.

Una pedalera que ya está en modo DFU, porque la pusiste a mano o por una actualización que no terminó, se flashea directamente.

La configuración se queda como estaba. Cuando una release cambia el formato de la configuración, el [changelog](../../../CHANGELOG.md) lo dice; en ese caso vuelve a cargar tu configuración con las herramientas actualizadas.

## Si algo sale mal

- **La pedalera se queda en FIRMWARE UPDATE, o arranca con la pantalla a oscuras como en el paso 1.** Está esperando una imagen en modo DFU, después de una actualización que no terminó. Seguirá arrancando así hasta que se flashee algo. Vuelve a ejecutar `Update_Firmware.py` o **Update Firmware…**, o flashéala con `dfu-util` como en el [paso 1](#1-flashea-el-firmware).
- **Quieres volver al firmware de fábrica.** El bootloader nunca se toca, así que la imagen del fabricante se puede flashear igual que en el paso 1. La configuración de este firmware vive en la propia flash del microcontrolador, y la configuración de fábrica, en la EEPROM externa, no se toca.
- **Una configuración te descoloca el equipo al encender.** Arranca la pedalera en [modo seguro](10-editing-on-the-pedal.md#modo-seguro).
- **La pedalera se ha reiniciado sola y ha mostrado RESTARTED.** Su watchdog la encontró colgada y la reinició, de vuelta en el banco, los toggles y el tempo que tenía. [Abre una incidencia](https://github.com/Charles5150/midi-commander-custom/issues) contando qué estaba haciendo: un cuelgue es un fallo.

<details><summary>Por dentro</summary>

El bootloader de fábrica es la demo de DFU de ST. Solo arranca el firmware cuando Bank Down y D están sin pisar **y** la primera palabra del firmware, su puntero de pila inicial, parece válida. Cuando se le pide por SysEx, el firmware escribe un cero sobre esa palabra y se reinicia, así que el bootloader se queda en modo DFU; la imagen nueva trae de vuelta una palabra buena. Mientras la pedalera espera en modo DFU, su pantalla dice **FIRMWARE UPDATE**. Si no se flashea nada, sigue arrancando en modo DFU, como si los pulsadores estuvieran pisados, hasta que se flashee algo.

</details>

---

[← Qué hace](01-what-it-does.md) · [Índice](README.md) · [El configurador →](03-the-configurator.md)
