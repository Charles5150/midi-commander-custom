# Herramientas de línea de comandos

[English](../en/13-command-line-tools.md) · **Español**

Todo lo que hace el configurador se puede hacer también desde un terminal, que viene bien para scripts, copias de seguridad y un flasheo rápido antes de un bolo. Ejecuta las herramientas desde la raíz del repositorio, con la pedalera conectada por USB en modo normal, no en modo DFU. Los ejemplos usan el entorno que crea el [lanzador](02-getting-started.md#2-instala-las-herramientas-de-python), `.venv/bin/python`; en Windows escribe `.venv\Scripts\python` y `python\CSV_to_Flash.py`.

Las herramientas encuentran la pedalera por su nombre MIDI USB, `MIDI Commander Custom`, y comprueban la versión de su firmware antes de hacer nada. Con [tres puertos USB](11-devices.md#tres-puertos-usb) usan el tercero, `Config`, y nunca el del DIN.

## Elegir una ranura de configuración

`CSV_to_Flash.py`, `Flash_to_CSV.py` y `Diff_Config.py` trabajan sobre una de las cuatro [ranuras de configuración](04-banks.md#cuatro-configuraciones) de la pedalera:

- `--slot 1` a `--slot 4` elige la ranura;
- si no lo pones, usan la ranura que está usando la pedalera.

Si lees una ranura vacía, te lo dicen en lugar de sacar un CSV. El firmware anterior a la 0.24 tiene una sola configuración, y con él las herramientas rechazan cualquier ranura que no sea la 1.

## CSV_to_Flash: enviar una configuración a la pedalera

```bash
.venv/bin/python python/CSV_to_Flash.py my-config.csv
.venv/bin/python python/CSV_to_Flash.py --slot 2 my-config.csv
```

Comprueba el CSV, dice cuánto ocupa la configuración y pregunta `Continue? (y/N)` antes de escribir nada; `--yes` o `-y` se salta la pregunta. Luego escribe la ranura y reinicia la pedalera.

## Flash_to_CSV: leer una configuración de vuelta

```bash
.venv/bin/python python/Flash_to_CSV.py current-config.csv
.venv/bin/python python/Flash_to_CSV.py --slot 3 slot3.csv
```

Escribe lo que tiene la pedalera en un CSV que puedes abrir en el configurador, incluido cualquier cambio hecho con el [editor de la pedalera](10-editing-on-the-pedal.md).

## Diff_Config: qué cambia

```bash
.venv/bin/python python/Diff_Config.py my-config.csv
.venv/bin/python python/Diff_Config.py --slot 2 my-config.csv
.venv/bin/python python/Diff_Config.py old.csv new.csv
```

Con un CSV, lee la ranura de la pedalera y dice qué cambiaría escribir ahí el CSV; con dos, qué cambia del primero al segundo. No escribe nada. Una línea por cambio, en palabras normales, y al final cuántos:

```text
Slot 1 holds "DEMO ALL". Writing my-config.csv to it changes:
Global: Don't resend the same PC: on -> off
Bank 1 LOOP, button 4, long press: A CC: CC#: 5 -> 21, Toggle: off -> on
Bank 5 MEDI, button 2: B: CC Ch 2, CC# 7, On 127 added
3 changes
```

Así pillas la ranura equivocada o un archivo viejo antes de un concierto, y ves qué hace distinto de la tuya una configuración que te han pasado. Los dos lados se empaquetan primero tal como los guarda la pedalera, así que solo cuenta lo que llega a ella: no el orden de las columnas del CSV, sus comentarios ni un campo que el comando no usa. Un comando que pasa a otra letra aparece como cambiado en las dos. Leer la ranura tarda unos 7 segundos. Termina con 0 si no cambia nada, 1 si cambia algo, 2 si un CSV tiene un error y 3 si no se pudo leer la pedalera, como `diff`. Los dos configuradores enseñan la misma lista antes de escribir: mira [Flash to Device](03-the-configurator.md#barra-lateral) y [Write to pedal](14-in-the-browser.md#guardar-y-escribir).

## Cheat_Sheet: una página para imprimir

```bash
.venv/bin/python python/Cheat_Sheet.py mi-config.csv
.venv/bin/python python/Cheat_Sheet.py mi-config.csv --open
.venv/bin/python python/Cheat_Sheet.py mi-config.csv -o hoja.html --device 2="Fender Tone Master Pro"
```

Escribe la configuración como una página para imprimir, `mi-config.html` junto al CSV salvo que `-o` diga otra: las etiquetas de cuatro caracteres dicen poco a la banda o al técnico. Un bloque por cada banco en uso, con sus pulsadores colocados como en la pedalera, 1–4 arriba y A–D abajo, cada uno con su etiqueta, su etiqueta de pulsación larga y lo que envían sus pulsaciones corta, larga y doble en palabras; un comando que entiende un equipo conocido va con el nombre que le da el equipo, como `HX Stomp: Snapshot 1`. Debajo de un banco, lo que envía al entrar y adónde apuntan sus pedales. Antes de los bancos, el setlist en su orden con el tempo de cada canción, sacado de un **Tap Set** en la lista de entrada de su banco, los pedales de expresión, los pulsadores de banco y las combinaciones. `--open` la abre en el navegador, cuyo **Imprimir** la pasa a papel o a PDF. El equipo de cada canal se deduce de los comandos, como hacen los configuradores; `--device CANAL=NOMBRE` indica uno que no encuentran, cualquier nombre de su menú **Device**, y puede repetirse. Antes se empaqueta tal como lo guarda la pedalera, y una configuración con un error no da página y termina con 2. Los dos configuradores hacen la misma página: **Cheat Sheet…** en la [barra lateral](03-the-configurator.md#barra-lateral) y **Cheat sheet** [en el navegador](14-in-the-browser.md#guardar-y-escribir).

## Copias de seguridad

`Backup_Slots.py` copia las cuatro ranuras a una carpeta de una vez, y las vuelve a poner.

```bash
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup
```

**backup** lee a la carpeta cada ranura que tenga una configuración:

- `slot1.csv` a `slot4.csv`, cada uno una configuración normal que se puede abrir en el configurador o cargar por separado;
- `backup.txt`, con la fecha, el firmware y el nombre de cada ranura.

Si no le das carpeta, crea una con la fecha y la hora como nombre.

**restore** vuelve a poner una carpeta de copia:

1. Comprueba cada archivo antes de tocar la pedalera.
2. Enumera las ranuras que va a sobrescribir y pregunta antes; `--yes` o `-y` se salta la pregunta.
3. Escribe cada archivo en su ranura, y reinicia la pedalera una sola vez al final.

Las ranuras sin archivo en la carpeta se quedan como están. Una copia restaurada da los mismos bytes de los que se leyó, salvo que los ajustes que nunca tuvo una configuración de un firmware anterior se escriben con el valor que ya usaba la pedalera para ellos.

## Send_Text: escribir en la pantalla

```bash
.venv/bin/python python/Send_Text.py "Sweet Child"
.venv/bin/python python/Send_Text.py --banner "The Band  612 345 678"
```

Pone un texto en la línea de arriba de la pedalera, o con `--hex` imprime los bytes SysEx para que los envíe otro programa; con `--banner` lee, guarda o borra el texto propio del banner. Mira [Texto desde el ordenador](09-the-display.md#texto-desde-el-ordenador) y [El texto propio del banner](09-the-display.md#el-texto-propio-del-banner).

## Kemper_Sim: un Kemper para probar Kemper_Mode sin tenerlo

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

Responde a la pedalera como lo haría un Kemper Profiler, por la misma conexión USB que usa un Player. En su prompt:

| Comando | Qué hace |
|---|---|
| `rig <name>` | pone nombre al rig que enseña la pedalera |
| `a`, `b`, `c`, `d` | enciende o apaga el Stomp A, B, C o D |
| `x`, `mod`, `dly`, `rev` | lo mismo con los demás módulos |
| `show` | lo que se supone que está haciendo el ampli |
| `quit` | termina |

Mira [Kemper en las dos direcciones](11-devices.md#kemper-en-las-dos-direcciones).

## GT1000_Sim: una GT-1000 para probar GT1000_Mode sin tenerla

```bash
.venv/bin/python python/GT1000_Sim.py
gt1000> patch 12 Lead Boost
gt1000> fx DELAY 1
```

Responde a la pedalera como lo haría una Boss GT-1000, con los mensajes RQ1 y DT1 de Roland. Arranca en un patch cuyos ASSIGN 1–4 activan OD/DS 1, DELAY 1, REVERB y CHORUS con los CC 80–83, y un CC de la pedalera activa el efecto como lo haría la unidad. En su prompt:

| Comando | Qué hace |
|---|---|
| `patch <n> [nombre]` | va al patch n y le pone nombre |
| `assign <n> <efecto> <cc>` | el ASSIGN n (1–16) activa ese efecto cuando llega ese CC |
| `fx <efecto>` | enciende o apaga un efecto, como su pulsador en la unidad |
| `show` | lo que se supone que está haciendo la unidad |
| `quit` | termina |

Mira [GT-1000 en las dos direcciones](11-devices.md#gt-1000-en-las-dos-direcciones).

## Update_Firmware: actualizar el firmware

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

Comprueba el archivo `.dfu`, pregunta antes de flashear (`--yes` se salta la pregunta), pone la pedalera en modo DFU, la flashea y la vuelve a arrancar, sin mantener nada pisado con el firmware 0.58 o posterior. Mira [Actualizar el firmware más adelante](02-getting-started.md#actualizar-el-firmware-más-adelante).

## Stress_Test, Latency_Test y Endurance_Test: poner a prueba la pedalera

```bash
.venv/bin/python python/Stress_Test.py      # work the pedal hard for a minute and check it is still sound
.venv/bin/python python/Latency_Test.py     # how long a press takes to leave as MIDI, quiet and under load
.venv/bin/python python/Endurance_Test.py   # an hour at a gig's pace, checking nothing drifts
```

`Stress_Test.py` le da caña a la pedalera durante un minuto y comprueba que sigue en forma; `Latency_Test.py` mide cuánto tarda una pisada en salir como MIDI, en reposo y con carga; `Endurance_Test.py` la deja tocando sola una hora al ritmo de un concierto (`--minutes` para más), con una línea cada dos minutos más o menos, y al final dice si alguna ronda falló y cuánta pila no ha llegado a usar nunca la pedalera. Conviene pasarla la víspera de un concierto, después de actualizar el firmware. Las tres necesitan la configuración de demostración, `python/demo-all-features.csv`, en la pedalera, y ningún pie. Se describen en [CONTRIBUTING](../../../CONTRIBUTING.md#tests) (en inglés).

## Ver lo que envía la pedalera

Cualquier monitor MIDI lo enseña: MIDI Monitor en macOS, MIDI-OX en Windows, o `aseqdump -p 'MIDI Commander Custom'` en Linux.

<details><summary>Por dentro</summary>

Las herramientas intercambian la configuración como mensajes SysEx con el ID de fabricante `0x7D`:

| Comando | Número |
|---|---|
| borrar | 52 |
| escribir un bloque de 16 bytes | 54 |
| leer un bloque | 56 |
| versión | 58 |
| reiniciar | 60 |
| lecturas de los pedales | 62 |
| elegir una ranura | 64 |
| pisar un pulsador | 66 |
| el estado de la pedalera | 68 |
| la pantalla de la pedalera | 70 |
| poner texto en la pantalla | 72 |
| reiniciar en modo DFU, con los bytes de comprobación `44 46` | 74 |
| el texto propio del banner | 76 |
| la latencia de las últimas pisadas | 78 |
| mantener un pedal de expresión en una posición | 80 |

Cada uno se contesta con su número más uno. Un borrado o una escritura que la flash no ha podido hacer se contesta con un byte más, `01`, desde el firmware 0.71, y las herramientas se detienen y lo dicen; un mensaje de longitud equivocada se ignora.

Los comandos de lectura necesitan el firmware 0.2 o posterior; las herramientas te avisan si la pedalera tiene uno anterior.

</details>

---

[← El archivo de configuración](12-configuration-file.md) · [Índice](README.md) · [En el navegador →](14-in-the-browser.md)
