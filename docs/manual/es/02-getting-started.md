# Primeros pasos

[English](../en/02-getting-started.md) · **Español**

Este capítulo lleva una pedalera del firmware de fábrica a tu primera configuración: flasheas el firmware una vez a mano, instalas las herramientas y cargas una configuración. A partir de ahí, las actualizaciones no necesitan mantener nada pisado.

**Qué necesitas**

- la pedalera, una MeloAudio Midi Commander o una Harley Benton MP-100;
- un cable USB;
- un ordenador con Python 3;
- `dfu-util`, para la primera actualización del firmware.

Flashear el firmware no borra tu configuración, y el bootloader de la pedalera nunca se escribe, así que siempre puedes volver a poner el firmware de fábrica.

## 1. Flashea el firmware

La primera vez hay que poner la pedalera en su modo de actualización a mano. El firmware viene como un archivo `.dfu` ya compilado, adjunto a la [última release](https://github.com/Charles5150/midi-commander-custom/releases/latest). Las imágenes anteriores están en la página de [releases](https://github.com/Charles5150/midi-commander-custom/releases), y algunas se guardan también en `artifacts/` como referencia. Si lo prefieres, puedes compilar tú la imagen, como explica [CONTRIBUTING](../../../CONTRIBUTING.md) (en inglés); los dos caminos llegan al mismo sitio.

1. Instala `dfu-util`:
   - macOS: `brew install dfu-util`;
   - Linux: el gestor de paquetes de tu distribución;
   - Windows: [dfu-util.sourceforge.net](https://dfu-util.sourceforge.net/).
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

```bash
git clone https://github.com/Charles5150/midi-commander-custom.git
cd midi-commander-custom
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
```

En macOS con el Python de Homebrew, el configurador necesita además Tk: `brew install python-tk`.

## 3. Configura la pedalera

En el configurador es donde se monta una configuración y se envía a la pedalera.

```bash
.venv/bin/python python/gui_configurator.py
```

1. Conecta la pedalera en modo normal, no en modo DFU.
2. Carga un punto de partida:
   - el configurador se abre con `python/demo-all-features.csv`, una configuración que usa todas las funciones, con etiquetas que dicen qué hace cada botón;
   - o una de las [plantillas](11-devices.md) listas para un Fractal FM3, un Line 6 HX Stomp o un Kemper Player, con **Load CSV…**;
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

<details><summary>Por dentro</summary>

El bootloader de fábrica es la demo de DFU de ST. Solo arranca el firmware cuando Bank Down y D están sin pisar **y** la primera palabra del firmware, su puntero de pila inicial, parece válida. Cuando se le pide por SysEx, el firmware escribe un cero sobre esa palabra y se reinicia, así que el bootloader se queda en modo DFU; la imagen nueva trae de vuelta una palabra buena. Mientras la pedalera espera en modo DFU, su pantalla dice **FIRMWARE UPDATE**. Si no se flashea nada, sigue arrancando en modo DFU, como si los pulsadores estuvieran pisados, hasta que se flashee algo.

</details>

---

[← Qué hace](01-what-it-does.md) · [Índice](README.md) · [El configurador →](03-the-configurator.md)
